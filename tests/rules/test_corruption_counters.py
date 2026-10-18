"""`VampireInPlay.corruption_counters` / `engine/corruption.py` (generic
corruption-counter primitive, built during an Aniel 201666 fix): counters
live on the minion itself, keyed by the placing Methuselah's `player_id`
(Sergio Bueno, krcg 201662: "...YOUR corruption counters..."), not on any
`CardAttachment`. `burn_corruption_counters` mirrors `engine/damage.py::
add_blood`/`engine/allies.py::add_life`'s own capped-helper shape, floored at
zero instead of capped at a maximum.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism* via `engine/corruption.py` directly, not through any one card.
"""

from helpers import ScenarioBuilder
from vtesbot.engine.corruption import (
    add_corruption_counters,
    burn_corruption_counters,
    total_corruption_counters,
)


def _fresh_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("W1", capacity=3)
    game = builder.build()
    return game.vampire("W1")


def test_add_corruption_counters_places_them_keyed_by_placer():
    vampire = _fresh_vampire()

    added = add_corruption_counters(vampire, "P1", 2)

    assert added == 2
    assert vampire.corruption_counters == {"P1": 2}


def test_add_corruption_counters_accumulates_for_the_same_placer():
    vampire = _fresh_vampire()
    add_corruption_counters(vampire, "P1", 1)

    add_corruption_counters(vampire, "P1", 2)

    assert vampire.corruption_counters == {"P1": 3}


def test_add_corruption_counters_tracks_different_placers_independently():
    vampire = _fresh_vampire()

    add_corruption_counters(vampire, "P1", 1)
    add_corruption_counters(vampire, "P2", 3)

    assert vampire.corruption_counters == {"P1": 1, "P2": 3}


def test_add_corruption_counters_ignores_a_non_positive_amount():
    vampire = _fresh_vampire()

    added = add_corruption_counters(vampire, "P1", 0)

    assert added == 0
    assert vampire.corruption_counters == {}


def test_burn_corruption_counters_decrements_the_named_placers_stash():
    vampire = _fresh_vampire()
    add_corruption_counters(vampire, "P1", 3)

    burned = burn_corruption_counters(vampire, "P1", 1)

    assert burned == 1
    assert vampire.corruption_counters == {"P1": 2}


def test_burn_corruption_counters_caps_at_what_is_actually_present():
    vampire = _fresh_vampire()
    add_corruption_counters(vampire, "P1", 2)

    burned = burn_corruption_counters(vampire, "P1", 5)

    assert burned == 2  # capped at the 2 actually present, not the full requested 5
    assert vampire.corruption_counters == {}


def test_burn_corruption_counters_removes_the_placer_entry_once_it_hits_zero():
    vampire = _fresh_vampire()
    add_corruption_counters(vampire, "P1", 1)

    burn_corruption_counters(vampire, "P1", 1)

    assert "P1" not in vampire.corruption_counters


def test_burn_corruption_counters_does_not_touch_a_different_placers_stash():
    vampire = _fresh_vampire()
    add_corruption_counters(vampire, "P1", 1)
    add_corruption_counters(vampire, "P2", 1)

    burn_corruption_counters(vampire, "P1", 1)

    assert vampire.corruption_counters == {"P2": 1}


def test_burn_corruption_counters_is_a_no_op_with_nothing_present():
    vampire = _fresh_vampire()

    burned = burn_corruption_counters(vampire, "P1", 1)

    assert burned == 0
    assert vampire.corruption_counters == {}


def test_burn_corruption_counters_ignores_a_non_positive_amount():
    vampire = _fresh_vampire()
    add_corruption_counters(vampire, "P1", 1)

    burned = burn_corruption_counters(vampire, "P1", 0)

    assert burned == 0
    assert vampire.corruption_counters == {"P1": 1}


def test_total_corruption_counters_sums_across_every_placer():
    vampire = _fresh_vampire()
    add_corruption_counters(vampire, "P1", 1)
    add_corruption_counters(vampire, "P2", 2)

    assert total_corruption_counters(vampire) == 3


def test_total_corruption_counters_is_zero_with_none_placed():
    vampire = _fresh_vampire()

    assert total_corruption_counters(vampire) == 0
