from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools.agent_tool import AgentTool

from ..models.hotel import HotelInvoiceResult
from ..tools import analyze_document_authenticity, extract_pdf_content
from .prompts import HOTEL_EXTRACTOR, HOTEL_STRUCTURER

_extractor = LlmAgent(
    model="gemini-2.5-flash",
    name="hotel_extractor_agent",
    description="Mengekstrak data invoice hotel dari PDF",
    instruction=HOTEL_EXTRACTOR,
    tools=[extract_pdf_content, analyze_document_authenticity],
    output_key="hotel_raw",
)

_structurer = LlmAgent(
    model="gemini-2.5-flash",
    name="hotel_structurer_agent",
    description="Mengubah hasil ekstraksi invoice hotel menjadi JSON terstruktur",
    instruction=HOTEL_STRUCTURER,
    output_schema=HotelInvoiceResult,
    output_key="hotel_result",
)

hotel_sequential_agent = SequentialAgent(
    name="hotel_invoice_agent",
    description="Verifikasi dan ekstraksi invoice hotel. Input: path file PDF.",
    sub_agents=[_extractor, _structurer],
)

hotel_agent_tool = AgentTool(agent=hotel_sequential_agent)
