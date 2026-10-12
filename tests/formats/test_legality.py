"""2P deck-construction legality checks (`vtesbot.formats.legality`).

Uses a small synthetic `AllowedList` rather than the real dated
`data/formats/2p/*.json` file, so these checks stay independent of future
VEKN updates (CLAUDE.md SS4: the format is a living playtest).
"""

from vtesbot.formats import (
    AllowedCard,
    AllowedList,
    ResolvedCryptEntry,
    ResolvedLibraryEntry,
    check_deck_legality,
)


def _allowed() -> AllowedList:
    cards = [
        AllowedCard(krcg_id=1, name="Vampire One", type="Crypt"),
        AllowedCard(krcg_id=2, name="Vampire Two", type="Crypt"),
        AllowedCard(krcg_id=3, name="Vampire Three", type="Crypt"),
        AllowedCard(krcg_id=100, name="Some Master Card", type="Library"),
        AllowedCard(krcg_id=101, name="Some Action Card", type="Library"),
    ]
    return AllowedList(
        vekn_last_updated="2026-01-01", source="test", by_krcg_id={c.krcg_id: c for c in cards}
    )


def _legal_crypt(count_per: int = 4) -> list[ResolvedCryptEntry]:
    return [
        ResolvedCryptEntry(krcg_id=1, name="Vampire One", count=count_per, group=5),
        ResolvedCryptEntry(krcg_id=2, name="Vampire Two", count=count_per, group=5),
        ResolvedCryptEntry(krcg_id=3, name="Vampire Three", count=count_per, group=5),
    ]


def _legal_library(count_per: int = 20) -> list[ResolvedLibraryEntry]:
    return [
        ResolvedLibraryEntry(krcg_id=100, name="Some Master Card", count=count_per),
        ResolvedLibraryEntry(krcg_id=101, name="Some Action Card", count=count_per),
    ]


def test_legal_deck_has_no_violations():
    violations = check_deck_legality(_legal_crypt(), _legal_library(), _allowed())
    assert violations == []


def test_crypt_below_minimum_size_is_a_violation():
    crypt = [ResolvedCryptEntry(krcg_id=1, name="Vampire One", count=11, group=5)]
    violations = check_deck_legality(crypt, _legal_library(), _allowed())
    assert any("Crypt size 11" in v.detail for v in violations)
    assert any(v.rule == "Rulebook §1 Deck construction" for v in violations)


def test_crypt_groups_must_be_one_or_two_consecutive():
    crypt = [
        ResolvedCryptEntry(krcg_id=1, name="Vampire One", count=6, group=5),
        ResolvedCryptEntry(krcg_id=2, name="Vampire Two", count=6, group=7),
    ]
    violations = check_deck_legality(crypt, _legal_library(), _allowed())
    assert any("not one group or two consecutive" in v.detail for v in violations)


def test_two_consecutive_crypt_groups_are_legal():
    crypt = [
        ResolvedCryptEntry(krcg_id=1, name="Vampire One", count=6, group=5),
        ResolvedCryptEntry(krcg_id=2, name="Vampire Two", count=6, group=6),
    ]
    violations = check_deck_legality(crypt, _legal_library(), _allowed())
    assert violations == []


def test_library_size_outside_40_60_is_a_violation():
    violations = check_deck_legality(_legal_crypt(), _legal_library(count_per=5), _allowed())
    assert any("Library size 10" in v.detail for v in violations)
    assert any(v.rule == "2P variant §2.3" for v in violations)


def test_card_not_on_allowed_list_is_a_violation():
    crypt = [*_legal_crypt(), ResolvedCryptEntry(krcg_id=999, name="Unknown", count=1, group=5)]
    violations = check_deck_legality(crypt, _legal_library(), _allowed())
    assert any("not on 2P allowed list" in v.detail for v in violations)


def test_crypt_card_listed_as_library_type_is_a_violation():
    # krcg_id 100 is a Library card on the allowed list; putting it in the
    # crypt section must be flagged.
    mislabeled = ResolvedCryptEntry(krcg_id=100, name="Some Master Card", count=1, group=5)
    crypt = [*_legal_crypt(), mislabeled]
    violations = check_deck_legality(crypt, _legal_library(), _allowed())
    assert any("is Library on the allowed list, not Crypt" in v.detail for v in violations)


def test_no_maximum_copy_count_is_enforced():
    crypt = [ResolvedCryptEntry(krcg_id=1, name="Vampire One", count=40, group=5)]
    violations = check_deck_legality(crypt, _legal_library(), _allowed())
    assert not any("maximum" in v.detail.lower() for v in violations)
