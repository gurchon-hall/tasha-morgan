"""Generic card identity records used by the engine.

The engine only needs enough of a card's identity to run the rules that are
implemented in `engine/` (blood capacity, card type for phase legality,
unique name for contest detection). Card-specific *behaviour* is out of
scope here and lives in `src/vtesbot/cards/` (CLAUDE.md SS5, SS6): the engine
must never special-case a card name.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CryptCard:
    """A vampire printing (deck-construction identity only).

    `name` is the card's unique name (Rulebook SS1: vampire names are unique);
    it is used by the engine to detect a 2P "contested" duplicate (2P variant,
    contested crypt cards) between two separately-built decks.
    """

    krcg_id: int
    name: str
    capacity: int
    group: int


@dataclass(frozen=True)
class LibraryCard:
    """A library card printing (deck-construction identity only)."""

    krcg_id: int
    name: str
    card_type: str
