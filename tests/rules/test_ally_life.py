"""`AllyInPlay.starting_life` / `engine/allies.py::add_life` (ENG-041):
recruiting an ally fixes its own printed starting life once, and `add_life`
mirrors `engine/damage.py::add_blood`'s capped shape (e.g. Seraphina, krcg
201686: "...not to exceed starting life.").

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism* via `engine/allies.py` directly, not through any one card."""

from helpers import ScenarioBuilder
from vtesbot.engine.allies import add_life, recruit_ally


def test_recruit_ally_fixes_starting_life_from_its_own_life_argument():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()

    ally = recruit_ally(game.state, "P1", krcg_id=999999, name="Fake Ally", life=4)

    assert ally.life == 4
    assert ally.starting_life == 4


def test_add_life_adds_up_to_the_requested_amount():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    ally = recruit_ally(game.state, "P1", krcg_id=999999, name="Fake Ally", life=4)
    ally.life = 2

    added = add_life(ally, 1)

    assert added == 1
    assert ally.life == 3


def test_add_life_caps_at_starting_life_not_beyond():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    ally = recruit_ally(game.state, "P1", krcg_id=999999, name="Fake Ally", life=4)
    ally.life = 3

    added = add_life(ally, 2)

    assert added == 1  # capped at starting_life (4), not the full requested 2
    assert ally.life == 4


def test_add_life_is_a_no_op_once_already_at_starting_life():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    ally = recruit_ally(game.state, "P1", krcg_id=999999, name="Fake Ally", life=4)

    added = add_life(ally, 2)

    assert added == 0
    assert ally.life == 4


def test_add_life_ignores_a_non_positive_amount():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    ally = recruit_ally(game.state, "P1", krcg_id=999999, name="Fake Ally", life=4)
    ally.life = 1

    added = add_life(ally, 0)

    assert added == 0
    assert ally.life == 1
