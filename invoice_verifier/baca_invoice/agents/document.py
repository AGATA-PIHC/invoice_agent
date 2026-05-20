from google.adk.agents import LlmAgent

from ..models.travel_document import TravelDocumentResult
from ..tools.combined import analyze_document
from .prompts import DOCUMENT_PROMPT

document_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="document_agent",
    description=(
        "Klasifikasi dan ekstraksi dokumen PDF sebagai invoice, receipt, atau unknown. "
        "Input: file_path."
    ),
    instruction=DOCUMENT_PROMPT,
    tools=[analyze_document],
    output_schema=TravelDocumentResult,
)
