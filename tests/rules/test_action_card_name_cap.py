"""Generic "same named action card at most once per turn" cap (ENG-037
Finding 2). Rulebook §4 Detailed Turn Sequence
(`data/sources/rulebook/2026-10-09/4-detailed-turn-sequence.md:188-191`,
verbatim): "A minion cannot play (unless cancelled) the same named action
card more than once each turn, even if they unlock." -- scoped to one
minion (`VampireInPlay.action_card_played_turn`), not every vampire its
controller owns.

Proven here against a real, already-implemented Action card (Dominate
Kine, krcg 100573, `cards/dominate_kine.py`) with two physical copies in
hand, per the `rules-scenario-test` skill's preference for a worked
example over a synthetic fixture when one is readily available."""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards.dominate_kine import KRCG_ID as DOMINATE_KINE_KRCG_ID
from vtesbot.cards.dominate_kine import NAME as DOMINATE_KINE_NAME
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, minion_phase


def _dominate_kine_card() -> LibraryCard:
    return LibraryCard(krcg_id=DOMINATE_KINE_KRCG_ID, name=DOMINATE_KINE_NAME, card_type="action")


def test_second_physical_copy_blocked_this_turn_even_after_unlocking_but_offered_again_next_turn():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=10, disciplines=("dom",)
    )
    p1.hand.append(_dominate_kine_card())
    p1.hand.append(_dominate_kine_card())  # second physical copy.
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with.
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "dominate_kine:basic")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # the first copy resolved normally.
    assert game.vampire("V1").locked is True

    # "even if they unlock": simulate a future unlock-mid-turn effect by
    # flipping the flag directly -- the cap itself is keyed by turn number,
    # not by `locked`, so it must still hold regardless.
    game.vampire("V1").locked = False
    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert "dominate_kine:basic" not in values
    assert "dominate_kine:superior" not in values

    # Next turn: the cap is turn-scoped, so the second copy becomes
    # playable again (still in hand -- never consumed).
    game.state.turn_number += 1
    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert "dominate_kine:basic" in values


def test_a_different_vampire_with_its_own_copy_may_still_play_it_the_same_turn():
    """The cap is per-minion ("a minion cannot play ..."), not per
    controller: a second vampire of the same Methuselah, using its own
    physical copy, is unaffected by the first vampire's own play this
    same turn."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("V1", capacity=5, blood=10, disciplines=("dom",))
    p1.ready_vampire("V2", capacity=5, blood=10, disciplines=("dom",))
    p1.hand.append(_dominate_kine_card())
    p1.hand.append(_dominate_kine_card())
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with.
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "dominate_kine:basic")
    actor.expect("minion_phase_choice", "act_with:V2")
    actor.expect("action_choice", "dominate_kine:basic")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 26  # both copies resolved, one per vampire.
    assert game.vampire("V1").locked is True
    assert game.vampire("V2").locked is True
    actor.assert_exhausted()
