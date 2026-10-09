"""Block attempts: the retry-until-decline state machine (Rulebook SS4 Minion Phase).

"If one attempt to block fails, another can be made as often as the
blocking Methuselah wishes" -- only once they decline to make any further
attempts does the window close. A failed (evaded) attempt does not lock the
vampire that tried it.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine.action import attempt_block


def test_failed_attempt_is_retried_with_another_vampire_then_declined():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1)
    p2.ready_vampire("B2", capacity=3, blood=1)
    game = builder.build()
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "block_with:B2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    # base_stealth=1 (hunt-level): intercept is hardcoded 0 this milestone,
    # so every attempt fails to connect regardless of which vampire tries.
    blocker = attempt_block(game.state, "P1", "P2", base_stealth=1)

    assert blocker is None
    assert game.vampire("B1").locked is False  # failed attempts never lock
    assert game.vampire("B2").locked is False
    defender.assert_exhausted()


def test_failed_attempt_can_be_retried_with_the_same_vampire():
    """Rulebook SS4: "a minion can attempt to block as often as the blocking
    Methuselah wishes" -- the more literal reading permits retrying with the
    *same* minion, not only switching to a different one. A failed attempt
    does not set `locked`, so the candidate is still offered next loop."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=1)

    assert blocker is None
    assert game.vampire("B1").locked is False
    defender.assert_exhausted()


def test_successful_attempt_stops_the_retry_loop_immediately():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    # base_stealth=0 (bleed-level): intercept (0) >= stealth (0), succeeds at once.
    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    assert blocker.instance_id == "B1"
    defender.assert_exhausted()


def test_declining_on_the_first_offer_ends_the_window_immediately():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    defender = ScriptedAgent("P2").expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    defender.assert_exhausted()
