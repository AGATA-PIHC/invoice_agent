from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools.agent_tool import AgentTool

from ..models.flight import FlightTicketResult
from ..tools import analyze_document_authenticity, extract_pdf_content
from .prompts import FLIGHT_EXTRACTOR, FLIGHT_STRUCTURER

_extractor = LlmAgent(
    model="gemini-2.5-flash",
    name="flight_extractor_agent",
    description="Mengekstrak data tiket pesawat dari PDF",
    instruction=FLIGHT_EXTRACTOR,
    tools=[extract_pdf_content, analyze_document_authenticity],
    output_key="flight_raw",
)

_structurer = LlmAgent(
    model="gemini-2.5-flash",
    name="flight_structurer_agent",
    description="Mengubah hasil ekstraksi tiket pesawat menjadi JSON terstruktur",
    instruction=FLIGHT_STRUCTURER,
    output_schema=FlightTicketResult,
    output_key="flight_result",
)

flight_sequential_agent = SequentialAgent(
    name="flight_ticket_agent",
    description="Verifikasi dan ekstraksi tiket pesawat. Input: path file PDF.",
    sub_agents=[_extractor, _structurer],
)

flight_agent_tool = AgentTool(agent=flight_sequential_agent)
