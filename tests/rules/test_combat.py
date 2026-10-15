"""Basic combat: hand strikes only, close range, damage/mend/press (Rulebook §4 Combat).

"Rounds of 7 steps: ... strike (acting minion chooses first; simultaneous
resolution) -> damage resolution (prevent, then mend) -> press (alternating)
-> end of round. Combat ends at once if a combatant is no longer ready."
"Hand strike = strength (default 1), close range only." "1 blood mends 1
damage; unmended -> wounded -> torpor."
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine.combat import run_combat


def test_combat_round_with_mend_and_declined_press():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=2)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("mend_damage", "1")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "hand_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.blood_of("V1") == 1  # mended 1 of the 1 damage taken
    assert game.vampire("V1").wounded is False
    assert game.vampire("B1").wounded is True  # 0 blood: could not mend, now wounded
    assert game.zone_of("V1") == "ready"
    assert game.zone_of("B1") == "ready"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_combat_ends_immediately_when_a_combatant_enters_torpor():
    """A second unmended normal-damage instance on an already-wounded vampire
    sends it to torpor; combat ends at once, with no press step for that
    round (Rulebook §4: "combat ends at once if a combatant is no longer
    ready")."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=2)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0, wounded=True)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.zone_of("B1") == "torpor"
    assert game.zone_of("V1") == "ready"
    actor.assert_exhausted()
    defender.assert_exhausted()  # no press decision was raised for either side


def test_pressing_continues_combat_to_another_round():
    """If either combatant presses and the press stands uncancelled,
    combat continues to another round (Rulebook §4 step 6). The blocking
    player must also get a press/decline turn in round 1 after the actor
    presses -- the bug this test now guards against is the blocking player
    never being asked at all once the actor pressed."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=2)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("mend_damage", "1")
    actor.expect("press", "press")  # round 1, actor's turn: press
    actor.expect("press", "end_combat")  # round 1, actor's turn: decline, closes the window
    actor.expect("strike_choice", "hand_strike")  # round 2
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "hand_strike")
    defender.expect("press", "end_combat")  # round 1, blocking's turn: decline
    defender.expect("strike_choice", "no_strike")  # round 2
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    # Round 2: B1 (already wounded from round 1, 0 blood) takes V1's strike
    # and is sent to torpor; combat ends there (no round-2 press decision).
    assert game.zone_of("B1") == "torpor"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_double_press_cancels_and_ends_combat_after_the_round():
    """Two offsetting presses (one each side) cancel out, matching
    Rulebook §4 step 6's "to keep offsetting the effects of their
    opponent's last press" -- the net uncancelled-press state is False, so
    no further round begins. Also exercises "a minion cannot play two
    presses in a row": the strict acting-then-blocking alternation means
    neither side is ever asked for a second press without the other's turn
    in between."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=2)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=2)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "press")  # round 1, actor's turn: press
    actor.expect("press", "end_combat")  # round 1, actor's turn: decline
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "press")  # round 1, blocking's turn: offsetting press
    defender.expect("press", "end_combat")  # round 1, blocking's turn: decline, closes the window
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    # No round 2 was played: both vampires are untouched and still ready,
    # and both scripted agents consumed every expectation above -- if
    # combat had wrongly continued, the agents would have no scripted
    # answer left for a round-2 strike_choice and would raise.
    assert game.zone_of("V1") == "ready"
    assert game.zone_of("B1") == "ready"
    actor.assert_exhausted()
    defender.assert_exhausted()
