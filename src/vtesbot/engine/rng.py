"""The game's single seeded source of randomness.

CLAUDE.md engine invariant: "all randomness through a seeded RNG owned by
the game state. Same seed + same decisions => same game." Nothing under
`engine/` may call `random` directly; every shuffle/cut/draw goes through
`GameRNG` so it is both deterministic and recorded in the replay log.
"""

import random

from .log import ReplayLog


class GameRNG:
    """Seeded RNG wrapper that logs every random operation for replay."""

    def __init__(self, seed: int, log: ReplayLog) -> None:
        self._random = random.Random(seed)
        self._log = log
        self.seed = seed

    def shuffle[T](self, items: list[T], description: str) -> None:
        """Shuffle `items` in place (Fisher-Yates via `random.Random.shuffle`)."""
        self._random.shuffle(items)
        self._log.record_random(description, [getattr(i, "name", repr(i)) for i in items])

    def cut[T](self, items: list[T], description: str) -> None:
        """Cut `items` at a random point (move the bottom portion to the top).

        2P variant SS3 Game Setup: "predator cuts" the shuffled deck. With a
        trusted, seeded digital shuffle already providing a uniformly random
        order, a cut of an already-random permutation carries no additional
        strategic information (cutting a uniform random order yields another
        uniform random order) -- the physical-table purpose of the cut
        (preventing deck stacking) is already guaranteed by the RNG. The
        engine therefore performs the cut as a procedural RNG draw rather
        than as a player `Decision`, while still recording it in the replay
        log so the step is not silently skipped.
        """
        if len(items) < 2:
            return
        point = self._random.randint(1, len(items) - 1)
        items[:] = items[point:] + items[:point]
        self._log.record_random(
            f"{description} (cut at {point})", [getattr(i, "name", repr(i)) for i in items]
        )

    def randint(self, a: int, b: int, description: str) -> int:
        value = self._random.randint(a, b)
        self._log.record_random(description, value)
        return value
