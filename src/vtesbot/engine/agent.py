"""The only interface a player implements (CLAUDE.md §5): receives an
`Observation`, never raw `GameState`, returns a `Choice` from
`decision.choices`. Real agents are `bot-strategist` territory."""

from typing import Protocol

from .decision import Choice, Decision
from .observation import Observation


class Agent(Protocol):
    def decide(self, observation: Observation, decision: Decision) -> Choice:
        """Return one of `decision.choices`. The engine rejects anything else."""
        ...
