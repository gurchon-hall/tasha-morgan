"""Enchant Kindred (krcg id 100640, `src/vtesbot/cards/enchant_kindred.py`).

Card text: "[pre] Ⓓ Bleed with +1 bleed.\n[PRE] +1 stealth action. Add 2
blood to a younger vampire in your uncontrolled region." No rulings on file.

One assertion per clause/qualifier: the basic clause (directed bleed,
amount 2, tagged `action=ACTION_BLEED` so a bleed-gated provider sharing the
same window still fires -- proven with Bonding's own real superior clause,
mirroring `tests/rules/test_action_card_play.py`'s own worked proof), the
superior clause (undirected, +1 stealth baseline, "a younger vampire"
target filter, capacity-room clamping, the new "which target" decision and
its "only when needed" single-target auto-apply), the basic/superior
discipline-level gating (inferior access unlocks only the basic clause),
and the one-shot immediate-consumption hand/ash-heap behaviour for both
clauses.
"""

import contextlib

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import bonding as bonding_module
from vtesbot.cards.enchant_kindred import KRCG_ID
from vtesbot.cards.registry import Status, get
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import ACTION_ACTION_CARD
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.observation import Observation
from vtesbot.engine.phases.minion import minion_phase

NAME = "Enchant Kindred"


def _enchant_kindred_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="action")


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


# --- Basic clause: "[pre] Ⓓ Bleed with +1 bleed" ---------------------------


def test_basic_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, disciplines=("pre",))
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # base bleed 1 only
    actor.assert_exhausted()


def test_basic_not_offered_without_presence():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_enchant_kindred_card())
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29
    actor.assert_exhausted()


def test_basic_level_bleeds_for_2_and_is_consumed_as_a_one_shot_action():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pre",)
    )
    p1.hand.append(_enchant_kindred_card())
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "enchant_kindred:basic")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # base 1 + 1 printed = 2
    assert game.state.edge_holder == "P1"
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()


def test_basic_level_blocked_does_not_resolve_but_the_card_is_still_consumed():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pre",)
    )
    p1.hand.append(_enchant_kindred_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "enchant_kindred:basic")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # blocked: resolve() never ran
    assert game.state.edge_holder is None
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_basic_clause_is_tagged_a_real_bleed_so_bonding_still_fires():
    """Rules-auditor finding (OQ-17 follow-up), proven against the real card:
    because the basic clause's card text literally says "Bleed",
    `ActionCardSpec.action` must be `ACTION_BLEED`, not the generic
    `ACTION_ACTION_CARD` default -- otherwise an existing bleed-gated
    provider sharing the same window (here, Bonding's own real, unmodified
    superior clause, gated on `context.get("action") == ACTION_BLEED`) would
    be silently and wrongly suppressed."""
    with contextlib.suppress(ValueError):
        hooks.unregister(
            bonding_module.STEALTH_MODIFIER_HOOK, bonding_module._provide_bonding_superior
        )
    hooks.register(bonding_module.STEALTH_MODIFIER_HOOK, bonding_module._provide_bonding_superior)

    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("pre", "DOM")
    )
    p1.hand.append(_enchant_kindred_card())
    p1.hand.append(
        LibraryCard(krcg_id=bonding_module.KRCG_ID, name="Bonding", card_type="modifier")
    )
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    seen_choices: dict[str, list[str]] = {"values": []}

    class ActorAgent:
        player_id = "P1"

        def decide(self, observation: Observation, decision):
            del observation
            by_kind = {
                "minion_phase_choice": "act_with:V1",
                "action_choice": "enchant_kindred:basic",
                "stealth_modifier": "decline",
                "strike_choice": "no_strike",
                "press": "end_combat",
            }
            if decision.kind == "stealth_modifier":
                seen_choices["values"] = sorted(c.value for c in decision.choices)
            expected_value = by_kind[decision.kind]
            matching = [c for c in decision.choices if c.value == expected_value]
            assert matching, (
                f"{expected_value!r} not among {[c.value for c in decision.choices]} "
                f"for kind {decision.kind!r}"
            )
            return matching[0]

    game.state.agents["P1"] = ActorAgent()
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert "bonding:superior" in seen_choices["values"]
    defender.assert_exhausted()


# --- Superior clause: "[PRE] +1 stealth action. Add 2 blood to a younger
#     vampire in your uncontrolled region." ---------------------------------


def test_superior_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("PRE",)
    )
    p1.uncontrolled_vampire("U1", capacity=2, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    actor.assert_exhausted()


def test_superior_not_offered_with_only_basic_presence():
    """Inferior-only access unlocks only the basic clause: a vampire with
    only basic "pre" never sees the superior option, even with an eligible
    target and the card in hand."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("pre",)
    )
    p1.hand.append(_enchant_kindred_card())
    p1.uncontrolled_vampire("U1", capacity=2, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "action_choice":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "enchant_kindred:basic")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen == [["bleed", "enchant_kindred:basic", "hunt"]]
    actor.assert_exhausted()


def test_superior_not_offered_without_an_eligible_uncontrolled_target():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("PRE",)
    )
    p1.hand.append(_enchant_kindred_card())
    builder.player("P2", pool=30)
    game = builder.build()
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "action_choice":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "enchant_kindred:basic")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen == [["bleed", "enchant_kindred:basic", "hunt"]]
    actor.assert_exhausted()


def test_superior_not_offered_when_the_uncontrolled_vampire_is_not_younger():
    """Equal (not strictly lower) printed capacity is not "younger"."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("PRE",)
    )
    p1.hand.append(_enchant_kindred_card())
    p1.uncontrolled_vampire("U1", capacity=5, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "action_choice":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "enchant_kindred:basic")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen == [["bleed", "enchant_kindred:basic", "hunt"]]
    actor.assert_exhausted()


def test_superior_not_offered_for_the_opponents_uncontrolled_vampire():
    """ "Your uncontrolled region" -- the opponent's own uncontrolled
    vampire, even if younger, is not a legal target."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("PRE",)
    )
    p1.hand.append(_enchant_kindred_card())
    p2 = builder.player("P2", pool=30)
    p2.uncontrolled_vampire("U1", capacity=2, blood=0)
    game = builder.build()
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "action_choice":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "enchant_kindred:basic")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen == [["bleed", "enchant_kindred:basic", "hunt"]]
    actor.assert_exhausted()


def test_superior_not_offered_when_the_target_is_already_at_capacity():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("PRE",)
    )
    p1.hand.append(_enchant_kindred_card())
    p1.uncontrolled_vampire("U1", capacity=2, blood=2)  # already full
    builder.player("P2", pool=30)
    game = builder.build()
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "action_choice":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "enchant_kindred:basic")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen == [["bleed", "enchant_kindred:basic", "hunt"]]
    actor.assert_exhausted()


def test_superior_single_eligible_target_is_applied_without_a_decision():
    """ "Only when needed": with exactly one eligible target, the amount is
    applied directly, with no "enchant_kindred_target" decision raised."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("PRE",)
    )
    p1.hand.append(_enchant_kindred_card())
    p1.uncontrolled_vampire("U1", capacity=4, blood=0)
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "enchant_kindred:superior")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.blood_of("U1") == 2
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()


def test_superior_amount_is_clamped_by_the_targets_remaining_capacity():
    """Target already has 1 blood out of capacity 2: room for only 1 more of
    the printed 2 blood (`add_blood`'s own effective-capacity clamp)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("PRE",)
    )
    p1.hand.append(_enchant_kindred_card())
    p1.uncontrolled_vampire("U1", capacity=2, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "enchant_kindred:superior")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.blood_of("U1") == 2  # capped at capacity, not 1 + 2 = 3
    actor.assert_exhausted()


def test_superior_with_multiple_eligible_targets_raises_a_choice_decision():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("PRE",)
    )
    p1.hand.append(_enchant_kindred_card())
    p1.uncontrolled_vampire("U1", capacity=4, blood=0)
    p1.uncontrolled_vampire("U2", capacity=4, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "enchant_kindred_target":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "enchant_kindred:superior")
    actor.expect("enchant_kindred_target", "enchant_kindred_target:U1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen == [["enchant_kindred_target:U1", "enchant_kindred_target:U2"]]
    assert game.blood_of("U1") == 2
    assert game.blood_of("U2") == 0
    actor.assert_exhausted()


def test_superior_uses_plus_one_stealth_baseline():
    """ "+1 stealth action": the superior clause's base stealth is 1, not 0
    -- a block attempt with the defender's default 0 intercept and no other
    modifiers fails outright, so the card resolves without ever offering a
    "stealth_modifier" decision."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("PRE",)
    )
    p1.hand.append(_enchant_kindred_card())
    p1.uncontrolled_vampire("U1", capacity=4, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "enchant_kindred:superior")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")  # stealth(1) > intercept(0): attempt failed
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.blood_of("U1") == 2
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_blocked_does_not_resolve_but_the_card_is_still_consumed():
    """Base stealth 1 needs a matching +1 intercept to actually succeed a
    block attempt; a temporary fake `"intercept_modifier"` provider (gated
    on this card's own default `ACTION_ACTION_CARD` discriminator, mirroring
    `test_bonding.py`'s own pattern for forcing a block) stands in for some
    other intercept-granting card so this test can reach the blocked
    branch."""

    def match_superior_stealth(state, context):
        if context.get("action") != ACTION_ACTION_CARD:
            return []
        return [HookOption(choice=Choice("match", "+1 intercept"), apply=lambda s: 1)]

    hooks.register("intercept_modifier", match_superior_stealth)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire(
            "V1", capacity=5, blood=1, disciplines=("PRE",)
        )
        p1.hand.append(_enchant_kindred_card())
        p1.uncontrolled_vampire("U1", capacity=4, blood=0)
        builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
        game = builder.build()
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "enchant_kindred:superior")
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

        assert game.blood_of("U1") == 0  # blocked: resolve() never ran
        assert game.state.players["P1"].hand == []
        assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
        assert game.zone_of("B1") == "ready"
        assert game.vampire("B1").locked is True
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("intercept_modifier", match_superior_stealth)
