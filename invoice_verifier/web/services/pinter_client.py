from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from baca_invoice.agents.postprocess import apply_postprocessing
from baca_invoice.models.authenticity import DocumentAuthenticity
from baca_invoice.models.travel_document import TravelDocumentResult
from baca_invoice.tools.combined import analyze_document

from web.config import (
    LLM_TIMEOUT_SECONDS,
    PINTER_AGENT_BASE_URL,
    PINTER_AGENT_ID,
    PINTER_PLATFORM_API_KEY,
)

logger = logging.getLogger(__name__)


def _normalize_pinter_base_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    for suffix in (
        "/api/agents/openai/v1",
        "/agents/openai/v1",
        "/api/conversations",
        "/conversations",
    ):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    if not cleaned.endswith("/api"):
        cleaned = f"{cleaned}/api"
    return cleaned


def _clean_json_markdown(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


class PinterAgentClient:
    """Klien HTTP untuk menjalankan Agent Pinter (dev.pupuk.ai) via Conversation API."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        agent_id: str | None = None,
        timeout: float = LLM_TIMEOUT_SECONDS,
    ) -> None:
        raw_url = base_url if base_url is not None else PINTER_AGENT_BASE_URL
        self.base_url = _normalize_pinter_base_url(raw_url)
        self.api_key = api_key if api_key is not None else PINTER_PLATFORM_API_KEY
        self.agent_id = agent_id if agent_id is not None else PINTER_AGENT_ID
        self.timeout = timeout

    async def extract_document(self, file_path: str) -> dict[str, Any]:
        """Ekstrak teks PDF secara lokal lalu panggil Pinter Agent via Conversation API."""
        if not self.api_key:
            raise RuntimeError("PINTER_PLATFORM_API_KEY is required to call Pinter Agent")
        if not self.agent_id:
            raise RuntimeError("PINTER_AGENT_ID is required to call Pinter Agent")

        raw_doc = analyze_document(file_path)

        # ponytail: jika file gagal dibaca/rusak, tidak perlu boros panggil remote agent
        if not raw_doc.get("success", False):
            err = raw_doc.get("error", "Gagal membaca dokumen")
            auth_val = raw_doc.get("authenticity") or {}
            auth_obj = None
            try:
                auth_obj = DocumentAuthenticity.model_validate(auth_val)
            except Exception:
                auth_obj = DocumentAuthenticity(verdict="TIDAK DIVERIFIKASI", is_suspicious=False)
            return TravelDocumentResult(
                doc_type="unknown",
                document_subtype="unknown",
                requires_manual_review=True,
                review_reasons=[err],
                summary=f"Gagal membaca file: {err}",
                authenticity=auth_obj,
            ).model_dump()

        doc_payload = {
            "document_data": {
                "tool_success": raw_doc.get("success", False),
                "tool_error": raw_doc.get("error", ""),
                "full_text": raw_doc.get("full_text", ""),
                "authenticity": raw_doc.get("authenticity", {}),
            }
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # 1. Buat thread percakapan dengan agent
            create_conv_url = f"{self.base_url}/conversations/"
            conv_body = {
                "title": "Verifikasi Dokumen Perjalanan Dinas",
                "agent_id": self.agent_id,
            }
            create_resp = await client.post(create_conv_url, headers=headers, json=conv_body)
            if create_resp.status_code not in (200, 201):
                error_msg = (
                    f"Pinter Create Conversation error ({create_resp.status_code}): "
                    f"{create_resp.text}"
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            conv_data = create_resp.json()
            conv_id = conv_data.get("id") or conv_data.get("conversation_id")
            if not conv_id:
                raise ValueError(f"Pinter did not return conversation ID: {conv_data}")

            # 2. Kirim pesan ekstraksi dokumen ke agent
            send_url = f"{self.base_url}/conversations/{conv_id}/send"
            send_body = {
                "message": json.dumps(doc_payload, ensure_ascii=False),
                "agent_id": self.agent_id,
                "stream": False,
            }
            send_resp = await client.post(send_url, headers=headers, json=send_body)
            if send_resp.status_code != 200:
                error_msg = f"Pinter Send Message error ({send_resp.status_code}): {send_resp.text}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)

            send_data = send_resp.json()

        content = send_data.get("message", "")
        cleaned_content = _clean_json_markdown(content)

        try:
            parsed_data = json.loads(cleaned_content)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse JSON from Pinter agent: %s\nContent: %s", exc, content)
            raise ValueError(f"Pinter Agent returned non-JSON content: {exc}") from exc

        result_obj = TravelDocumentResult.model_validate(parsed_data)

        raw_auth = raw_doc.get("authenticity")
        auth_override: DocumentAuthenticity | None = None
        if isinstance(raw_auth, dict):
            try:
                auth_override = DocumentAuthenticity.model_validate(raw_auth)
            except Exception as e:
                logger.warning("Failed to validate local authenticity for override: %s", e)

        final_obj = apply_postprocessing(result_obj, authenticity_override=auth_override)
        return final_obj.model_dump()
