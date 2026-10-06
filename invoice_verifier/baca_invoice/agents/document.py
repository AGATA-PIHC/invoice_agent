from __future__ import annotations

from collections.abc import AsyncGenerator
import json
import os
import re

from google.adk.agents import BaseAgent, LlmAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

from ..models.travel_document import TravelDocumentResult
from ..tools.authenticity import analyze_authenticity
from ..tools.combined import analyze_document
from ..utils.schema_inline import inline_json_schema_refs
from .postprocess import RAW_AUTHENTICITY_STATE_KEY, postprocess_llm_response
from .prompts import FORMATTER_PROMPT
from web.config import (
    GEMINI_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
)

# Providers OpenAI-compatible seperti Databricks Foundation Model API menolak
# JSON schema yang memakai $ref/$defs untuk model nested (error: "Invalid JSON
# schema - /$defs/<Model>"). Saat OPENAI_BASE_URL dipakai, ratakan skema jadi
# literal supaya tetap valid. Gemini native tidak punya batasan ini, sehingga
# tetap memakai kelas pydantic langsung.
_FORMATTER_OUTPUT_SCHEMA = (
    inline_json_schema_refs(TravelDocumentResult)
    if OPENAI_BASE_URL
    else TravelDocumentResult
)


def _agent_model():
    if not OPENAI_BASE_URL:
        return GEMINI_MODEL

    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is required when OPENAI_BASE_URL is set"
        )
    if not OPENAI_MODEL:
        raise RuntimeError(
            "OPENAI_MODEL is required when OPENAI_BASE_URL is set"
        )

    from google.adk.models.lite_llm import LiteLlm

    model_name = OPENAI_MODEL
    if not model_name.startswith("openai/"):
        model_name = f"openai/{model_name}"
    return LiteLlm(
        model=model_name,
        api_base=OPENAI_BASE_URL,
        api_key=OPENAI_API_KEY,
        extra_headers={"API-Version": "1"},
    )


class ExtractorAgent(BaseAgent):
    """Membaca dokumen (PDF/gambar) secara deterministik tanpa LLM tool call."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        file_path = ""
        if ctx.session and ctx.session.state and ctx.session.state.get("file_path"):
            file_path = str(ctx.session.state["file_path"]).strip()

        if not file_path and ctx.user_content and ctx.user_content.parts:
            for part in ctx.user_content.parts:
                text = getattr(part, "text", "") or ""
                match = re.search(r"file_path:\s*([^\r\n]+)", text)
                if match:
                    file_path = match.group(1).strip().strip("\"'")
                    break
                candidate = text.strip().strip("\"'")
                if candidate and os.path.exists(candidate):
                    file_path = candidate
                    break

        if not file_path:
            raw_doc = {
                "success": False,
                "error": "Path file tidak ditemukan dalam input.",
                "full_text": "",
                "total_pages": 0,
                "authenticity": analyze_authenticity(
                    {"success": False, "error": "Path file tidak ditemukan"}, ""
                ),
            }
        else:
            raw_doc = analyze_document(file_path)

        doc_data_payload = {
            "full_text": raw_doc.get("full_text", ""),
            "authenticity": raw_doc.get("authenticity", {}),
            "tool_success": raw_doc.get("success", False),
            "tool_error": raw_doc.get("error", ""),
        }

        actions = EventActions(
            state_delta={
                "document_data": json.dumps(doc_data_payload, ensure_ascii=False),
                RAW_AUTHENTICITY_STATE_KEY: raw_doc.get("authenticity", {}),
            }
        )
        yield Event(author=self.name, actions=actions)


extractor_agent = ExtractorAgent(
    name="extractor_agent",
    description="Membaca teks dan metadata dokumen ke session state.",
)

formatter_agent = LlmAgent(
    model=_agent_model(),
    name="formatter_agent",
    description=(
        "Mengklasifikasi dan mengekstrak field TravelDocumentResult dari "
        "document_data hasil extractor."
    ),
    instruction=FORMATTER_PROMPT,
    output_schema=_FORMATTER_OUTPUT_SCHEMA,
    after_model_callback=postprocess_llm_response,
)

document_agent = SequentialAgent(
    name="document_agent",
    description=(
        "Pipeline klasifikasi & ekstraksi dokumen PDF perjalanan dinas "
        "(invoice/receipt/unknown)."
    ),
    sub_agents=[extractor_agent, formatter_agent],
)
