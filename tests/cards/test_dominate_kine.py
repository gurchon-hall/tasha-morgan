"""Dominate Kine (krcg id 100573, `src/vtesbot/cards/dominate_kine.py`).

Card text: "[dom] +1 stealth action. Ⓓ Bleed with +1 bleed.\n[DOM] Ⓓ Steal
a location." Rulings: "If used to steal an equipment representing a
location, it can be placed on any minion controlled by the new
controller." [RTR 19960112]; "Changing the controller of a location has
no other effect, unless specified by card text. Exception: ..." [RTR
19980623].

One assertion per clause/qualifier/ruling: the printed 2-blood cost gate
(at offer time, for both clauses) and its "paid only on the unblocked
branch" timing; the basic/superior discipline-level gating; the basic
clause's directed +1-bleed bleed with its own +1 stealth baseline, tagged
`ACTION_BLEED` so a bleed-gated provider sharing the same window still
fires; the superior clause's "steal a location" (no opponent location in
play -> not offered; single eligible location -> applied directly;
multiple -> a `Decision`; "changing the controller has no other effect" --
locked/zone untouched); and the RUL-007 fizzle convention (cost still paid,
no further effect) when the announced location stops qualifying before
`resolve()` runs.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards.dominate_kine import KRCG_ID
from vtesbot.cards.registry import Status, get
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import ACTION_BLEED
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.master_cards import bring_master_card_into_play
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, minion_phase

NAME = "Dominate Kine"
# Chantry (krcg id 100329): a `LOCATION_KRCG_IDS` member with no card module
# of its own, mirroring `test_disputed_territory.py`'s own stand-in choice.
LOCATION_KRCG_ID = 100329
LOCATION_NAME = "Chantry"
OTHER_LOCATION_KRCG_ID = 100620  # Elder Library
OTHER_LOCATION_NAME = "Elder Library"


def _dominate_kine_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="action")


def _match_action(action: str, intercept: int = 1):
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
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=5, disciplines=("DOM",))
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert options == []


def test_no_clause_offered_without_enough_blood():
    """Printed blood cost: a vampire with 1 blood (< 2) cannot play the
    card at all, regardless of discipline level."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("DOM",)
    )
    p1.hand.append(_dominate_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert options == []


# --- Basic/superior discipline-level gating ---------------------------------


def test_basic_not_offered_without_dom():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("pot",)
    )
    p1.hand.append(_dominate_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert "dominate_kine:basic" not in values


def test_basic_offered_with_only_basic_dom():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("dom",)
    )
    p1.hand.append(_dominate_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert values == {"dominate_kine:basic"}


def test_basic_also_offered_with_only_superior_dom():
    """Rulebook §3 "may opt to use either the basic or the superior
    effect": superior access alone also unlocks the basic clause."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("DOM",)
    )
    p1.hand.append(_dominate_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert "dominate_kine:basic" in values


def test_superior_not_offered_with_only_basic_dom():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("dom",)
    )
    p1.hand.append(_dominate_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()
    bring_master_card_into_play(game.state, "P2", krcg_id=LOCATION_KRCG_ID, name=LOCATION_NAME)

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert "dominate_kine:superior" not in values


# --- "[dom] +1 stealth action. Ⓓ Bleed with +1 bleed." (basic clause) -------


def test_basic_bleeds_for_2_with_plus_one_stealth_baseline_and_pays_cost_on_resolve():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("dom",)
    )
    p1.hand.append(_dominate_kine_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "dominate_kine:basic")
    defender = ScriptedAgent("P2")
    # base_stealth=1 > default intercept=0: any plain block attempt fails outright.
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # default bleed 1 + printed "+1 bleed" = 2
    assert game.state.edge_holder == "P1"
    assert game.blood_of("V1") == 3  # 2-blood cost paid on the unblocked branch
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
            "V1", capacity=5, blood=5, disciplines=("dom",)
        )
        p1.hand.append(_dominate_kine_card())
        builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1)
        game = builder.build()
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "dominate_kine:basic")
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
    `test_basic_blocked_does_not_resolve_and_cost_is_not_paid` --
    re-asserted directly here against the hook's own returned spec."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("dom",)
    )
    p1.hand.append(_dominate_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    (option,) = [o for o in options if o.choice.value == "dominate_kine:basic"]
    spec = option.apply(game.state)
    assert spec.action == ACTION_BLEED


# --- "[DOM] Ⓓ Steal a location." (superior clause) -------------------------


def test_superior_not_offered_without_any_opponent_location_in_play():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("DOM",)
    )
    p1.hand.append(_dominate_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert all(o.choice.value != "dominate_kine:superior" for o in options)


def test_superior_not_offered_for_the_actors_own_location():
    """The directed target is always the single 2P opponent (module
    docstring): the actor's own location is never an eligible target, even
    with the superior clause otherwise unlocked."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("DOM",)
    )
    p1.hand.append(_dominate_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()
    bring_master_card_into_play(game.state, "P1", krcg_id=LOCATION_KRCG_ID, name=LOCATION_NAME)

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert all(o.choice.value != "dominate_kine:superior" for o in options)


def test_superior_single_eligible_location_is_stolen_and_pays_cost_on_resolve():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("DOM",)
    )
    p1.hand.append(_dominate_kine_card())
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with
    game = builder.build()
    location = bring_master_card_into_play(
        game.state, "P2", krcg_id=LOCATION_KRCG_ID, name=LOCATION_NAME
    )
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "dominate_kine:superior")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert location.controller == "P1"
    assert location.instance_id in game.state.players["P1"].master_cards
    assert location.instance_id not in game.state.players["P2"].master_cards
    assert game.blood_of("V1") == 3  # 2-blood cost paid on the unblocked branch
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()


def test_superior_changing_the_controller_has_no_other_effect():
    """ "Changing the controller of a location has no other effect ...":
    a locked location stays locked, and stays `zone == "in_play"`, once
    control changes. [RTR 19980623]"""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("DOM",)
    )
    p1.hand.append(_dominate_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()
    location = bring_master_card_into_play(
        game.state, "P2", krcg_id=LOCATION_KRCG_ID, name=LOCATION_NAME
    )
    location.locked = True
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "dominate_kine:superior")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert location.controller == "P1"
    assert location.locked is True
    assert location.zone == "in_play"


def test_superior_with_multiple_eligible_locations_raises_a_choice_decision():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("DOM",)
    )
    p1.hand.append(_dominate_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()
    location_a = bring_master_card_into_play(
        game.state, "P2", krcg_id=LOCATION_KRCG_ID, name=LOCATION_NAME
    )
    location_b = bring_master_card_into_play(
        game.state, "P2", krcg_id=OTHER_LOCATION_KRCG_ID, name=OTHER_LOCATION_NAME
    )
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "dominate_kine_target":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "dominate_kine:superior")
    actor.expect("dominate_kine_target", f"dominate_kine_target:{location_a.instance_id}")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen == [
        sorted(
            [
                f"dominate_kine_target:{location_a.instance_id}",
                f"dominate_kine_target:{location_b.instance_id}",
            ]
        )
    ]
    assert location_a.controller == "P1"
    assert location_b.controller == "P2"
    actor.assert_exhausted()


def test_superior_blocked_cost_is_not_paid_and_location_is_unchanged():
    """`base_stealth=0`: the defender's default 0 intercept already
    matches it, so a plain block attempt succeeds with no modifier
    needed (contrast the basic clause's `base_stealth=1`)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("DOM",)
    )
    p1.hand.append(_dominate_kine_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1)
    game = builder.build()
    location = bring_master_card_into_play(
        game.state, "P2", krcg_id=LOCATION_KRCG_ID, name=LOCATION_NAME
    )
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "dominate_kine:superior")
    actor.expect("strike_choice", "no_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert location.controller == "P2"  # blocked: resolve() never ran
    assert game.blood_of("V1") == 5  # blocked: cost not paid
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_resolve_fizzles_if_the_location_stops_qualifying_but_cost_is_still_paid():
    """RUL-007 convention: the target is chosen at `apply()` time (announce),
    with `resolve()` only ever re-validating -- never re-choosing -- that
    same target. Not reachable through ordinary play today, so exercised
    directly against the hook machinery, bypassing `minion_phase`."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("DOM",)
    )
    p1.hand.append(_dominate_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()
    state = game.state
    location = bring_master_card_into_play(
        state, "P2", krcg_id=LOCATION_KRCG_ID, name=LOCATION_NAME
    )

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, state, player="P1", vampire="V1")
    (option,) = [o for o in options if o.choice.value == "dominate_kine:superior"]
    spec = option.apply(state)  # single eligible location: bound directly, no Decision.

    location.zone = "burned"  # simulate the target leaving play post-announce.

    spec.resolve({})

    assert location.controller == "P2"  # fizzled: no transfer happened
    assert game.blood_of("V1") == 3  # cost still paid despite the fizzle
    assert state.players["P1"].hand == []  # the card itself was still consumed at apply() time
