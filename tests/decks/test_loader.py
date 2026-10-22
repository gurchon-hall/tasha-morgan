"""End-to-end deck import: parse -> resolve -> legality -> `DeckSpec`
(`vtesbot.decks.loader`).

Closes ENG-012 Gap 1's own long-standing gap ("no
path, even a manual one, by which a real vampire's sect would reach a
`CryptCard` instance") -- `test_legal_deck_expands_to_a_deck_spec_with_sect`
below is the first production-code path that actually exercises it.
"""

import json
from pathlib import Path

import krcg
import pytest

from vtesbot.decks import check_and_build, load_resolved_fixture, parse_decklist, resolve_decklist
from vtesbot.decks.resolver import ResolvedDecklist
from vtesbot.engine.cards import DisciplineRequirement, DisciplineRequirementType, Sect
from vtesbot.formats import (
    AllowedCard,
    AllowedList,
    ResolvedCryptEntry,
    ResolvedLibraryEntry,
    load_allowed_list,
)

ALEXA_DRAPER_ID = 201529
BONDING_ID = 100236
SLAM_ID = 101798
LINE_BRAWL_ID = 102229
PARITY_SHIFT_ID = 101353


@pytest.fixture(scope="module")
def cards() -> krcg.CardDict:
    return krcg.load()


@pytest.fixture(scope="module")
def tiny_allowed_list() -> AllowedList:
    entries = [
        AllowedCard(krcg_id=ALEXA_DRAPER_ID, name="Alexa Draper", type="Crypt"),
        AllowedCard(krcg_id=BONDING_ID, name="Bonding", type="Library"),
    ]
    return AllowedList(
        vekn_last_updated="test", source="test", by_krcg_id={c.krcg_id: c for c in entries}
    )


def test_legal_deck_expands_to_a_deck_spec_with_sect(cards, tiny_allowed_list):
    text = "Crypt\n12x Alexa Draper\n\nLibrary\n40x Bonding\n"
    parsed = parse_decklist(text)
    resolved = resolve_decklist(parsed, cards)
    assert resolved.unresolved == []

    result = check_and_build(resolved, tiny_allowed_list, cards, name="tiny legal deck")

    assert result.legal
    assert result.violations == []
    assert result.deck_spec is not None
    assert len(result.deck_spec.crypt) == 12
    assert len(result.deck_spec.library) == 40

    vampire = result.deck_spec.crypt[0]
    assert vampire.krcg_id == ALEXA_DRAPER_ID
    assert vampire.clan == "Ventrue"
    assert vampire.title == "Prince"
    assert vampire.sect is Sect.CAMARILLA

    library_card = result.deck_spec.library[0]
    assert library_card.krcg_id == BONDING_ID
    assert library_card.card_type == "Action Modifier"
    # Bonding's own superior [DOM] clause (`cards/bonding.py`): krcg's
    # `discipline_requirement` is level-agnostic (see `engine/cards.py`'s
    # `DisciplineRequirement` docstring), so this is "dom" regardless of
    # basic/superior, Mono (a single discipline).
    assert library_card.discipline_requirement == DisciplineRequirement(
        type=DisciplineRequirementType.MONO, disciplines=("dom",)
    )


def test_library_card_discipline_requirement_round_trips_from_krcg(cards):
    """Mono (Slam, `[pot]`/`[POT]`), Choice (Line Brawl, `[cel]`/`[pot]`/
    `[pre]`) and no-requirement (Parity Shift, a Political Action) shapes,
    straight from the installed krcg package -- see `decks/loader.py::
    _build_library_card` and `engine/cards.py::DisciplineRequirement`."""
    allowed = AllowedList(
        vekn_last_updated="test",
        source="test",
        by_krcg_id={
            c.krcg_id: c
            for c in (
                AllowedCard(krcg_id=ALEXA_DRAPER_ID, name="Alexa Draper", type="Crypt"),
                AllowedCard(krcg_id=BONDING_ID, name="Bonding", type="Library"),
                AllowedCard(krcg_id=SLAM_ID, name="Slam", type="Library"),
                AllowedCard(krcg_id=LINE_BRAWL_ID, name="Line Brawl", type="Library"),
                AllowedCard(krcg_id=PARITY_SHIFT_ID, name="Parity Shift", type="Library"),
            )
        },
    )
    resolved = ResolvedDecklist(
        crypt=[ResolvedCryptEntry(krcg_id=ALEXA_DRAPER_ID, name="Alexa Draper", count=12, group=6)],
        library=[
            ResolvedLibraryEntry(krcg_id=SLAM_ID, name="Slam", count=1),
            ResolvedLibraryEntry(krcg_id=LINE_BRAWL_ID, name="Line Brawl", count=1),
            ResolvedLibraryEntry(krcg_id=PARITY_SHIFT_ID, name="Parity Shift", count=1),
            ResolvedLibraryEntry(krcg_id=BONDING_ID, name="Bonding", count=37),
        ],
        unresolved=[],
    )

    result = check_and_build(resolved, allowed, cards, name="discipline requirement shapes")

    assert result.legal, result.violations
    assert result.deck_spec is not None
    by_id = {c.krcg_id: c for c in result.deck_spec.library}

    assert by_id[SLAM_ID].discipline_requirement == DisciplineRequirement(
        type=DisciplineRequirementType.MONO, disciplines=("pot",)
    )
    assert by_id[LINE_BRAWL_ID].discipline_requirement == DisciplineRequirement(
        type=DisciplineRequirementType.CHOICE, disciplines=("cel", "pot", "pre")
    )
    assert by_id[PARITY_SHIFT_ID].discipline_requirement == DisciplineRequirement(
        type=DisciplineRequirementType.MONO, disciplines=()
    )


def test_illegal_crypt_groups_blocks_deck_spec_construction(cards):
    allowed = AllowedList(
        vekn_last_updated="test",
        source="test",
        by_krcg_id={
            1: AllowedCard(krcg_id=1, name="Low Group", type="Crypt"),
            2: AllowedCard(krcg_id=2, name="High Group", type="Crypt"),
            100: AllowedCard(krcg_id=100, name="Some Library Card", type="Library"),
        },
    )
    from vtesbot.decks.resolver import ResolvedDecklist

    resolved = ResolvedDecklist(
        crypt=[
            ResolvedCryptEntry(krcg_id=1, name="Low Group", count=6, group=1),
            ResolvedCryptEntry(krcg_id=2, name="High Group", count=6, group=8),
        ],
        library=[ResolvedLibraryEntry(krcg_id=100, name="Some Library Card", count=40)],
        unresolved=[],
    )

    result = check_and_build(resolved, allowed, cards, name="illegal deck")

    assert not result.legal
    assert result.deck_spec is None
    assert any("not one group or two consecutive" in v.detail for v in result.violations)


def test_unmatched_name_is_reported_not_guessed(cards, tiny_allowed_list):
    text = "Crypt\n12x Alexa Draper\n\nLibrary\n39x Bonding\n1x Totally Made Up Card Name\n"
    parsed = parse_decklist(text)
    resolved = resolve_decklist(parsed, cards)

    assert len(resolved.unresolved) == 1
    assert resolved.unresolved[0].name == "Totally Made Up Card Name"

    result = check_and_build(resolved, tiny_allowed_list, cards, name="unmatched name deck")

    assert not result.legal
    assert result.deck_spec is None
    assert any(
        "Unresolved name" in v.detail and "Totally Made Up Card Name" in v.detail
        for v in result.violations
    )


def test_real_ventrue_suggested_decklist_is_legal(cards):
    repo_root = Path(__file__).resolve().parents[2]
    allowed = load_allowed_list(repo_root / "data" / "formats" / "2p" / "2026-10-03.json")
    fixture = json.loads(
        (repo_root / "data" / "decks" / "vekn-2p" / "ventrue.json").read_text(encoding="utf-8")
    )

    resolved = load_resolved_fixture(fixture)
    result = check_and_build(resolved, allowed, cards, name=fixture["name"])

    assert result.legal, result.violations
    assert result.deck_spec is not None

    lucinde = next(c for c in result.deck_spec.crypt if c.krcg_id == 201700)
    assert lucinde.clan == "Ventrue"
    assert lucinde.title == "Justicar"
    assert lucinde.sect is Sect.CAMARILLA
    assert lucinde.group == 7
