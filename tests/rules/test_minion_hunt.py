"""Default hunt action (Rulebook SS4 Minion Phase).

"hunt (undirected, +1 stealth, +1 blood)." "mandatory actions first (a ready
vampire with no blood must hunt)."
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine.phases.minion import minion_phase


def test_vampire_with_no_blood_must_hunt():
    """Mandatory action: resolved before the player chooses anything else."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    # No minion_phase_choice is scripted for the mandatory hunt: it is forced,
    # not chosen. After it resolves, V1 is locked, so the optional loop finds
    # no ready unlocked vampire left and returns without asking anything else.
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.blood_of("V1") == 1
    assert game.vampire("V1").locked is True


def test_hunt_always_evades_a_block_attempt_due_to_its_baseline_stealth():
    """Hunt's baseline stealth (1) always exceeds a blocker's baseline
    intercept (0) when no intercept cards are implemented: the block attempt
    is still offered to the defender (their right to attempt), but it never
    connects, and the blocking vampire does not lock. Rulebook SS4: a failed
    attempt does not end the block-attempt window, so the defender is
    re-offered another attempt or decline; here they decline."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "hunt")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.blood_of("V1") == 2  # hunt resolved despite the block attempt
    assert game.vampire("B1").locked is False  # evaded: blocker does not lock
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_hunt_blood_gain_is_capped_at_capacity():
    """Rulebook SS1 Vampires: a vampire cannot hold more blood than its capacity."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=2, blood=2)
    builder.player("P2", pool=30)
    game = builder.build()
    # V1 already has blood (2) so it is not subject to the mandatory-hunt rule;
    # the player chooses to hunt with it anyway.
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "hunt")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.blood_of("V1") == 2  # capped, not 3
    actor.assert_exhausted()
