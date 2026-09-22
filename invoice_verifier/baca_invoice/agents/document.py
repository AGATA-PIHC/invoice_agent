from google.adk.agents import LlmAgent, SequentialAgent

from ..models.travel_document import TravelDocumentResult
from ..tools.combined import analyze_document
from .postprocess import capture_tool_authenticity, postprocess_llm_response
from .prompts import EXTRACTOR_PROMPT, FORMATTER_PROMPT
from web.config import (
    GEMINI_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
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
    )


extractor_agent = LlmAgent(
    model=_agent_model(),
    name="extractor_agent",
    description=(
        "Memanggil tool analyze_document untuk membaca PDF dan menyimpan "
        "full_text + authenticity ke state."
    ),
    instruction=EXTRACTOR_PROMPT,
    tools=[analyze_document],
    output_key="document_data",
    after_tool_callback=capture_tool_authenticity,
)

formatter_agent = LlmAgent(
    model=_agent_model(),
    name="formatter_agent",
    description=(
        "Mengklasifikasi dan mengekstrak field TravelDocumentResult dari "
        "document_data hasil extractor."
    ),
    instruction=FORMATTER_PROMPT,
    output_schema=TravelDocumentResult,
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
