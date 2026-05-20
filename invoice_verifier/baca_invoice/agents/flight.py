from google.adk.agents import LlmAgent

from ..tools.combined import analyze_document
from .prompts import FLIGHT_TOOL_PROMPT

flight_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="flight_detail_agent",
    description=(
        "Helper agent untuk mengekstrak detail penerbangan/tiket pesawat dari PDF. "
        "Tidak menentukan doc_type."
    ),
    instruction=FLIGHT_TOOL_PROMPT,
    tools=[analyze_document],
)
