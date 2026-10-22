"""Pre-combat maneuver grant primitive (ENG-017,
resolved): a card's own grant (e.g. Fleetness's superior clause, "This
acting vampire gets 1 optional maneuver during that combat") must exist at
*announce time* -- strictly before the block-attempt window opens, i.e.
before whichever combat the resulting action produces has even started.
`engine/combat.py::run_combat`'s own `initial_combat_state` parameter and
`engine/action.py::perform_minion_action`'s own `maneuver_grant` parameter
(threaded from `engine/phases/minion.py::ActionCardSpec.maneuver_grant`) are
the generic primitive this file proves end-to-end, through both paths that
can lead into a combat from one minion action: unblocked (the card's own
`resolve()` calls `run_combat` directly, mirroring `cards/line_brawl.py`'s
`[pot]` clause) and blocked (`perform_minion_action`'s own internal
`run_combat` call, which has no `ActionCardSpec`-shaped field or hook of its
own to extend).

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a trivial fake `"maneuver"` provider recognizing the
generic `PRE_COMBAT_MANEUVER_GRANT_KEY` -- Fleetness itself remains
`card-implementer`'s job once this capability exists (`src/vtesbot/cards/
fleetness.py` stays `Status.BLOCKED` until that pass).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards._shared import play_from_hand
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import perform_minion_action
from vtesbot.engine.combat import (
    MANEUVER_HOOK,
    PRE_COMBAT_MANEUVER_GRANT_KEY,
    consume_pre_combat_maneuver_grant,
    pre_combat_maneuver_available,
    run_combat,
    seed_pre_combat_maneuver_grant,
)
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, ActionCardSpec, minion_phase

FAKE_FLEETNESS_KRCG_ID = 999_001


def _provide_fake_pre_combat_maneuver(state, context):
    """Generic stand-in for a `"maneuver"` provider recognizing
    `PRE_COMBAT_MANEUVER_GRANT_KEY` -- not card-specific, exactly the shape a
    real card's own provider (e.g. a future Fleetness module) would use:
    offer exactly when this combatant currently has an unclaimed pre-combat
    grant, via the shared `pre_combat_maneuver_available`/`consume_pre_
    combat_maneuver_grant` helpers (never reading/writing the dict directly)."""
    del state
    if not pre_combat_maneuver_available(context):
        return []

    def use(s):
        del s
        consume_pre_combat_maneuver_grant(context)

    return [
        hooks.HookOption(
            choice=Choice("fake_pre_combat_maneuver", "Pre-combat maneuver"), apply=use
        )
    ]


def _build_combat_scenario(*, blocking_blood: int = 0):
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=10, blood=5)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=10, blood=blocking_blood)
    return builder.build()


# --- Helper functions' own degrade-gracefully contract -----------------------


def test_pre_combat_maneuver_available_degrades_gracefully_without_shared_state():
    """Mirrors `additional_strike_limit_used`'s own convention: a hook offered
    directly, bypassing `run_combat` (no `combat_state` in context at all),
    is treated as "nothing granted," not an error."""
    assert pre_combat_maneuver_available({"vampire": "V1"}) is False
    consume_pre_combat_maneuver_grant({"vampire": "V1"})  # must not raise


def test_seed_pre_combat_maneuver_grant_shape_is_recognized_by_the_helpers():
    """Proves `seed_pre_combat_maneuver_grant`'s own output is exactly the
    shape `pre_combat_maneuver_available`/`consume_pre_combat_maneuver_grant`
    recognize, and that a grant seeded with `count=2` survives two separate
    consumptions before running out."""
    seed = seed_pre_combat_maneuver_grant("V1", count=2)
    context = {"vampire": "V1", "combat_state": seed}

    assert pre_combat_maneuver_available(context) is True
    consume_pre_combat_maneuver_grant(context)
    assert seed[PRE_COMBAT_MANEUVER_GRANT_KEY]["V1"] == 1
    assert pre_combat_maneuver_available(context) is True

    consume_pre_combat_maneuver_grant(context)
    assert seed[PRE_COMBAT_MANEUVER_GRANT_KEY]["V1"] == 0
    assert pre_combat_maneuver_available(context) is False

    consume_pre_combat_maneuver_grant(context)  # already 0: no-op
    assert seed[PRE_COMBAT_MANEUVER_GRANT_KEY]["V1"] == 0


# --- `run_combat`'s own `initial_combat_state` parameter ---------------------


def test_run_combat_without_initial_combat_state_offers_nothing_even_with_the_provider_registered():
    """Zero-regression check: the generic provider above offers nothing
    unless a grant was actually seeded -- `run_combat`'s own default (no
    `initial_combat_state` passed) is byte-for-byte unchanged."""
    hooks.register(MANEUVER_HOOK, _provide_fake_pre_combat_maneuver)
    game = _build_combat_scenario()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    actor.assert_exhausted()
    defender.assert_exhausted()


def test_run_combat_seeded_via_initial_combat_state_offers_the_grant_from_round_one():
    """The core engine primitive: a caller that seeds `initial_combat_state`
    before `run_combat`'s very first round sees the grant offered
    immediately, on turn 1 of Determine Range -- proving the grant exists
    *before* this combat's first step ever runs (distinct from Saku
    Pihlajamäki's own per-combat grant, which only ever needs to exist once
    her vampire is already a live combatant, something `run_combat`'s
    previous always-`{}` `combat_state` already provided for free)."""
    hooks.register(MANEUVER_HOOK, _provide_fake_pre_combat_maneuver)
    game = _build_combat_scenario()
    seed = seed_pre_combat_maneuver_grant(game.vampire("V1").instance_id)

    actor = ScriptedAgent("P1")
    actor.expect("maneuver_choice", "fake_pre_combat_maneuver")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"), seed)

    actor.assert_exhausted()
    defender.assert_exhausted()
    # One-shot: consumed, not left available for a hypothetical later round.
    assert seed[PRE_COMBAT_MANEUVER_GRANT_KEY][game.vampire("V1").instance_id] == 0


# --- `perform_minion_action`'s own `maneuver_grant` parameter (blocked path,
# and the unblocked path's own `resolve()`-seeds-it-itself shape) -----------


def test_perform_minion_action_unblocked_branch_lets_resolve_seed_the_grant_itself():
    """Unblocked path: no `perform_minion_action` engine change is needed --
    the card's own `resolve()` already calls `run_combat` directly (mirrors
    `cards/line_brawl.py`'s `[pot]` clause) and can pass `initial_combat_
    state=seed_pre_combat_maneuver_grant(...)` to that same call itself.
    Proven here through the real `perform_minion_action` entry point, not a
    bare `run_combat` call."""
    hooks.register(MANEUVER_HOOK, _provide_fake_pre_combat_maneuver)
    game = _build_combat_scenario()
    acting_vampire = game.vampire("V1")

    def resolve(pending):
        del pending
        run_combat(
            game.state,
            "P1",
            acting_vampire,
            "P2",
            game.vampire("B1"),
            seed_pre_combat_maneuver_grant(acting_vampire.instance_id),
        )

    actor = ScriptedAgent("P1")
    actor.expect("maneuver_choice", "fake_pre_combat_maneuver")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    # Declines the block attempt outright: resolve() runs (unblocked path).
    defender.expect("block_attempt", "decline")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(game.state, "P1", "P2", acting_vampire, 0, resolve)

    actor.assert_exhausted()
    defender.assert_exhausted()


def test_perform_minion_action_blocked_branch_threads_maneuver_grant_into_its_run_combat_call():
    """The blocked branch has no `ActionCardSpec`-shaped field or hook of its
    own to extend (ENG-017's own analysis): `perform_minion_action`'s new
    `maneuver_grant` parameter is the only way to reach it. `resolve` is
    never called here (the action goes blocked), proving the grant is
    honored by `perform_minion_action`'s own internal `run_combat` call
    itself, not merely by whatever the card's own `resolve` closure would
    have done on the other branch."""
    hooks.register(MANEUVER_HOOK, _provide_fake_pre_combat_maneuver)
    game = _build_combat_scenario()
    acting_vampire = game.vampire("V1")
    resolve_calls: list[bool] = []

    def resolve(pending):
        del pending
        resolve_calls.append(True)

    actor = ScriptedAgent("P1")
    actor.expect("maneuver_choice", "fake_pre_combat_maneuver")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(
        game.state,
        "P1",
        "P2",
        acting_vampire,
        0,
        resolve,
        maneuver_grant=acting_vampire.instance_id,
    )

    assert resolve_calls == []  # blocked: resolve() never ran
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_perform_minion_action_blocked_branch_without_maneuver_grant_offers_nothing():
    """Zero-regression check: `maneuver_grant=None` (the default, every call
    site before this pass -- `_perform_bleed`/`_perform_hunt`/`_perform_
    recruit_ally`) seeds nothing, so the fake provider offers no option even
    though it is registered."""
    hooks.register(MANEUVER_HOOK, _provide_fake_pre_combat_maneuver)
    game = _build_combat_scenario()
    acting_vampire = game.vampire("V1")

    def resolve(pending):
        del pending

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(game.state, "P1", "P2", acting_vampire, 0, resolve)

    actor.assert_exhausted()
    defender.assert_exhausted()


# --- `ActionCardSpec.maneuver_grant`, end-to-end through `minion_phase` -----


def _fake_fleetness_like_provider(state, context):
    """Stand-in for a real card module's own `"action_card_play"` provider
    (Fleetness itself remains `card-implementer`'s job): offers one option
    while its own fake card is in hand; its `ActionCardSpec` declares
    `maneuver_grant` (for the blocked path) and its own `resolve()` also
    seeds the same grant on its own direct `run_combat` call (for the
    unblocked path) -- exactly the two-path shape ENG-017 describes."""
    player = context["player"]
    vampire_id = context["vampire"]
    if not any(c.krcg_id == FAKE_FLEETNESS_KRCG_ID for c in state.players[player].hand):
        return []

    def _apply(s):
        play_from_hand(s, player, FAKE_FLEETNESS_KRCG_ID)
        other = s.other_player(player)

        def resolve(pending):
            del pending
            acting = s.players[player].vampires[vampire_id]
            target = next(iter(s.players[other].vampires.values()))
            run_combat(s, player, acting, other, target, seed_pre_combat_maneuver_grant(vampire_id))

        return ActionCardSpec(
            base_stealth=0,
            directed=True,
            resolve=resolve,
            maneuver_grant=vampire_id,
        )

    return [
        hooks.HookOption(choice=Choice("fake_fleetness", "Fake Fleetness-style card"), apply=_apply)
    ]


def test_action_card_spec_maneuver_grant_threads_through_minion_phase_unblocked():
    hooks.register(MANEUVER_HOOK, _provide_fake_pre_combat_maneuver)
    hooks.register(ACTION_CARD_PLAY_HOOK, _fake_fleetness_like_provider)
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire("V1", capacity=10, blood=5)
    pb.hand.append(
        LibraryCard(krcg_id=FAKE_FLEETNESS_KRCG_ID, name="Fake Fleetness", card_type="action")
    )
    builder.player("P2", pool=30).ready_vampire("B1", capacity=10, blood=0)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "fake_fleetness")
    actor.expect("maneuver_choice", "fake_pre_combat_maneuver")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    actor.assert_exhausted()
    defender.assert_exhausted()


def test_action_card_spec_maneuver_grant_threads_through_minion_phase_blocked():
    hooks.register(MANEUVER_HOOK, _provide_fake_pre_combat_maneuver)
    hooks.register(ACTION_CARD_PLAY_HOOK, _fake_fleetness_like_provider)
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire("V1", capacity=10, blood=5)
    pb.hand.append(
        LibraryCard(krcg_id=FAKE_FLEETNESS_KRCG_ID, name="Fake Fleetness", card_type="action")
    )
    builder.player("P2", pool=30).ready_vampire("B1", capacity=10, blood=0)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "fake_fleetness")
    actor.expect("maneuver_choice", "fake_pre_combat_maneuver")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    actor.assert_exhausted()
    defender.assert_exhausted()
