from pathlib import Path


_DOCUMENT_AGENT = Path(__file__).parents[2] / "invoice_verifier" / "baca_invoice" / "agents" / "document.py"


def test_openai_compatible_model_sends_api_version_header():
    source = _DOCUMENT_AGENT.read_text()

    assert '"API-Version": "1"' in source
