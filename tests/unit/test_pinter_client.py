from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from web.services.pinter_client import (
    PinterAgentClient,
    _clean_json_markdown,
    _normalize_pinter_base_url,
)


def test_normalize_pinter_base_url():
    assert _normalize_pinter_base_url("https://api-dev.pupuk.ai") == "https://api-dev.pupuk.ai/api"
    assert _normalize_pinter_base_url("https://api-dev.pupuk.ai/") == "https://api-dev.pupuk.ai/api"
    assert (
        _normalize_pinter_base_url("https://api-dev.pupuk.ai/api/agents/openai/v1")
        == "https://api-dev.pupuk.ai/api"
    )
    assert (
        _normalize_pinter_base_url("https://api-dev.pupuk.ai/api/conversations")
        == "https://api-dev.pupuk.ai/api"
    )
    assert _normalize_pinter_base_url("http://localhost:8000") == "http://localhost:8000/api"


def test_clean_json_markdown():
    raw_md = '```json\n{"doc_type": "receipt"}\n```'
    assert _clean_json_markdown(raw_md) == '{"doc_type": "receipt"}'

    raw_plain = '{"doc_type": "invoice"}'
    assert _clean_json_markdown(raw_plain) == '{"doc_type": "invoice"}'


@pytest.mark.asyncio
async def test_pinter_client_missing_credentials():
    client = PinterAgentClient(api_key="", agent_id="test_agent")
    with pytest.raises(RuntimeError, match="PINTER_PLATFORM_API_KEY is required"):
        await client.extract_document("/dummy/path.pdf")

    client2 = PinterAgentClient(api_key="sk_test", agent_id="")
    with pytest.raises(RuntimeError, match="PINTER_AGENT_ID is required"):
        await client2.extract_document("/dummy/path.pdf")


@pytest.mark.asyncio
async def test_pinter_client_failed_pdf_short_circuits():
    client = PinterAgentClient(api_key="sk_test", agent_id="agnt_123")
    with patch("web.services.pinter_client.analyze_document") as mock_doc:
        mock_doc.return_value = {
            "success": False,
            "error": "File corrupted",
            "full_text": "",
            "authenticity": {"verdict": "TIDAK DIVERIFIKASI", "is_suspicious": False},
        }
        res = await client.extract_document("/dummy/corrupt.pdf")
        assert res["doc_type"] == "unknown"
        assert res["requires_manual_review"] is True
        assert "File corrupted" in res["review_reasons"]


@pytest.mark.asyncio
async def test_pinter_client_success():
    client = PinterAgentClient(api_key="sk_test", agent_id="agnt_123")

    conv_response = httpx.Response(
        status_code=201,
        json={"id": "conv-test-123"},
        request=httpx.Request("POST", "https://api-dev.pupuk.ai/api/conversations/"),
    )

    send_response = httpx.Response(
        status_code=200,
        json={
            "message": json.dumps(
                {
                    "doc_type": "receipt",
                    "document_subtype": "hotel",
                    "provider": "Tiket.com",
                    "total_payment": 1500000.0,
                    "currency": "IDR",
                    "receipt": {
                        "receipt_number": "TRX-999",
                        "payment_status": "Lunas",
                    },
                    "hotel": {
                        "hotel_name": "Hotel Mulia",
                        "check_in_date": "2026-05-10",
                        "check_out_date": "2026-05-12",
                        "total_nights": 2,
                    },
                }
            )
        },
        request=httpx.Request("POST", "https://api-dev.pupuk.ai/api/conversations/conv-test-123/send"),
    )

    with patch("web.services.pinter_client.analyze_document") as mock_doc, patch(
        "httpx.AsyncClient.post", new_callable=AsyncMock
    ) as mock_post, patch(
        "web.services.pinter_client.apply_postprocessing", side_effect=lambda res, **kw: res
    ):
        mock_doc.return_value = {
            "success": True,
            "full_text": "Sample Hotel Receipt Content",
            "authenticity": {
                "verdict": "asli",
                "is_suspicious": False,
                "confidence_score": 0.95,
            },
        }
        mock_post.side_effect = [conv_response, send_response]

        result = await client.extract_document("/dummy/invoice.pdf")
        assert result["doc_type"] == "receipt"
        assert result["document_subtype"] == "hotel"
        assert result["total_payment"] == 1500000.0
        assert mock_post.await_count == 2


@pytest.mark.asyncio
async def test_agent_runner_delegates_to_pinter():
    from web.services.agent_runner import AgentRunnerService, Job

    runner_service = AgentRunnerService()
    dummy_job = Job(job_id="test_job_1", filename="test.pdf", file_path="/dummy/test.pdf")

    with patch("web.services.agent_runner.USE_PINTER_AGENT", True), patch.object(
        runner_service._pinter_client, "extract_document", new_callable=AsyncMock
    ) as mock_extract:
        mock_extract.return_value = {
            "doc_type": "invoice",
            "document_subtype": "hotel",
            "invoice_number": "INV-123",
            "total_payment": 2000000.0,
            "vendor_name": "Hotel XYZ",
            "summary": "Invoice Hotel",
            "extraction_confidence": 0.85,
            "requires_manual_review": False,
            "review_reasons": [],
            "authenticity": {"verdict": "asli", "is_suspicious": False},
        }

        res = await runner_service._extract_document(dummy_job)
        mock_extract.assert_awaited_once_with("/dummy/test.pdf")
        assert res["doc_type"] == "invoice"
        assert res["invoice_number"] == "INV-123"
        assert res["total_payment"] == 2000000.0
