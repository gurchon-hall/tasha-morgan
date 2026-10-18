"""`attempt_block`'s/`perform_minion_action`'s `BLOCK_ATTEMPT_COST_HOOK`
(`engine/action.py::BlockAttemptCost`): a passive, per-candidate, mandatory
cost gate on attempting to block a specific actor -- distinct from
`block_candidate_predicate` (a stateless, per-action-card property filter,
see `test_block_candidate_predicate.py`): this one is registered globally
by a crypt card (its ability applies across every action type it ever
performs), and it actually deducts a resource the instant a qualifying
candidate is chosen to attempt, independent of whether the stealth/
intercept duel that follows then succeeds or fails.

Motivating source: Sergio Bueno (krcg 201662, `src/vtesbot/cards/
sergio_bueno.py`, still `Status.BLOCKED` pending this primitive): "Minions
with 1 or more of your corruption counters must burn 1 blood or life to
attempt to block Sergio." -- "to attempt", not "to block successfully", is
why `pay` must run on selection, not on success (see `BlockAttemptCost`'s
own docstring for the full citation chain). Per the `rules-scenario-test`
skill: these are scenario tests for the *mechanism*, using a trivial fake
provider gated on one named candidate instead of corruption counters --
wiring Sergio Bueno's own corruption-counter-specific gate remains a
`card-implementer` pass; this file proves the primitive alone.

CLAUDE.md §5 "mandatory effects defined by the rules": the cost is never
offered as its own `Decision` -- a candidate either affords it and pays
automatically on selection, or cannot afford it and is not offered as a
block candidate at all.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import (
    BLOCK_ATTEMPT_COST_HOOK,
    BLOCK_CANDIDATE_INJECTION_HOOK,
    BlockAttemptCost,
    attempt_block,
    perform_minion_action,
)
from vtesbot.engine.decision import Choice


def _fake_gated_cost_provider(gated_instance_id: str, amount: int = 1):
    """Generic stand-in for Sergio Bueno's own "must burn 1 blood ... to
    attempt to block" passive, gated here on one named candidate instead of
    "1+ corruption counters placed by Sergio's own controller" -- the
    corruption-counter-specific gating is out of scope for this mechanism
    test (see `src/vtesbot/cards/sergio_bueno.py`'s own module docstring)."""

    def provider(state, context):
        if context["candidate"] != gated_instance_id:
            return None
        vampire = state.players[context["defender"]].vampires[gated_instance_id]

        def pay(s):
            del s
            vampire.blood -= amount

        return BlockAttemptCost(can_pay=vampire.blood >= amount, pay=pay)

    return provider


def _injection_provider_for(target_instance_id: str):
    """Mirrors `test_block_candidate_predicate.py`'s own stand-in for
    Second Tradition: Domain's/Organized Resistance's "unlock and force
    block" shape."""

    def injection_provider(state, context):
        del state

        def apply(s):
            vampire = s.players[context["defender"]].vampires[target_instance_id]
            vampire.locked = False
            return vampire

        return [
            hooks.HookOption(
                choice=Choice(
                    f"forced_block:{target_instance_id}",
                    f"Unlock and force-block with {target_instance_id}",
                ),
                apply=apply,
                block_candidate_instance_id=target_instance_id,
            )
        ]

    return injection_provider


def test_unaffordable_candidate_is_not_offered_at_all():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    hooks.register(BLOCK_ATTEMPT_COST_HOOK, _fake_gated_cost_provider("B1"))
    game.state.agents["P2"] = ScriptedAgent("P2")  # no block_attempt decision at all

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    assert game.vampire("B1").blood == 0  # never charged: never chosen


def test_cost_is_paid_the_instant_chosen_even_if_the_attempt_then_fails():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    hooks.register(BLOCK_ATTEMPT_COST_HOOK, _fake_gated_cost_provider("B1"))
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=5)

    assert blocker is None  # stealth 5 > intercept 0, no modifier available: attempt fails
    assert game.vampire("B1").blood == 0  # cost paid regardless of the attempt's own outcome
    defender.assert_exhausted()


def test_cost_is_paid_when_the_attempt_succeeds():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    hooks.register(BLOCK_ATTEMPT_COST_HOOK, _fake_gated_cost_provider("B1"))
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    assert blocker.instance_id == "B1"
    assert game.vampire("B1").blood == 0
    defender.assert_exhausted()


def test_cost_recomputed_fresh_each_retry_charges_again_until_unaffordable():
    """Not a one-time toll: each separate attempt by the same candidate
    pays again, proving the cost is re-queried live on every pass through
    `attempt_block`'s own retry loop, same convention as
    `block_candidate_predicate` -- a candidate with 2 blood survives one
    failed attempt (down to 1), is still offered and pays a second time
    (down to 0), then is excluded once truly unaffordable."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=2)
    game = builder.build()
    hooks.register(BLOCK_ATTEMPT_COST_HOOK, _fake_gated_cost_provider("B1"))
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=5)

    assert blocker is None  # every attempt fails (stealth 5 > intercept 0)
    assert game.vampire("B1").blood == 0  # charged once per attempt, not once total
    defender.assert_exhausted()


def test_composes_with_block_candidate_predicate_excluded_first_never_costed():
    def _not_titled(vampire) -> bool:
        return vampire.card.title is None

    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Prince")
    game = builder.build()
    hooks.register(BLOCK_ATTEMPT_COST_HOOK, _fake_gated_cost_provider("B1"))
    game.state.agents["P2"] = ScriptedAgent("P2")  # excluded by predicate: no decision at all

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, block_candidate_predicate=_not_titled
    )

    assert blocker is None
    assert game.vampire("B1").blood == 1  # never queried for a cost: predicate excluded it first


def test_injected_block_candidate_also_pays_the_cost_when_chosen():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, locked=True)
    game = builder.build()
    hooks.register(BLOCK_CANDIDATE_INJECTION_HOOK, _injection_provider_for("B1"))
    hooks.register(BLOCK_ATTEMPT_COST_HOOK, _fake_gated_cost_provider("B1"))
    game.state.agents["P1"] = ScriptedAgent("P1")
    defender = ScriptedAgent("P2").expect("block_attempt", "forced_block:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    assert blocker.instance_id == "B1"
    assert blocker.locked is False
    assert game.vampire("B1").blood == 0  # cost paid on the injected path too
    defender.assert_exhausted()


def test_injected_block_candidate_excluded_when_it_cannot_afford_the_cost():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0, locked=True)
    game = builder.build()
    hooks.register(BLOCK_CANDIDATE_INJECTION_HOOK, _injection_provider_for("B1"))
    hooks.register(BLOCK_ATTEMPT_COST_HOOK, _fake_gated_cost_provider("B1"))
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")  # excluded: no decision at all

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    assert game.vampire("B1").locked is True  # never unlocked: the injected apply never ran


def test_perform_minion_action_pays_the_cost_through_the_real_call_site():
    """Real call site proof (`perform_minion_action`'s own retry loop, not
    just `attempt_block` directly): the cost is paid even though the
    candidate's lone attempt then fails and the action resolves unblocked
    -- "to attempt", not "to succeed"."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    acting = game.vampire("V1")
    hooks.register(BLOCK_ATTEMPT_COST_HOOK, _fake_gated_cost_provider("B1"))
    game.state.agents["P1"] = ScriptedAgent("P1")
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender
    resolve_calls: list[bool] = []

    def resolve(pending):
        del pending
        resolve_calls.append(True)

    perform_minion_action(game.state, "P1", "P2", acting, base_stealth=5, resolve=resolve)

    assert resolve_calls == [True]  # unblocked: the lone candidate's attempt failed
    assert game.vampire("B1").blood == 0  # cost still paid: "to attempt", not "to succeed"
    defender.assert_exhausted()


def test_zero_regression_no_cost_provider_leaves_candidate_list_unaffected():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    assert blocker.instance_id == "B1"
    defender.assert_exhausted()
