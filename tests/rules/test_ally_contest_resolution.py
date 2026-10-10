"""Ally contest *resolution* (OQ-15, `docs/OPEN_QUESTIONS.md`): once two
allies are flagged as contesting each other (OQ-10,
`engine/allies.py::detect_contest_on_recruit`), each controller must be
offered the rulebook's own pay-1-pool-or-yield decision during their own
unlock phases (Rulebook SS4 Advanced Rules > Contested Cards), mirroring the
crypt-card mechanism already proven by `tests/rules/test_unlock.py`'s own
contest tests -- except an ally has no 2P "stays usable" override, so the
surviving copy's own `zone` only flips back to `"ready"` on its controller's
own *next* unlock phase, not instantaneously with the opponent's yield (see
`engine/allies.py::resolve_one_ally_contest` and
`engine/phases/unlock.py::_unlock_own_allies`).
"""

from helpers import ScenarioBuilder, ScenarioGame, ScriptedAgent
from vtesbot.engine.allies import detect_contest_on_recruit, recruit_ally
from vtesbot.engine.phases.unlock import unlock_phase
from vtesbot.engine.state import AllyInPlay

UNIQUE_ALLY_KRCG_ID = 102217  # 47th Street Royals' own id, reused as a stand-in
UNIQUE_ALLY_NAME = "47th Street Royals"


def _contested_pair(game: ScenarioGame) -> tuple[AllyInPlay, AllyInPlay]:
    """Recruit a same-named ally for each player and flag the contest,
    mirroring `tests/rules/test_ally_contests.py`'s own setup pattern."""
    existing = recruit_ally(
        game.state, "P2", krcg_id=UNIQUE_ALLY_KRCG_ID, name=UNIQUE_ALLY_NAME, life=2
    )
    incoming = recruit_ally(
        game.state, "P1", krcg_id=UNIQUE_ALLY_KRCG_ID, name=UNIQUE_ALLY_NAME, life=2
    )
    detect_contest_on_recruit(game.state, incoming)
    return incoming, existing


def test_contested_allys_controller_is_offered_pay_or_yield_during_unlock():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10)
    builder.player("P2", pool=10)
    game = builder.build()
    _contested_pair(game)
    agent = ScriptedAgent("P1").expect("ally_contest_resolution", "pay")
    game.state.agents["P1"] = agent

    unlock_phase(game.state, "P1")

    assert game.state.players["P1"].pool == 9
    agent.assert_exhausted()


def test_paying_keeps_both_copies_contested_and_out_of_play():
    """Unlike the crypt-card case (2P override keeps `zone == "ready"`
    throughout), an ally has no such override: paying leaves it
    `zone == "contested"`, still out of play."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10)
    builder.player("P2", pool=10)
    game = builder.build()
    mine, opponent = _contested_pair(game)
    game.state.agents["P1"] = ScriptedAgent("P1").expect("ally_contest_resolution", "pay")

    unlock_phase(game.state, "P1")

    assert mine.zone == "contested"
    assert mine.contested_with == opponent.instance_id
    assert opponent.zone == "contested"
    assert opponent.contested_with == mine.instance_id


def test_yielding_burns_the_yielding_ally_and_does_not_immediately_restore_the_opponent():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10)
    builder.player("P2", pool=10)
    game = builder.build()
    mine, opponent = _contested_pair(game)
    game.state.agents["P1"] = ScriptedAgent("P1").expect("ally_contest_resolution", "yield")

    unlock_phase(game.state, "P1")

    assert mine.zone == "burned"
    assert mine.contested_with is None
    assert game.state.players["P1"].pool == 10  # yielding costs no pool
    # Not instantaneous with the yield: the rulebook's own wording is "...
    # during your next unlock phase, ending the contest" (a further event
    # tied to the surviving controller's own next unlock phase).
    assert opponent.contested_with is None
    assert opponent.zone == "contested"


def test_the_surviving_allys_zone_is_only_restored_on_its_controllers_own_next_unlock_phase():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10)
    builder.player("P2", pool=10)
    game = builder.build()
    mine, opponent = _contested_pair(game)
    game.state.agents["P1"] = ScriptedAgent("P1").expect("ally_contest_resolution", "yield")
    unlock_phase(game.state, "P1")
    assert opponent.zone == "contested"  # not yet restored

    agent_p2 = ScriptedAgent("P2")  # no pending effects expected for P2
    game.state.agents["P2"] = agent_p2

    unlock_phase(game.state, "P2")

    assert opponent.zone == "ready"
    assert opponent.locked is False
    assert opponent.contested_with is None
    agent_p2.assert_exhausted()


def test_zero_regression_an_uncontested_allys_zone_is_left_untouched_by_unlock():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10)
    builder.player("P2", pool=10)
    game = builder.build()
    solo = recruit_ally(game.state, "P1", krcg_id=1, name="Solo Ally", life=1)
    game.state.agents["P1"] = ScriptedAgent("P1")  # no decisions expected

    unlock_phase(game.state, "P1")

    assert solo.zone == "ready"
    assert solo.contested_with is None
