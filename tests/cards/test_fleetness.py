"""Fleetness (krcg id 100747, `src/vtesbot/cards/fleetness.py`).

Card text: "+1 stealth action.\n[cel] Ⓓ Bleed.\n[CEL] Ⓓ Enter combat with a
locked minion. This acting vampire gets 1 optional maneuver during that
combat." Ruling: "[CEL]If the action is unblocked when it resolves and the
target is unlocked, the action "fizzles" (cost, if any, is paid, and it is
considered successful, but has no effect)."

One assertion per clause/qualifier/ruling: the printed 1-blood cost gate (at
offer time, for both clauses) and its "paid only on the unblocked branch"
timing; the basic/superior discipline-level gating (inferior access unlocks
only the basic clause, superior access unlocks both); the basic clause's
plain, default-amount directed bleed with its +1 stealth baseline, tagged
`ACTION_BLEED` so a bleed-gated provider sharing the same window still
fires; the superior clause's "enter combat with a locked minion" (no
eligible target -> not offered; single eligible locked target -> applied
directly; multiple -> a `Decision`; the pre-combat maneuver grant actually
claimable during a real combat round on both the unblocked and blocked
paths); and the ruling's fizzle convention (cost still paid, no further
effect) when the announced target unlocks before `resolve()` runs.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards.fleetness import KRCG_ID
from vtesbot.cards.registry import Status, get
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import ACTION_ACTION_CARD, ACTION_BLEED
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import PASS_VALUE, HookOption
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, minion_phase

NAME = "Fleetness"


def _fleetness_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="action")


def _match_action(action: str, intercept: int = 1):
    """A fake `"intercept_modifier"` provider gated on a specific `action`
    discriminator -- stands in for some other intercept-granting card so a
    test can force a block attempt to actually succeed against this card's
    own `base_stealth=1` baseline, mirroring `test_enchant_kindred.py`'s own
    pattern for the same purpose."""

    def provide(state, context):
        del state
        if context.get("action") != action:
            return []
        return [HookOption(choice=Choice("match", "+1 intercept"), apply=lambda s: intercept)]

    return provide


def test_registered_as_implemented_against_the_action_card_play_hook():
    reg = get(KRCG_ID)
    assert reg is not None
    assert reg.status is Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


def test_is_on_the_active_2p_allowed_list():
    import json
    from pathlib import Path

    data_path = Path(__file__).resolve().parents[2] / "data" / "formats" / "2p" / "2026-10-03.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    ids = {card.get("krcg_id") for card in data["cards"]}
    assert KRCG_ID in ids


# --- Playability gates (shared by both clauses) -----------------------------


def test_no_clause_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=5, disciplines=("CEL",))
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0, locked=True)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert options == []


def test_no_clause_offered_without_enough_blood():
    """Printed blood cost: a vampire with 0 blood cannot play the card at
    all, regardless of discipline level."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=0, disciplines=("CEL",)
    )
    p1.hand.append(_fleetness_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0, locked=True)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert options == []


# --- Basic/superior discipline-level gating ---------------------------------


def test_basic_not_offered_without_cel():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("pot",)
    )
    p1.hand.append(_fleetness_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0, locked=True)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert "fleetness:basic" not in values


def test_basic_offered_with_only_basic_cel():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("cel",)
    )
    p1.hand.append(_fleetness_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0, locked=True)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert values == {"fleetness:basic"}


def test_basic_also_offered_with_only_superior_cel():
    """Rulebook §3 "may opt to use either the basic or the superior
    effect": superior access alone also unlocks the basic clause."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("CEL",)
    )
    p1.hand.append(_fleetness_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0, locked=True)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert "fleetness:basic" in values


def test_superior_not_offered_with_only_basic_cel():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("cel",)
    )
    p1.hand.append(_fleetness_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0, locked=True)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert "fleetness:superior" not in values


def test_superior_offered_with_superior_cel():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("CEL",)
    )
    p1.hand.append(_fleetness_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0, locked=True)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert "fleetness:superior" in values


# --- "+1 stealth action. [cel] Ⓓ Bleed." (basic clause) --------------------


def test_basic_bleeds_for_1_with_plus_one_stealth_baseline_and_pays_cost_on_resolve():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("cel",)
    )
    p1.hand.append(_fleetness_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "fleetness:basic")
    defender = ScriptedAgent("P2")
    # base_stealth=1 > default intercept=0: any plain block attempt fails outright.
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # default bleed amount 1, no printed bonus
    assert game.state.edge_holder == "P1"
    assert game.blood_of("V1") == 4  # 1-blood cost paid on the unblocked branch
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_basic_blocked_does_not_resolve_and_cost_is_not_paid():
    provider = _match_action(ACTION_BLEED)
    hooks.register("intercept_modifier", provider)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire(
            "V1", capacity=5, blood=5, disciplines=("cel",)
        )
        p1.hand.append(_fleetness_card())
        builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1)
        game = builder.build()
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "fleetness:basic")
        actor.expect("strike_choice", "no_strike")
        actor.expect("press", "end_combat")
        defender = ScriptedAgent("P2")
        defender.expect("block_attempt", "block_with:B1")
        defender.expect("intercept_modifier", "match")
        defender.expect("strike_choice", "no_strike")
        defender.expect("press", "end_combat")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = defender

        minion_phase(game.state, "P1")

        assert game.pool_of("P2") == 30  # blocked: resolve() never ran
        assert game.state.edge_holder is None
        assert game.blood_of("V1") == 5  # blocked: cost not paid
        assert game.state.players["P1"].hand == []
        assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("intercept_modifier", provider)


def test_basic_clause_is_tagged_a_real_bleed():
    """Card text literally says "Bleed", so `ActionCardSpec.action` must be
    `ACTION_BLEED`, confirmed indirectly by `_match_action(ACTION_BLEED)`
    above successfully forcing a block in
    `test_basic_blocked_does_not_resolve_and_cost_is_not_paid` -- re-asserted
    directly here against the hook's own returned spec."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("cel",)
    )
    p1.hand.append(_fleetness_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    (option,) = [o for o in options if o.choice.value == "fleetness:basic"]
    spec = option.apply(game.state)
    assert spec.action == ACTION_BLEED


# --- "[CEL] Ⓓ Enter combat with a locked minion. ..." (superior clause) -----


def test_superior_not_offered_without_an_eligible_locked_target():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("CEL",)
    )
    p1.hand.append(_fleetness_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)  # ready, unlocked
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert all(o.choice.value != "fleetness:superior" for o in options)


def test_superior_not_offered_when_the_opponent_controls_no_vampire():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("CEL",)
    )
    p1.hand.append(_fleetness_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert all(o.choice.value != "fleetness:superior" for o in options)


def test_superior_single_eligible_target_enters_combat_and_maneuver_is_claimable_unblocked():
    """Also proves the OQ-25 pre-combat maneuver grant is actually claimable
    during a real combat round, not merely seeded: the acting vampire's
    controller is offered (and uses) a `"maneuver_choice"` during Determine
    Range, before the strike step. The target has no other opposing vampire
    to block with (it is itself locked, so it cannot be offered as a
    blocker), so the whole block-attempt phase is skipped."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("CEL",)
    )
    p1.hand.append(_fleetness_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0, locked=True)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "fleetness:superior")
    actor.expect("maneuver_choice", "fleetness:maneuver")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.vampire("B1").wounded is True  # V1's hand strike landed in the forced combat
    assert game.blood_of("V1") == 4  # 1-blood cost paid on the unblocked branch
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_with_multiple_eligible_targets_raises_a_choice_decision():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("CEL",)
    )
    p1.hand.append(_fleetness_card())
    builder.player("P2", pool=30).ready_vampire(
        "B1", capacity=5, blood=0, locked=True
    ).ready_vampire("B2", capacity=5, blood=0, locked=True)
    game = builder.build()
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "fleetness_combat_target":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "fleetness:superior")
    actor.expect("fleetness_combat_target", "fleetness_combat_target:B1")
    actor.expect("maneuver_choice", PASS_VALUE)
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert seen == [["fleetness_combat_target:B1", "fleetness_combat_target:B2"]]
    assert game.vampire("B1").wounded is True
    assert game.vampire("B2").wounded is False
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_blocked_cost_is_not_paid_but_the_grant_still_threads_into_the_combat():
    """The announced (locked) target is never offered as a blocker (it is
    locked); the opponent's other, unlocked vampire blocks instead -- the
    generic block-attempt path's own internal `run_combat` call supersedes
    `resolve()` entirely. The `maneuver_choice` still fires inside that
    combat, proving `ActionCardSpec.maneuver_grant` threads all the way into
    `perform_minion_action`'s own blocked-branch `run_combat` call (OQ-25).
    """
    provider = _match_action(ACTION_ACTION_CARD)
    hooks.register("intercept_modifier", provider)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire(
            "V1", capacity=5, blood=5, disciplines=("CEL",)
        )
        p1.hand.append(_fleetness_card())
        builder.player("P2", pool=30).ready_vampire(
            "T1", capacity=5, blood=0, locked=True
        ).ready_vampire("B2", capacity=5, blood=0)
        game = builder.build()
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "fleetness:superior")
        actor.expect("maneuver_choice", "fleetness:maneuver")
        actor.expect("strike_choice", "hand_strike")
        actor.expect("press", "end_combat")
        defender = ScriptedAgent("P2")
        defender.expect("block_attempt", "block_with:B2")
        defender.expect("intercept_modifier", "match")
        defender.expect("strike_choice", "no_strike")
        defender.expect("press", "end_combat")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = defender

        minion_phase(game.state, "P1")

        assert game.blood_of("V1") == 5  # blocked: cost not paid
        assert game.vampire("B2").locked is True  # blocker locked, per the generic block path
        assert game.vampire("B2").wounded is True  # V1's hand strike landed on the blocker
        assert game.vampire("T1").locked is True  # announced target untouched, never entered combat
        assert game.state.players["P1"].hand == []
        assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("intercept_modifier", provider)


def test_superior_resolve_fizzles_if_the_target_unlocks_before_resolve_but_cost_is_still_paid():
    """OQ-21/the card's own on-file ruling: an unblocked action whose target
    no longer meets the printed condition at resolve time fizzles -- "cost,
    if any, is paid, and it is considered successful, but has no effect."
    Not reachable through ordinary play today (nothing in this engine's
    current scope unlocks an opposing vampire during a block-attempt
    window), so exercised directly against the hook machinery, bypassing
    `minion_phase`."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("CEL",)
    )
    p1.hand.append(_fleetness_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0, locked=True)
    game = builder.build()
    state = game.state

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, state, player="P1", vampire="V1")
    (option,) = [o for o in options if o.choice.value == "fleetness:superior"]
    spec = option.apply(state)  # single eligible target (B1): bound directly, no Decision.

    game.vampire("B1").locked = False  # simulate the target unlocking post-announce.

    spec.resolve({})

    assert game.vampire("B1").wounded is False  # fizzled: no combat happened
    assert game.blood_of("V1") == 4  # cost still paid despite the fizzle
    assert state.players["P1"].hand == []  # the card itself was still consumed at apply() time
