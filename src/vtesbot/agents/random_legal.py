"""The random-legal baseline agent (CLAUDE.md milestone 4).

Picks uniformly among `decision.choices` with no knowledge of decision
`kind`, so by construction it can never raise `IllegalChoiceError`
(`engine/state.py`'s `GameState.ask`).

Agents live outside `engine/`, so they are not bound by `GameRNG` --
CLAUDE.md's "nothing under `engine/` may call `random` directly" is scoped
to the engine's own internal randomness. Each instance owns its own seeded
`random.Random`, so a match stays reproducible from its top-level seed
(`sim/runner.py::run_match`).
"""

import random

from vtesbot.engine.agent import Agent
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.observation import Observation


class RandomLegalAgent(Agent):
    def __init__(self, player_id: str, seed: int) -> None:
        self.player_id = player_id
        self._random = random.Random(seed)

    def decide(self, observation: Observation, decision: Decision) -> Choice:
        return self._random.choice(decision.choices)
