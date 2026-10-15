"""Format configuration (CLAUDE.md §7). `two_player` defaults to True
(§1 scope, 4-5 player out of scope for now) -- no code currently reads
this flag, since every 2P-only rule is applied unconditionally rather
than gated by it (`docs/DECISIONS.md` D-11, an accepted simplification,
not an oversight)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FormatConfig:
    two_player: bool = True
    hand_size: int = 7
    """Rulebook §2 Cards in General: default hand size is 7."""
