"""Random-legal baseline agent (milestone 4). Picks uniformly among
`decision.choices`, so it never raises `IllegalChoiceError`. Owns its own
seeded `random.Random`, unbound by `engine/`'s `GameRNG`."""

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
