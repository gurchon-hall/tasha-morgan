"""Deck legality verdict + expansion to a `DeckSpec`. Ties
`formats.check_deck_legality` to a live krcg lookup for per-card identity
data, yielding either a usable `DeckSpec` or a reported violation set."""

import krcg
from krcg import utils as krcg_utils

from vtesbot.cards import registry
from vtesbot.engine.cards import CryptCard, LibraryCard, derive_sect
from vtesbot.engine.setup import DeckSpec
from vtesbot.formats import (
    AllowedList,
    LegalityViolation,
    ResolvedCryptEntry,
    ResolvedLibraryEntry,
    check_deck_legality,
)

from .resolver import ResolvedDecklist, UnresolvedName


class NotYetPlayableCard:
    def __init__(
        self, krcg_id: int, name: str, status: str, blocked_reason: str | None = None
    ) -> None:
        self.krcg_id = krcg_id
        self.name = name
        self.status = status
        self.blocked_reason = blocked_reason


class DeckImportResult:
    def __init__(
        self,
        name: str | None,
        crypt_count: int,
        groups: list[int],
        library_count: int,
        violations: list[LegalityViolation],
        not_yet_playable: list[NotYetPlayableCard],
        deck_spec: DeckSpec | None,
    ) -> None:
        self.name = name
        self.crypt_count = crypt_count
        self.groups = groups
        self.library_count = library_count
        self.violations = violations
        self.not_yet_playable = not_yet_playable
        self.deck_spec = deck_spec

    @property
    def legal(self) -> bool:
        return not self.violations


def _unresolved_as_violation(unresolved: UnresolvedName) -> LegalityViolation:
    where = f"line {unresolved.line_no}" if unresolved.line_no else "deck fixture"
    return LegalityViolation(
        "deck-validation skill (name resolution)",
        f"Unresolved name on decklist ({where}): {unresolved.name!r}",
    )


def _not_yet_playable(krcg_id: int, name: str) -> NotYetPlayableCard | None:
    reg = registry.get(krcg_id)
    if reg is None:
        return NotYetPlayableCard(krcg_id, name, "not_implemented")
    if reg.status is registry.Status.BLOCKED:
        return NotYetPlayableCard(krcg_id, name, "blocked", reg.blocked_reason)
    return None


def _build_crypt_card(krcg_id: int, count: int, cards: krcg.CardDict) -> list[CryptCard]:
    card = cards[krcg_id]
    name = krcg_utils.vekn_name(card, ascii=False)
    if card.unicity_suffix:
        name = name.removesuffix(f" ({card.unicity_suffix})")
    is_vampire = "Vampire" in [t.value for t in card.types]
    sect = derive_sect(card.text) if is_vampire else None
    built = CryptCard(
        krcg_id=krcg_id,
        name=name,
        capacity=card.capacity,
        group=int(card.group.lstrip("Gg")),
        clan=card.clan,
        # krcg reports `title` as an enum member; `CryptCard.title` wants a
        # plain `str | None`, so unwrap `.value` here.
        title=card.title.value if card.title else None,
        disciplines=tuple(card.disciplines),
        sect=sect,
    )
    return [built] * count


def _build_library_card(krcg_id: int, count: int, cards: krcg.CardDict) -> list[LibraryCard]:
    card = cards[krcg_id]
    name = krcg_utils.vekn_name(card, ascii=False)
    # `LibraryCard.card_type` is a single string; every library card in the
    # active 2P pool prints exactly one krcg type (checked 2026-10-12), so
    # the first (only) one is used.
    card_type = card.types[0].value
    built = LibraryCard(krcg_id=krcg_id, name=name, card_type=card_type)
    return [built] * count


def _expand_deck_spec(resolved: ResolvedDecklist, cards: krcg.CardDict) -> DeckSpec:
    crypt: list[CryptCard] = []
    for entry in resolved.crypt:
        crypt.extend(_build_crypt_card(entry.krcg_id, entry.count, cards))

    library: list[LibraryCard] = []
    for entry in resolved.library:
        library.extend(_build_library_card(entry.krcg_id, entry.count, cards))

    return DeckSpec(crypt=crypt, library=library)


def check_and_build(
    resolved: ResolvedDecklist,
    allowed: AllowedList,
    cards: krcg.CardDict,
    *,
    name: str | None = None,
) -> DeckImportResult:
    violations = check_deck_legality(resolved.crypt, resolved.library, allowed)
    violations = violations + [_unresolved_as_violation(u) for u in resolved.unresolved]

    not_yet_playable: list[NotYetPlayableCard] = []
    for entry in (*resolved.crypt, *resolved.library):
        npy = _not_yet_playable(entry.krcg_id, entry.name)
        if npy is not None:
            not_yet_playable.append(npy)

    deck_spec = _expand_deck_spec(resolved, cards) if not violations else None

    return DeckImportResult(
        name=name,
        crypt_count=sum(e.count for e in resolved.crypt),
        groups=sorted({e.group for e in resolved.crypt}),
        library_count=sum(e.count for e in resolved.library),
        violations=violations,
        not_yet_playable=not_yet_playable,
        deck_spec=deck_spec,
    )


def load_resolved_fixture(fixture: dict) -> ResolvedDecklist:
    """Adapts a curated, krcg-id-resolved `data/decks/vekn-2p/*.json` fixture
    into a `ResolvedDecklist`, so it can drive `check_and_build` directly
    without the plain-text parser/resolver."""
    crypt = [
        ResolvedCryptEntry(krcg_id=c["krcg_id"], name=c["name"], count=c["count"], group=c["group"])
        for c in fixture["crypt"]
    ]
    library = [
        ResolvedLibraryEntry(krcg_id=c["krcg_id"], name=c["name"], count=c["count"])
        for c in fixture["library"]
    ]
    unresolved = [
        UnresolvedName(
            line_no=0,
            name=u["name"],
            section="crypt" if u.get("type") == "Crypt" else "library",
            suggested_krcg_id=u.get("suggested_krcg_id"),
            suggested_name=u.get("suggested_name"),
            candidates=u.get("candidates"),
        )
        for u in fixture.get("unmatched", [])
    ]
    return ResolvedDecklist(crypt=crypt, library=library, unresolved=unresolved)
