"""The game's single seeded source of randomness (CLAUDE.md engine
invariant). Nothing under `engine/` may call `random` directly; every
shuffle/cut/draw goes through `GameRNG`, deterministic and logged."""

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
        """Cut `items` at a random point (2P variant §3 "predator cuts").
        A cut of an already-random shuffle adds no strategic information,
        so this is a procedural RNG draw, not a player `Decision`."""
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
