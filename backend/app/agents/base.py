"""Base interface for all LearnMate AI agents.

Every agent:
  - Has a name and description.
  - Receives a dict of inputs and returns a dict of outputs.
  - Optionally uses the shared GraniteService for LLM calls.

Stage 2 will implement the full intelligent workflows inside each agent.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from app.services.granite import GraniteService, get_granite_service


class AgentInput(dict):  # type: ignore[type-arg]
    """Typed alias — agents receive plain dicts; subclasses may add validation."""


class AgentOutput(dict):  # type: ignore[type-arg]
    """Typed alias — agents return plain dicts; subclasses may add validation."""


class BaseAgent(ABC):
    """Abstract base class for all LearnMate AI agents."""

    name: str = "base_agent"
    description: str = "Base agent"

    def __init__(self, granite: Optional[GraniteService] = None) -> None:
        self.granite = granite or get_granite_service()

    @abstractmethod
    async def run(self, inputs: dict) -> dict:
        """Execute the agent's primary workflow.

        Args:
            inputs: Agent-specific input dictionary.

        Returns:
            Agent-specific output dictionary.
        """

    def _stub_response(self, message: str) -> dict:
        """Return a clearly-marked stub response for Stage 1 placeholders."""
        return {
            "status": "stub",
            "agent": self.name,
            "message": message,
            "stage": 1,
            "note": "Full implementation in Stage 2.",
        }
