"""Propaganda (krcg id 101495, `src/vtesbot/cards/propaganda.py`).

Card text: "[pre] Ⓓ Bleed with +1 bleed. Titled vampires cannot block this
action.\n[PRE] As above, and the target Methuselah locks a ready unlocked
minion they control." No rulings on file.

One assertion per clause/qualifier: the printed 2-blood cost gate (at
offer time, for both clauses) and its "paid only on the unblocked branch"
timing; the basic/superior discipline-level gating; the basic clause's
directed +1-bleed bleed with the "titled vampires cannot block" property
filter (both the hardcoded candidate list and an injected candidate); the
superior clause's additional "target Methuselah locks a ready unlocked
minion" effect (the *defender* chooses among ties, and the clause fizzles
with no decision when the defender has none at all, without blocking the
bleed itself); and the ENG-003 bleed-amount composability tag (`ACTION_
BLEED`).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards.propaganda import KRCG_ID
from vtesbot.cards.registry import Status, get
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import ACTION_BLEED
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, minion_phase

NAME = "Propaganda"


def _propaganda_card() -> LibraryCard:
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


# --- Playability gates (shared by both clauses) -----------------------------


def test_no_clause_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=5, disciplines=("PRE",))
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert options == []


def test_no_clause_offered_without_enough_blood():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("PRE",)
    )
    p1.hand.append(_propaganda_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    assert options == []


# --- Basic/superior discipline-level gating ---------------------------------


def test_basic_not_offered_without_pre():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("dom",)
    )
    p1.hand.append(_propaganda_card())
    builder.player("P2", pool=30)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert "propaganda:basic" not in values


def test_basic_offered_with_only_basic_pre():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("pre",)
    )
    p1.hand.append(_propaganda_card())
    builder.player("P2", pool=30)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert values == {"propaganda:basic"}


def test_basic_also_offered_with_only_superior_pre():
    """Rulebook §3 "may opt to use either the basic or the superior
    effect": superior access alone also unlocks the basic clause."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("PRE",)
    )
    p1.hand.append(_propaganda_card())
    builder.player("P2", pool=30)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert values == {"propaganda:basic", "propaganda:superior"}


def test_superior_not_offered_with_only_basic_pre():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("pre",)
    )
    p1.hand.append(_propaganda_card())
    builder.player("P2", pool=30)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    }
    assert "propaganda:superior" not in values


# --- "[pre] Ⓓ Bleed with +1 bleed. Titled vampires cannot block this
# action." (basic clause) -----------------------------------------------------


def test_basic_bleeds_for_2_and_pays_cost_on_resolve():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("pre",)
    )
    p1.hand.append(_propaganda_card())
    builder.player("P2", pool=30)  # no ready vampire: unblockable
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "propaganda:basic")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # default bleed 1 + printed "+1 bleed" = 2
    assert game.state.edge_holder == "P1"
    assert game.blood_of("V1") == 3  # 2-blood cost paid on the unblocked branch
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()


def test_basic_blocked_does_not_resolve_and_cost_is_not_paid():
    """An *untitled* defending vampire can still block normally -- the
    predicate only excludes titled candidates. `base_stealth=0` matches
    the default intercept, so a plain block attempt succeeds immediately,
    contrast `dominate_kine.py`'s basic clause which needs an extra
    intercept modifier to force a block at `base_stealth=1`."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("pre",)
    )
    p1.hand.append(_propaganda_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "propaganda:basic")
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
    assert game.blood_of("V1") == 5  # blocked: cost not paid
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_titled_defending_vampire_cannot_block():
    """ "Titled vampires cannot block this action." -- a titled defender,
    even as the only ready unlocked candidate, is excluded from the
    hardcoded candidate list entirely: no block decision is raised."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("pre",)
    )
    p1.hand.append(_propaganda_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1, title="Prince")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "propaganda:basic")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")  # B1 excluded: no block decision at all

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28
    actor.assert_exhausted()


def test_titled_vampire_also_excluded_as_an_injected_block_candidate():
    """The predicate filters an injected candidate too (e.g. Second
    Tradition: Domain, Organized Resistance), not just the hardcoded
    candidate list."""

    def injection_provider(state, context):
        del state
        target_id = "B1"

        def apply(s):
            vampire = s.players[context["defender"]].vampires[target_id]
            vampire.locked = False
            return vampire

        return [
            HookOption(
                choice=Choice("forced_block:B1", "Unlock and force-block with B1"),
                apply=apply,
                block_candidate_instance_id=target_id,
            )
        ]

    hooks.register("block_candidate_injection", injection_provider)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire(
            "V1", capacity=5, blood=5, disciplines=("pre",)
        )
        p1.hand.append(_propaganda_card())
        builder.player("P2", pool=30).ready_vampire(
            "B1", capacity=5, blood=1, title="Prince", locked=True
        )
        game = builder.build()
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "propaganda:basic")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = ScriptedAgent("P2")  # injected option filtered too

        minion_phase(game.state, "P1")

        assert game.pool_of("P2") == 28
        assert game.vampire("B1").locked is True  # never unlocked: the injected apply never ran
        actor.assert_exhausted()
    finally:
        hooks.unregister("block_candidate_injection", injection_provider)


def test_basic_clause_is_tagged_a_real_bleed():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("pre",)
    )
    p1.hand.append(_propaganda_card())
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    (option,) = [o for o in options if o.choice.value == "propaganda:basic"]
    spec = option.apply(game.state)
    assert spec.action == ACTION_BLEED
    assert spec.block_candidate_predicate is not None


# --- "[PRE] As above, and the target Methuselah locks a ready unlocked
# minion they control." (superior clause) ------------------------------------


def test_superior_forces_the_defender_to_lock_a_ready_unlocked_vampire():
    """The *target* Methuselah (the defender), not the caller, chooses
    among multiple eligible candidates -- `force_lock_ready_unlocked_
    minion`'s own Brujah Debate-sourced ruling."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("PRE",)
    )
    p1.hand.append(_propaganda_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0).ready_vampire(
        "B2", capacity=5, blood=0
    )
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "propaganda:superior")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("forced_lock_own_minion", "lock:B2")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28
    assert game.vampire("B1").locked is False
    assert game.vampire("B2").locked is True
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_fizzles_the_lock_with_no_decision_when_defender_has_no_ready_vampire():
    """ "Cannot do the impossible" convention: the bleed itself still
    resolves even though the lock clause has nothing to act on."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("PRE",)
    )
    p1.hand.append(_propaganda_card())
    builder.player("P2", pool=30)  # no vampire at all: unblockable, and nothing to lock
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "propaganda:superior")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")  # no decision raised at all

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28
    actor.assert_exhausted()


def test_superior_titled_defender_also_excluded_from_blocking():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("PRE",)
    )
    p1.hand.append(_propaganda_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1, title="Justicar")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "propaganda:superior")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")  # B1 excluded: no block_attempt decision at all,
    # and the sole ready unlocked vampire is auto-forced (no decision) by force_lock itself.

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28
    assert game.vampire("B1").locked is True  # forced by the superior clause's own lock effect
    actor.assert_exhausted()


def test_superior_blocked_cost_is_not_paid_and_no_lock_happens():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=5, disciplines=("PRE",)
    )
    p1.hand.append(_propaganda_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "propaganda:superior")
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
    assert game.blood_of("V1") == 5  # blocked: cost not paid
    assert game.vampire("B1").locked is True  # re-locked for combat, like any blocker
    actor.assert_exhausted()
    defender.assert_exhausted()
