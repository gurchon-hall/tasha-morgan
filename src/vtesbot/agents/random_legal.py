"""The random-legal baseline agent (CLAUDE.md milestone 4).

Picks uniformly among whatever `decision.choices` the engine offers, with
no domain knowledge of any decision `kind` -- this is the entire point of a
"random legal" baseline: by construction it can never raise
`IllegalChoiceError` (`GameState.ask`, `engine/state.py`), since it only
ever returns a member of the exact tuple it was given.

Agents live outside `engine/`, so they are not bound by (and cannot share)
`GameRNG` -- CLAUDE.md's "nothing under `engine/` may call `random`
directly" is scoped to the engine's own internal randomness (shuffle/cut/
draw, replayed from the log). Each `RandomLegalAgent` instance owns its own
seeded `random.Random`, so a match is still fully reproducible once its
seed (and the setup seed) are fixed -- see `sim/runner.py::run_match`.
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
