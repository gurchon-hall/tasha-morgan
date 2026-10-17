"""Block-attempt-time combat grant primitive (OQ-60, `docs/OPEN_QUESTIONS.md`,
resolved): a reaction played during the block attempt's own stealth/intercept
resolution (`engine/action.py::_duel_stealth_intercept`, before `run_combat`
even exists) must be able to hand a one-shot combat-time effect forward into
the *specific later* `run_combat` call for that same vampire, if (and only
if) the block succeeds and this same vampire ends up the blocker
[LSJ 20010813] -- never for a vampire that merely attempted and failed, and
never into a second/follow-up combat [LSJ 20010819-2].

Two cooperating primitives:

1. `engine/action.py::grant_block_time_combat_effect` records the grant into
   the block attempt's own `pending[PENDING_BLOCK_TIME_COMBAT_GRANT_KEY]`,
   keyed by the reacting vampire's own instance id; `perform_minion_action`
   forwards only the entry keyed by the vampire that ends up the successful
   `blocker` into that one `run_combat` call's own `initial_combat_state`
   (`engine/combat.py::seed_block_time_combat_grants`), re-earned fresh each
   time the reaction is actually played [LSJ 20010814-2].
2. `engine/damage.py::is_round_one` (round-scoped `ROUND_NUMBER_KEY`, written
   by `engine/combat.py::run_combat` at the top of each round) lets a
   `DAMAGE_PREVENTION_HOOK` provider gate a "round 1 of the resulting combat
   only" effect (e.g. Precognition, krcg 101475) -- distinct from, and
   necessary in addition to, the grant's own one-shot consumption, since an
   unconsumed grant (no damage occurred in round 1) must not still apply in
   round 2.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using trivial fake providers shaped like Precognition's own
superior clause ("this vampire can prevent 1 damage during the first round
of the resulting combat if they block") -- Precognition itself remains a
follow-up `card-implementer` pass (`src/vtesbot/cards/precognition.py` stays
`Status.BLOCKED` until that pass wires real hook providers).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import (
    INTERCEPT_MODIFIER_HOOK,
    PENDING_BLOCK_TIME_COMBAT_GRANT_KEY,
    grant_block_time_combat_effect,
    perform_minion_action,
)
from vtesbot.engine.combat import (
    BLOCK_TIME_COMBAT_GRANT_KEY,
    block_time_combat_grant_available,
    consume_block_time_combat_grant,
    consume_pre_combat_maneuver_grant,
    pre_combat_maneuver_available,
    run_combat,
    seed_block_time_combat_grants,
)
from vtesbot.engine.damage import ROUND_STATE_CONTEXT_KEY, is_round_one
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption

GRANT_NAME = "fake_round1_prevent"


# --- Helper functions' own degrade-gracefully / shape contract --------------


def test_block_time_combat_grant_available_degrades_gracefully_without_shared_state():
    """Mirrors `pre_combat_maneuver_available`'s own convention: a hook
    offered directly, bypassing `run_combat` (no `combat_state` in context at
    all), is treated as "nothing granted," not an error."""
    assert block_time_combat_grant_available({"vampire": "V1"}, GRANT_NAME) is False
    consume_block_time_combat_grant({"vampire": "V1"}, GRANT_NAME)  # must not raise


def test_grant_block_time_combat_effect_is_a_no_op_without_a_pending_dict():
    grant_block_time_combat_effect(None, "V1", GRANT_NAME)  # must not raise


def test_seed_block_time_combat_grants_shape_is_recognized_by_the_helpers():
    """Proves `seed_block_time_combat_grants`'s own output is exactly the
    shape `block_time_combat_grant_available`/`consume_block_time_combat_
    grant` recognize, and that a grant survives until consumed."""
    seed = seed_block_time_combat_grants({"V1": {GRANT_NAME: 1}})
    context = {"vampire": "V1", "combat_state": seed}

    assert block_time_combat_grant_available(context, GRANT_NAME) is True
    consume_block_time_combat_grant(context, GRANT_NAME)
    assert seed[BLOCK_TIME_COMBAT_GRANT_KEY]["V1"][GRANT_NAME] == 0
    assert block_time_combat_grant_available(context, GRANT_NAME) is False

    consume_block_time_combat_grant(context, GRANT_NAME)  # already 0: no-op
    assert seed[BLOCK_TIME_COMBAT_GRANT_KEY]["V1"][GRANT_NAME] == 0


def test_is_round_one_reads_the_round_number_run_combat_writes():
    """Direct unit coverage of `damage.py::is_round_one`'s own contract:
    missing `round_state` degrades to False (a hook offered outside
    `run_combat`), round 1 is True, any later round is False."""
    assert is_round_one(None) is False
    assert is_round_one({}) is False  # no ROUND_NUMBER_KEY written at all
    assert is_round_one({"round_number": 1}) is True
    assert is_round_one({"round_number": 2}) is False


def test_grant_block_time_combat_effect_accumulates_into_pending():
    """`grant_block_time_combat_effect` appends (never replaces); a second
    call for the same vampire/grant_name adds to the running count, and a
    distinct vampire gets its own independent entry."""
    pending: dict = {}
    grant_block_time_combat_effect(pending, "V1", GRANT_NAME)
    grant_block_time_combat_effect(pending, "V1", GRANT_NAME)
    grant_block_time_combat_effect(pending, "V2", GRANT_NAME)

    grants = pending[PENDING_BLOCK_TIME_COMBAT_GRANT_KEY]
    assert grants["V1"][GRANT_NAME] == 2
    assert grants["V2"][GRANT_NAME] == 1


# --- `run_combat`'s own `initial_combat_state` seeding, direct -------------


def _fake_round1_prevention_provider(state, context):
    """Generic stand-in for Precognition's own superior clause: "prevent 1
    damage during the first round of the resulting combat if they block" --
    gates on *both* `is_round_one` and the seeded grant, never just one."""
    del state
    round_state = context.get(ROUND_STATE_CONTEXT_KEY)
    if not is_round_one(round_state):
        return []
    if not block_time_combat_grant_available(context, GRANT_NAME):
        return []
    damage_box = context["damage"]
    if damage_box.get("normal", 0) <= 0:
        return []

    def _apply(s):
        del s
        consume_block_time_combat_grant(context, GRANT_NAME)
        damage_box["normal"] = max(0, damage_box["normal"] - 1)

    return [HookOption(choice=Choice("fake_prevent_1", "Prevent 1 damage"), apply=_apply)]


def _combat_scenario():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=10, blood=5)
    builder.player("P2", pool=30).ready_vampire("D1", capacity=10, blood=0)
    return builder.build()


def test_round_one_gate_suppresses_an_unused_grant_once_round_two_starts():
    """The grant alone (unconsumed in round 1, since no damage landed) is
    *not* enough to also apply in round 2 -- `is_round_one` must suppress the
    option even though `block_time_combat_grant_available` would still read
    True. Proves the round-number signal is load-bearing, not redundant with
    the grant's own one-shot consumption."""
    hooks.register("damage_prevention", _fake_round1_prevention_provider)
    game = _combat_scenario()
    seed = seed_block_time_combat_grants({"D1": {GRANT_NAME: 1}})

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "no_strike")  # round 1: no damage at all
    actor.expect("press", "press")
    actor.expect("press", "end_combat")
    actor.expect("strike_choice", "hand_strike")  # round 2: 1 damage to D1
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("A1"), "P2", game.vampire("D1"), seed)

    actor.assert_exhausted()
    defender.assert_exhausted()
    assert game.vampire("D1").wounded is True  # round 2's damage was not prevented
    # Never consumed: the round-1 gate suppressed the option entirely in
    # round 1 (nothing to prevent) and again in round 2 (wrong round), not
    # merely declined.
    assert seed[BLOCK_TIME_COMBAT_GRANT_KEY]["D1"][GRANT_NAME] == 1


def test_seeded_grant_prevents_damage_in_round_one():
    """Zero-regression companion: the same seed, consulted in round 1 while
    damage is actually dealt, is offered and consumed."""
    hooks.register("damage_prevention", _fake_round1_prevention_provider)
    game = _combat_scenario()
    seed = seed_block_time_combat_grants({"D1": {GRANT_NAME: 1}})

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("damage_prevention", "fake_prevent_1")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("A1"), "P2", game.vampire("D1"), seed)

    actor.assert_exhausted()
    defender.assert_exhausted()
    assert game.vampire("D1").wounded is False  # prevented
    assert seed[BLOCK_TIME_COMBAT_GRANT_KEY]["D1"][GRANT_NAME] == 0  # consumed


# --- `perform_minion_action`'s own forwarding, end to end -------------------


def _fake_reaction_intercept_and_grant(vampire_id: str, *, bonus: int):
    """Stand-in for Precognition's own superior clause offered during the
    block attempt's stealth/intercept ping-pong: grants intercept *and*
    records a block-time combat grant for the specific reacting vampire, via
    its own provider `context["pending"]` -- the convention every real
    card's provider would use."""
    used = [False]

    def provider(state, context):
        del state
        if context.get("blocking_vampire") != vampire_id or used[0]:
            return []
        pending = context.get("pending")

        def _apply(s):
            del s
            used[0] = True
            grant_block_time_combat_effect(pending, vampire_id, GRANT_NAME)
            return bonus

        return [
            HookOption(
                choice=Choice(f"reaction:{vampire_id}", f"+{bonus} intercept ({vampire_id})"),
                apply=_apply,
            )
        ]

    return provider


def test_perform_minion_action_forwards_the_grant_only_for_the_successful_blocker():
    """End-to-end proof through the real `perform_minion_action` entry point:
    the reacting vampire's own grant, recorded mid-block-attempt, survives
    into the resulting combat's round 1 and prevents damage -- exactly the
    two-primitive composition OQ-60 describes."""
    hooks.register(INTERCEPT_MODIFIER_HOOK, _fake_reaction_intercept_and_grant("D1", bonus=2))
    hooks.register("damage_prevention", _fake_round1_prevention_provider)
    game = _combat_scenario()
    acting_vampire = game.vampire("A1")

    def resolve(pending):
        del pending
        raise AssertionError("must not resolve unblocked: the attempt succeeds")

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:D1")
    defender.expect(INTERCEPT_MODIFIER_HOOK, "reaction:D1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("damage_prevention", "fake_prevent_1")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(game.state, "P1", "P2", acting_vampire, base_stealth=2, resolve=resolve)

    actor.assert_exhausted()
    defender.assert_exhausted()
    assert game.vampire("D1").wounded is False  # prevented


def test_perform_minion_action_drops_the_grant_when_a_different_vampire_blocks():
    """The reacting vampire (D1) plays the reaction but still fails to
    block (insufficient intercept even with the bonus); a second vampire
    (D2) blocks instead, via its own unrelated intercept bonus, never having
    recorded any grant for itself. The grant recorded for D1 must not leak
    onto D2's own combat."""
    hooks.register(INTERCEPT_MODIFIER_HOOK, _fake_reaction_intercept_and_grant("D1", bonus=2))

    def d2_bonus_provider(state, context):
        del state
        if context.get("blocking_vampire") != "D2":
            return []
        return [HookOption(choice=Choice("reaction:D2", "+10 intercept (D2)"), apply=lambda s: 10)]

    hooks.register(INTERCEPT_MODIFIER_HOOK, d2_bonus_provider)
    hooks.register("damage_prevention", _fake_round1_prevention_provider)

    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("A1", capacity=10, blood=5)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("D1", capacity=10, blood=0)
    p2.ready_vampire("D2", capacity=10, blood=0)
    game = builder.build()
    acting_vampire = game.vampire("A1")

    def resolve(pending):
        del pending
        raise AssertionError("must not resolve unblocked: D2's attempt succeeds")

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:D1")
    defender.expect(INTERCEPT_MODIFIER_HOOK, "reaction:D1")  # D1: 0 + 2 = 2 < 5, still fails
    defender.expect("block_attempt", "block_with:D2")
    defender.expect(INTERCEPT_MODIFIER_HOOK, "reaction:D2")  # D2: 0 + 10 = 10 >= 5, succeeds
    defender.expect("strike_choice", "no_strike")
    # No "damage_prevention" decision: D2 carries no grant of its own.
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(game.state, "P1", "P2", acting_vampire, base_stealth=5, resolve=resolve)

    actor.assert_exhausted()
    defender.assert_exhausted()
    assert game.vampire("D2").wounded is True  # not prevented: no grant of its own
    assert game.vampire("D1").zone == "ready"  # failed attempt: never entered combat
    assert game.vampire("D1").locked is False


def test_perform_minion_action_blocked_branch_without_any_grant_offers_nothing():
    """Zero-regression check: no `INTERCEPT_MODIFIER_HOOK` provider writing
    into `PENDING_BLOCK_TIME_COMBAT_GRANT_KEY` (every existing card/test
    before this pass) leaves `initial_combat_state` exactly as `maneuver_
    grant`-only behaviour already proved (`tests/rules/test_pre_combat_
    maneuver_grant.py`) -- the new merge step is a no-op when there is
    nothing to merge."""
    hooks.register("damage_prevention", _fake_round1_prevention_provider)
    game = _combat_scenario()
    acting_vampire = game.vampire("A1")

    def resolve(pending):
        del pending

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:D1")
    defender.expect("strike_choice", "no_strike")
    # No "damage_prevention" decision: nothing was ever granted.
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(game.state, "P1", "P2", acting_vampire, base_stealth=0, resolve=resolve)

    actor.assert_exhausted()
    defender.assert_exhausted()
    assert game.vampire("D1").wounded is True  # ordinary, unprevented hand-strike damage


def test_perform_minion_action_merges_a_block_time_grant_alongside_a_maneuver_grant():
    """The two `initial_combat_state` seeds (OQ-25's `maneuver_grant`
    parameter and OQ-60's own pending-forwarded grant) use distinct
    top-level keys and must both survive the merge in `perform_minion_
    action` -- neither silently overwrites the other."""

    def maneuver_provider(state, context):
        del state
        if not pre_combat_maneuver_available(context):
            return []

        def use(s):
            del s
            consume_pre_combat_maneuver_grant(context)

        return [HookOption(choice=Choice("fake_maneuver", "Pre-combat maneuver"), apply=use)]

    hooks.register("maneuver", maneuver_provider)
    hooks.register(INTERCEPT_MODIFIER_HOOK, _fake_reaction_intercept_and_grant("D1", bonus=2))
    hooks.register("damage_prevention", _fake_round1_prevention_provider)
    game = _combat_scenario()
    acting_vampire = game.vampire("A1")

    def resolve(pending):
        del pending
        raise AssertionError("must not resolve unblocked")

    actor = ScriptedAgent("P1")
    actor.expect("maneuver_choice", "fake_maneuver")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:D1")
    defender.expect(INTERCEPT_MODIFIER_HOOK, "reaction:D1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("damage_prevention", "fake_prevent_1")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(
        game.state,
        "P1",
        "P2",
        acting_vampire,
        base_stealth=2,
        resolve=resolve,
        maneuver_grant=acting_vampire.instance_id,
    )

    actor.assert_exhausted()
    defender.assert_exhausted()
    assert game.vampire("D1").wounded is False  # both seeds took effect together
