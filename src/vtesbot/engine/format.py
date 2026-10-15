"""Format configuration: gates 2P-variant deltas from the rulebook
(CLAUDE.md §7). `two_player` defaults to True (§1 scope), but every
2P-only rule still reads this flag rather than being unconditional."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FormatConfig:
    two_player: bool = True
    hand_size: int = 7
    """Rulebook §2 Cards in General: default hand size is 7."""
