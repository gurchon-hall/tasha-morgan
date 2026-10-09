"""The only interface a player (bot or human-backed) implements.

CLAUDE.md SS5: agents receive an `Observation`, never the raw `GameState`,
and may only return a `Choice` drawn from `decision.choices`. Real agent
implementations (random-legal, heuristic, search-based) are `bot-strategist`
territory (CLAUDE.md SS7, milestone 4+); this module only defines the
Protocol. The one concrete implementation introduced by this pass,
`ScriptedAgent`, is a test helper (see `tests/helpers.py`), not a real agent.
"""

from typing import Protocol

from .decision import Choice, Decision
from .observation import Observation


class Agent(Protocol):
    def decide(self, observation: Observation, decision: Decision) -> Choice:
        """Return one of `decision.choices`. The engine rejects anything else."""
        ...
