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


@dataclass(frozen=True)
class LibraryCard:
    """A library card printing (deck-construction identity only)."""

    krcg_id: int
    name: str
    card_type: str


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
