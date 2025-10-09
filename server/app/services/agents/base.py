from __future__ import annotations

from typing import Any, Dict, Literal, Protocol, TypedDict

Decision = Literal["BUY", "SELL", "HOLD", "NO_TRADE"]


class AgentOutput(TypedDict):
    decision: Decision
    confidence: float
    inputs: Dict[str, Any]
    notes: str


class Agent(Protocol):
    key: str
    resolution: str

    async def run(self, market: Dict[str, Any]) -> AgentOutput:
        ...
