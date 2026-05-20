from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

from ..tools.combined import analyze_document
from .flight import flight_agent
from .hotel import hotel_agent
from .prompts import DOCUMENT_PROMPT

_AGENT_TOOLS = [
    analyze_document,
    AgentTool(agent=hotel_agent, skip_summarization=True),
    AgentTool(agent=flight_agent, skip_summarization=True),
]

document_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="document_agent",
    description=(
        "Klasifikasi dan ekstraksi dokumen PDF sebagai invoice, receipt, atau unknown. "
        "Input: file_path."
    ),
    instruction=DOCUMENT_PROMPT,
    tools=_AGENT_TOOLS,
)
