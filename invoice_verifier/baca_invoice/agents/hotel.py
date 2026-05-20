from google.adk.agents import LlmAgent

from ..tools.combined import analyze_document
from .prompts import HOTEL_TOOL_PROMPT

hotel_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="hotel_detail_agent",
    description=(
        "Helper agent untuk mengekstrak detail hotel/penginapan dari PDF. "
        "Tidak menentukan doc_type."
    ),
    instruction=HOTEL_TOOL_PROMPT,
    tools=[analyze_document],
)
