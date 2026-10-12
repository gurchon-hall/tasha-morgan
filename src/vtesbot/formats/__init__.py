"""2P-variant allowed-list loading and deck-construction legality (CLAUDE.md
SS5): "legality checks (2P variant), allowed-list loading."
"""

from .allowed_list import AllowedCard, AllowedList, load_allowed_list
from .legality import (
    LegalityViolation,
    ResolvedCryptEntry,
    ResolvedLibraryEntry,
    check_deck_legality,
)

__all__ = [
    "AllowedCard",
    "AllowedList",
    "load_allowed_list",
    "LegalityViolation",
    "ResolvedCryptEntry",
    "ResolvedLibraryEntry",
    "check_deck_legality",
]
