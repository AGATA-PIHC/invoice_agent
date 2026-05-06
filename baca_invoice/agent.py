from google.adk.agents import LlmAgent

from .agents import flight_agent_tool, hotel_agent_tool
from .agents.prompts import COORDINATOR

root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="invoice_verification_agent",
    description="Koordinator verifikasi dokumen perjalanan dinas SSC.",
    instruction=COORDINATOR,
    tools=[flight_agent_tool, hotel_agent_tool],
)
