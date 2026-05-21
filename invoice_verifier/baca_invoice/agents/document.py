from google.adk.agents import LlmAgent, SequentialAgent

from ..models.travel_document import TravelDocumentResult
from ..tools.combined import analyze_document
from .postprocess import capture_tool_authenticity, postprocess_llm_response
from .prompts import EXTRACTOR_PROMPT, FORMATTER_PROMPT

extractor_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="extractor_agent",
    description="Memanggil tool analyze_document untuk membaca PDF dan menyimpan full_text + authenticity ke state.",
    instruction=EXTRACTOR_PROMPT,
    tools=[analyze_document],
    output_key="document_data",
    after_tool_callback=capture_tool_authenticity,
)

formatter_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="formatter_agent",
    description="Mengklasifikasi dan mengekstrak field TravelDocumentResult dari document_data hasil extractor.",
    instruction=FORMATTER_PROMPT,
    output_schema=TravelDocumentResult,
    after_model_callback=postprocess_llm_response,
)

document_agent = SequentialAgent(
    name="document_agent",
    description="Pipeline klasifikasi & ekstraksi dokumen PDF perjalanan dinas (invoice/receipt/unknown).",
    sub_agents=[extractor_agent, formatter_agent],
)
