"""Forced block from a locked vampire (OQ-26, `docs/OPEN_QUESTIONS.md`,
resolved): `engine/action.py::attempt_block` offers `BLOCK_CANDIDATE_
INJECTION_HOOK` to the defender, alongside its own hardcoded
`state.ready_unlocked_vampires(defender)` candidates, so a registered
provider can contribute an extra candidate drawn from one of the
defender's own currently-*locked* vampires. Choosing that candidate (a)
unlocks it, (b) is an immediate, unconditional *successful* block --
never runs `_duel_stealth_intercept`'s "only when needed" ping-pong -- and
(c) leads straight to combat, exactly like a normal successful block.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a trivial fake `BLOCK_CANDIDATE_INJECTION_HOOK`
provider (not Organized Resistance, krcg 102230, itself -- that remains
`card-implementer`'s job once this capability exists; it stays registered
`blocked`/`OQ-26` until then).
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import (
    BLOCK_CANDIDATE_INJECTION_HOOK,
    attempt_block,
    perform_minion_action,
)
from vtesbot.engine.decision import Choice


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def _fake_forced_block_provider(state, context):
    """Generic stand-in for OQ-26's "unlock a locked minion you control; it
    attempts to block, even if intercept is not yet needed" shape: offers
    every one of the defender's own currently-locked, ready vampires as a
    forced-block candidate. `apply` unlocks the chosen one and returns it,
    exactly the contract `BLOCK_CANDIDATE_INJECTION_HOOK` documents."""
    defender = context["defender"]
    locked = [
        v for v in state.players[defender].vampires.values() if v.zone == "ready" and v.locked
    ]
    options = []
    for vampire in locked:

        def _apply(s, vampire=vampire):
            del s
            vampire.locked = False
            return vampire

        options.append(
            hooks.HookOption(
                choice=Choice(
                    f"forced_block:{vampire.instance_id}",
                    f"Unlock and force-block with {vampire.card.name}",
                ),
                apply=_apply,
            )
        )
    return options


def _locked_blocker_game():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    # blood=0 on B1: no blood to mend damage with, so the combat test below
    # does not also need to script a "mend_damage" decision.
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0, locked=True)
    return builder.build()


def test_locked_vampire_can_be_injected_unlocked_and_force_blocks_unconditionally():
    """B1 is locked, so `state.ready_unlocked_vampires` excludes it entirely
    -- the injected option is the *only* block candidate offered besides
    decline. Choosing it unlocks B1 and `attempt_block` returns it directly
    as a successful blocker. `base_stealth=5` would fail every ordinary
    stealth/intercept attempt (intercept is hardcoded 0 this milestone),
    proving this path never consults `_duel_stealth_intercept` at all."""
    hooks.register(BLOCK_CANDIDATE_INJECTION_HOOK, _fake_forced_block_provider)
    game = _locked_blocker_game()
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "forced_block:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=5)

    assert blocker is not None
    assert blocker.instance_id == "B1"
    assert game.vampire("B1").locked is False  # unlocked as part of being chosen
    defender.assert_exhausted()


def test_injected_candidate_leads_to_combat_through_perform_minion_action():
    """End-to-end through the real call site `card-implementer` will use:
    `perform_minion_action`'s blocked branch needs no changes at all --
    combat runs against the unlocked B1 exactly as it would against any
    other successful blocker, and `resolve()` (the unblocked callback)
    never runs."""
    hooks.register(BLOCK_CANDIDATE_INJECTION_HOOK, _fake_forced_block_provider)
    game = _locked_blocker_game()
    acting = game.vampire("V1")
    resolve_calls: list[bool] = []

    def resolve(pending):
        del pending
        resolve_calls.append(True)

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "forced_block:B1")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(game.state, "P1", "P2", acting, 5, resolve)

    assert resolve_calls == []  # blocked branch: resolve() never ran
    actor.assert_exhausted()
    defender.assert_exhausted()
    # perform_minion_action re-locks the (now-unlocked) blocker for combat,
    # exactly like the normal successful-block path.
    assert game.vampire("B1").locked is True


def test_zero_regression_ordinary_block_path_unaffected_when_no_provider_registered():
    """No `BLOCK_CANDIDATE_INJECTION_HOOK` provider registered (the case for
    every existing test and every other card today): the ordinary
    ready-unlocked block path is byte-for-byte unchanged -- `hooks.offer`
    returns `[]` and the only candidate offered is the normal one."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    assert blocker.instance_id == "B1"
    defender.assert_exhausted()


def test_zero_regression_no_candidates_and_no_injection_still_returns_none_without_a_decision():
    """No ready-unlocked vampires and no injection provider registered: the
    original "no vacuous decision raised" short-circuit still fires -- the
    `ScriptedAgent` (with nothing queued) proves no decision was asked."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, locked=True)
    game = builder.build()
    defender = ScriptedAgent("P2")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    defender.assert_exhausted()
