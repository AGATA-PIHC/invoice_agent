from .agents.flight import flight_agent
from .agents.hotel import hotel_agent

# Expose individual agents so agent_runner can pick the right one
# based on server-side document type detection (no coordinator LLM call needed).
root_agent = flight_agent  # ADK CLI default; runtime routing is done in agent_runner.py

__all__ = ["root_agent", "flight_agent", "hotel_agent"]
