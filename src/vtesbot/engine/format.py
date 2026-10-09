"""Format configuration: gates the 2P-variant deltas from the rulebook.

CLAUDE.md SS7 "Two-player deltas ... are implemented in the engine, gated by
the format config." This milestone only targets the 2P variant (CLAUDE.md
SS1 Scope), so `FormatConfig.two_player` defaults to True, but every 2P-only
rule in the engine still reads this flag rather than being unconditional.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FormatConfig:
    two_player: bool = True
    hand_size: int = 7
    """Rulebook SS2 Cards in General: default hand size is 7."""
