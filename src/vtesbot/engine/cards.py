"""Generic card identity records used by the engine.

The engine only needs enough of a card's identity to run the rules that are
implemented in `engine/` (blood capacity, card type for phase legality,
unique name for contest detection). Card-specific *behaviour* is out of
scope here and lives in `src/vtesbot/cards/` (CLAUDE.md SS5, SS6): the engine
must never special-case a card name.
"""

import re
from dataclasses import dataclass
from enum import StrEnum

from .errors import UnresolvedRulingError


class Sect(StrEnum):
    """A vampire's sect.

    Source (re-fetched live 2026-10-10, both pages' `dateModified` matching
    the local cache under `data/sources/rulebook/2026-10-09/`): Rulebook SS6
    "Vampire Sects" <https://www.vekn.net/rulebook/6-vampire-sects>, verbatim:
    "A vampire always belongs to one and only one sect." That page defines
    Camarilla, Anarch, Sabbat and Independent. The fifth sect, Laibon, is
    documented separately under Rulebook SS7 "Legacy Sets" > "Other Vampire
    Sects" > "Laibon" <https://www.vekn.net/rulebook/7-legacy-sets> (its own
    cards predate 5th Edition, hence the "legacy" placement -- the page is
    explicit it is just as much a sect as the other four: "Only Laibon can
    hold the laibon titles kholo and magaji."). These five are the only sect
    values defined anywhere in the current Rulebook; no other value is
    valid.
    """

    CAMARILLA = "Camarilla"
    ANARCH = "Anarch"
    SABBAT = "Sabbat"
    INDEPENDENT = "Independent"
    LAIBON = "Laibon"


_SECT_PREAMBLE_RE = re.compile(r"^(?:Advanced,\s*)?(Camarilla|Anarch|Sabbat|Independent|Laibon)\b")


def derive_sect(card_text: str) -> Sect:
    """Derive a vampire's sect from its own printed `card_text`.

    krcg exposes no structured sect field (checked both the installed
    package's `Card.to_json()` and the live API's structured requirement
    fields -- neither has a `sect`/`sect_requirement` key, `docs/
    OPEN_QUESTIONS.md` OQ-18 Gap 1). Sect is only ever embedded as free text
    at the very start of a vampire's own printed text, e.g. `"Camarilla."`
    (Jeremy MacNeil), `"Anarch."` (Aluc Romas de Leon, Anita Wainwright),
    `"Anarch: Ariane gets -1 stealth..."` (Ariane), `"Anarch Baron of
    Miami: ..."`, `"Sabbat Archbishop of Rome: ..."`, `"Laibon magaji: ..."`,
    or (for "Advanced" vampire printings) `"Advanced, Camarilla: ..."` /
    `"Advanced, Sabbat. Red List: ..."`.

    Reliability (checked 2026-10-10 against every crypt card in the
    installed krcg 5.14 dataset, `krcg.load()`, excluding Imbued -- see
    below): all 1765 vampire printings' `card_text` start with exactly one
    of the five sect keywords (optionally preceded by `"Advanced, "` for an
    advanced printing), with a trailing title/qualifier phrase (clan
    justicar/Inner Circle, "primogen", "Prince of <city>", "Archbishop of
    <city>", "bishop", "priscus", "cardinal", "regent", "Baron of <city>",
    "magaji", "kholo", ...) before the terminating "." or ":". The match was
    100% on that sample: in practice there is currently no vampire whose
    text omits the sect preamble (contrary to what might be assumed from the
    Rulebook's "Independent" wording alone -- Independent vampires are not
    left bare, their printed text literally starts with the word
    "Independent."). No manual override table was needed for this sample.
    This function still refuses to guess rather than default silently: if a
    future card's text does not match this convention (e.g. a new printing
    with a malformed or omitted preamble), it raises `UnresolvedRulingError`
    instead of defaulting to Independent, so the gap gets a human decision
    and an OPEN_QUESTIONS.md entry instead of a silently wrong sect.

    Imbued caveat: Imbued are not vampires and have no sect at all (Rulebook
    SS6 only speaks of vampires; Imbued card text never carries a sect
    preamble -- sampled 8 Imbued printings, e.g. Jack "Hannibal137" Harmon,
    none start with one of the five keywords). Callers must only invoke this
    function for genuine vampire crypt cards; calling it on an Imbued's text
    will correctly raise `UnresolvedRulingError` rather than misreporting
    "Independent" (Imbued have no `sect` at all, not the Independent sect).
    """
    match = _SECT_PREAMBLE_RE.match(card_text)
    if match is None:
        raise UnresolvedRulingError(
            "OQ-18",
            f"card text does not start with a recognised sect preamble: {card_text[:60]!r}",
        )
    return Sect(match.group(1))


@dataclass(frozen=True)
class CryptCard:
    """A vampire printing (deck-construction identity only).

    `name` is the card's unique name (Rulebook SS1: vampire names are unique);
    it is used by the engine to detect a 2P "contested" duplicate (2P variant,
    contested crypt cards) between two separately-built decks.

    `clan`, `title`, `disciplines` and `sect` are plain printed stats (same
    status as `capacity`/`group`), not behaviour: a vampire's printed
    special-ability *text* (e.g. Kevin Jackson's clan-conditional combat
    bonus, Alexa Draper's polling-step ability) is card-specific behaviour
    and lives in `src/vtesbot/cards/` like any other card hook (CLAUDE.md
    SS5/SS6) -- this dataclass only carries the identity data every such
    hook, and the generic engine (title -> vote value, discipline-level
    gating, "Requires a/an <Sect>" playability gating), needs to be able to
    read. `disciplines` uses krcg's own basic/superior convention (lowercase
    code = basic level, uppercase code = superior level, e.g. `("for",
    "pot", "DOM", "PRE")`), matching the bracket notation (`[dom]`/`[DOM]`)
    printed on library action-modifier cards.

    `sect` defaults to `None` (sect not modeled for this instance: a
    synthetic test vampire, an Imbued, or a real vampire not yet run through
    `derive_sect`), not to any particular `Sect` member -- a card gating on
    sect must treat `None` as "does not qualify," never guess a default
    sect (CLAUDE.md "no guessing"). Milestone 1's deck-import pipeline does
    not exist yet (`docs/OPEN_QUESTIONS.md` OQ-18 Gap 1), so there is
    currently no end-to-end path populating this field from real krcg data;
    `derive_sect` is the ready-made, tested unit that pipeline will call
    once it exists.
    """

    krcg_id: int
    name: str
    capacity: int
    group: int
    clan: str | None = None
    title: str | None = None
    disciplines: tuple[str, ...] = ()
    sect: Sect | None = None


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
