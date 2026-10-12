"""Name -> krcg id matching (`vtesbot.decks.name_resolution`).

Same cases `scripts/krcg_match.py` was already relying on before this
logic moved into production code (CLAUDE.md no-guessing rule: only an
*exact* match, folding case/whitespace/accents and the "Name, The" <->
"The Name" convention, is ever auto-resolved).
"""

import krcg
import pytest

from vtesbot.decks.name_resolution import build_indexes, match_crypt, match_library


@pytest.fixture(scope="module")
def cards() -> krcg.CardDict:
    return krcg.load()


@pytest.fixture(scope="module")
def indexes(cards: krcg.CardDict):
    return build_indexes(cards)


def test_unambiguous_library_name_matches(cards, indexes):
    library_index, _ = indexes
    result = match_library(cards, "Bonding", library_index)
    assert result["matched"] is True
    assert result["krcg_name"] == "Bonding"


def test_library_name_is_case_and_whitespace_insensitive(cards, indexes):
    library_index, _ = indexes
    result = match_library(cards, "  bonding  ", library_index)
    assert result["matched"] is True


def test_the_x_convention_resolves_either_way(cards, indexes):
    library_index, _ = indexes
    comma_form = match_library(cards, "Sleeping Mind, The", library_index)
    the_form = match_library(cards, "The Sleeping Mind", library_index)
    assert comma_form["matched"] is True
    assert the_form["matched"] is True
    assert comma_form["krcg_id"] == the_form["krcg_id"]


def test_unknown_library_name_is_unmatched_not_guessed(cards, indexes):
    library_index, _ = indexes
    result = match_library(cards, "Totally Made Up Card Name", library_index)
    assert result["matched"] is False
    assert result["krcg_id"] is None


def test_crypt_name_with_multiple_printings_disambiguated_by_min_group(cards, indexes):
    # "Lucinde, Alastor" prints at G3 (200873) and G7 (201700); the 2P pool
    # only uses group >= 5 reprints (confirmed with the user 2026-10-08).
    _, crypt_by_base = indexes
    result = match_crypt(cards, "Lucinde, Alastor", crypt_by_base, min_group=5)
    assert result["matched"] is True
    assert result["krcg_id"] == 201700


def test_crypt_name_ambiguous_below_min_group_is_unmatched(cards, indexes):
    _, crypt_by_base = indexes
    result = match_crypt(cards, "Lucinde, Alastor", crypt_by_base, min_group=100)
    assert result["matched"] is False
    assert result["candidates"] is not None
    assert {c["krcg_id"] for c in result["candidates"]} == {200873, 201700}


def test_unambiguous_crypt_name_matches_regardless_of_min_group(cards, indexes):
    _, crypt_by_base = indexes
    result = match_crypt(cards, "Alexa Draper", crypt_by_base, min_group=5)
    assert result["matched"] is True
    assert result["krcg_id"] == 201529
