"""Generic card identity records: just enough for engine rules (capacity, card type,
unique name). Card-specific behaviour lives in `src/vtesbot/cards/` (CLAUDE.md §5/§6)."""

import re
from dataclasses import dataclass
from enum import StrEnum

from .errors import UnresolvedRulingError


class Sect(StrEnum):
    """A vampire's sect (Rulebook §6 Vampire Sects: Camarilla/Anarch/Sabbat/Independent;
    Laibon is §7 Legacy Sets' fifth). The only five valid values."""

    CAMARILLA = "Camarilla"
    ANARCH = "Anarch"
    SABBAT = "Sabbat"
    INDEPENDENT = "Independent"
    LAIBON = "Laibon"


_SECT_PREAMBLE_RE = re.compile(r"^(?:Advanced,\s*)?(Camarilla|Anarch|Sabbat|Independent|Laibon)\b")


def derive_sect(card_text: str) -> Sect:
    """Derive sect from the keyword starting `card_text` (krcg has no structured field,
    OQ-18 Gap 1). Raises `UnresolvedRulingError` on a non-matching or Imbued text."""
    match = _SECT_PREAMBLE_RE.match(card_text)
    if match is None:
        raise UnresolvedRulingError(
            "OQ-18",
            f"card text does not start with a recognised sect preamble: {card_text[:60]!r}",
        )
    return Sect(match.group(1))


@dataclass(frozen=True)
class CryptCard:
    """A vampire printing (deck-construction identity). `name` is unique (§1), used for
    2P contested-crypt detection. Printed stats, not behaviour. `sect` defaults `None`
    (OQ-18) until `derive_sect` runs."""

    krcg_id: int
    name: str
    capacity: int
    group: int
    clan: str | None = None
    title: str | None = None
    disciplines: tuple[str, ...] = ()
    sect: Sect | None = None


class DisciplineRequirementType(StrEnum):
    """How a library card's printed discipline symbols combine (krcg's own
    `krcg.models.DisciplineRequirement.Type`, mirrored verbatim, values
    confirmed live via `krcg.load()`, 2026-10-15): Mono = a single
    discipline, printed at basic and/or superior level (e.g. Slam's `[pot]`/
    `[POT]`); Choice = any one of several, each basic-only on every 2P-pool
    card checked (e.g. Line Brawl's `[cel]`/`[pot]`/`[pre]`); Combo =
    several required together, each independently basic/superior (e.g.
    Forced March's `[cel][for]`/`[CEL][FOR]`)."""

    MONO = "Mono"
    CHOICE = "Choice"
    COMBO = "Combo"


@dataclass(frozen=True)
class DisciplineRequirement:
    """A library card's printed discipline requirement (krcg's own
    `Card.discipline_requirement`, `krcg.models.DisciplineRequirement`;
    confirmed live via `krcg.load()`, 2026-10-15, across Mono/Choice/Combo
    cards and no-discipline cards, e.g. Political Actions and most Masters:
    every library card carries one, never `None` -- a card with no
    discipline symbol at all gets `type=Mono, disciplines=()`).

    `disciplines` is a tuple of lowercase trigrams (`"dom"`, not `"DOM"`):
    krcg's own field is level-agnostic by design (its field docstring:
    "library requirements are level-agnostic: lowercase trigrams"), because
    which level (basic/bold-superior, Rulebook §3 "Discipline symbol within
    a diamond ... may opt to use either the basic (plain text) or the
    superior (bold) effect") a play uses is a property of *how the card is
    played*, not of what it structurally requires while sitting in hand,
    library or ash heap. That in-hand/library/ash-heap collapse is itself
    an explicit ruling, not an engine assumption: "When played, a
    multi-Disciplines card counts as requiring the Discipline(s) being
    used. In the hand, library, or ash heap, the card is considered to
    require any and/or all Disciplines listed on it." [LSJ 20011204-3]
    [PIB 20130704]. No card in the active 2P pool was found printing a
    superior-only clause with no matching basic clause (checked 2026-10-15
    across the full krcg library-card set), so this has not been observed
    to lose information for any card currently in scope; if such a card is
    ever added, this field would still (correctly, per the ruling above)
    list its trigram here regardless."""

    type: DisciplineRequirementType = DisciplineRequirementType.MONO
    disciplines: tuple[str, ...] = ()


def requires_discipline(requirement: DisciplineRequirement, discipline: str) -> bool:
    """Whether a library card's discipline requirement includes `discipline`
    (a trigram, case-insensitive -- callers may pass a printed bracket
    token like `"DOM"`). True regardless of `requirement.type` (Mono/
    Choice/Combo): the in-hand/library/ash-heap collapsing ruling cited on
    `DisciplineRequirement` above draws no type distinction -- a card is
    considered to require any/all of its listed disciplines whenever it is
    not the one actually being played."""
    return discipline.lower() in requirement.disciplines


@dataclass(frozen=True)
class LibraryCard:
    """A library card printing (deck-construction identity only)."""

    krcg_id: int
    name: str
    card_type: str
    discipline_requirement: DisciplineRequirement = DisciplineRequirement()


@dataclass
class CardAttachment:
    """A card attached to a vampire (§5, e.g. Celerity, Fame). Tracks attachment and
    controller only; behaviour lives in `cards/`. Not frozen: `zone` mutates (OQ-22);
    `controller` from `attach_card` (§2)."""

    krcg_id: int
    name: str
    counters: int | None = None
    controller: str | None = None
    instance_id: str | None = None
    zone: str = "attached"
    contested_with: str | None = None
    is_equipment: bool = False
    """Printed Equipment card type (§2 Card Types: "Equipment cards: ...
    put into play on the acting minion"), set by the attaching card module
    itself at construction time (e.g. `cards/weighted_walking_stick.py`),
    never inferred by the engine. Gates `engine/diablerie.py::
    resolve_diablerie` step 2 ("the diablerist may take any equipment on
    the victim") -- a discipline/archetype master-card attachment (e.g.
    Celerity) or a Unique master card attached to a vampire (e.g. Fame)
    is not equipment and defaults to `False`, correctly excluded from
    that offer."""
