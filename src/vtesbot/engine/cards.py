"""Generic card identity records used by the engine.

The engine only needs enough of a card's identity to run the rules that are
implemented in `engine/` (blood capacity, card type for phase legality,
unique name for contest detection). Card-specific *behaviour* is out of
scope here and lives in `src/vtesbot/cards/` (CLAUDE.md SS5, SS6): the engine
must never special-case a card name.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CryptCard:
    """A vampire printing (deck-construction identity only).

    `name` is the card's unique name (Rulebook SS1: vampire names are unique);
    it is used by the engine to detect a 2P "contested" duplicate (2P variant,
    contested crypt cards) between two separately-built decks.

    `clan`, `title` and `disciplines` are plain printed stats (same status as
    `capacity`/`group`), not behaviour: a vampire's printed special-ability
    *text* (e.g. Kevin Jackson's clan-conditional combat bonus, Alexa
    Draper's polling-step ability) is card-specific behaviour and lives in
    `src/vtesbot/cards/` like any other card hook (CLAUDE.md SS5/SS6) -- this
    dataclass only carries the identity data every such hook, and the
    generic engine (title -> vote value, discipline-level gating), needs to
    be able to read. `disciplines` uses krcg's own basic/superior convention
    (lowercase code = basic level, uppercase code = superior level, e.g.
    `("for", "pot", "DOM", "PRE")`), matching the bracket notation
    (`[dom]`/`[DOM]`) printed on library action-modifier cards.
    """

    krcg_id: int
    name: str
    capacity: int
    group: int
    clan: str | None = None
    title: str | None = None
    disciplines: tuple[str, ...] = ()


@dataclass(frozen=True)
class LibraryCard:
    """A library card printing (deck-construction identity only)."""

    krcg_id: int
    name: str
    card_type: str


@dataclass(frozen=True)
class CardAttachment:
    """A card physically attached to a vampire (CLAUDE.md SS5 "equipment"/
    "retainer" hook category): a discipline/archetype master card (Celerity,
    Fame, Perfectionist), a piece of combat equipment (Weighted Walking
    Stick), or a retainer. The engine only needs to track *that* a card is
    attached and to whom (`VampireInPlay.attachments`, `engine/state.py`) so
    it can be found, destroyed, or referenced by a hook; what the attachment
    *does* is card-specific behaviour registered against a hook by its
    `src/vtesbot/cards/` module, never special-cased here (CLAUDE.md SS6).
    """

    krcg_id: int
    name: str
    counters: int | None = None
