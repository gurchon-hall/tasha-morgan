"""`WAKE_LOCKED_MINION_HOOK` (OQ-48, `docs/OPEN_QUESTIONS.md`, resolved):
`INTERCEPT_DECREASE_HOOK`/`STEALTH_INCREASE_HOOK`'s defender-side sibling in
`engine/action.py::attempt_block`'s retry loop, offered to `defender`
strictly before `state.ready_unlocked_vampires(defender)` is (re)computed
each time around, so a chosen option's own `apply` setting `VampireInPlay.
woken = True` on one of the defender's own locked vampires is picked up by
that very computation -- the moment On the Qui Vive's (krcg id 101321) own
primary "attempting to block" clause needs, on top of OQ-46's own
`woken`/`is_ready_unlocked` primitive.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism* only, using a fake stub provider -- On the Qui Vive's own card
module remains `card-implementer`'s job once this capability exists; it
stays registered `blocked`/`OQ-48`.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import WAKE_LOCKED_MINION_HOOK, attempt_block
from vtesbot.engine.allies import recruit_ally
from vtesbot.engine.decision import Choice


def test_hook_fires_for_defender_before_candidates_are_computed():
    """Queried even though `defender` (P2) has zero vampires at all -- i.e.
    strictly before `attempt_block`'s own "nothing legal to block with: no
    vacuous decision raised" short-circuit, which would otherwise return
    `None` without ever consulting this hook."""
    calls: list[str] = []

    def provider(state, context):
        del state
        calls.append(context["player"])
        return []

    hooks.register(WAKE_LOCKED_MINION_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    game.state.agents["P2"] = ScriptedAgent("P2")  # no decision expected

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None
    assert calls == ["P2"]


def test_choosing_to_wake_a_locked_vampire_makes_it_an_ordinary_block_candidate():
    """The chosen option's own `apply` mutation (`woken = True`) is picked up
    by that same `attempt_block` call's own `ready_unlocked_vampires(defender)`
    computation right after -- a fully ordinary, stealth/intercept-subject
    candidate, not an unconditional success (`base_stealth=0` here succeeds
    only because intercept's own baseline is also 0, same as any other
    candidate, never because of the wake itself)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, locked=True)
    game = builder.build()

    def provider(state, context):
        if context["player"] != "P2":
            return []
        b1 = state.players["P2"].vampires["B1"]
        if b1.woken:
            return []

        def apply(s):
            del s
            b1.woken = True

        return [hooks.HookOption(choice=Choice("wake_b1", "Wake B1"), apply=apply)]

    hooks.register(WAKE_LOCKED_MINION_HOOK, provider)
    defender = ScriptedAgent("P2")
    defender.expect("wake_locked_minion", "wake_b1")
    defender.expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    assert blocker.instance_id == "B1"
    assert game.vampire("B1").locked is True  # "while remaining structurally locked"
    defender.assert_exhausted()


def test_apply_can_set_an_allys_skip_next_unlock_reusing_oq46s_own_field():
    """On the Qui Vive's own ally footnote ("If this minion is an ally, they
    do not unlock as normal during their next unlock phase") reuses OQ-46's
    own `AllyInPlay.skip_next_unlock` field rather than a duplicate -- an
    ally is never itself offered as a block candidate in this engine (out of
    scope, OQ-46's own solution note), so this is exercised directly through
    the hook's generic "apply just mutates state" contract, independent of
    `attempt_block`'s own (here empty) vampire candidate list."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    ally = recruit_ally(game.state, "P2", krcg_id=1, name="Some Ally", life=1)
    assert ally.locked is True
    assert ally.skip_next_unlock is False

    def provider(state, context):
        del state
        if context["player"] != "P2" or ally.skip_next_unlock:
            return []

        def apply(s):
            del s
            ally.skip_next_unlock = True

        return [hooks.HookOption(choice=Choice("wake_ally", "Wake the ally"), apply=apply)]

    hooks.register(WAKE_LOCKED_MINION_HOOK, provider)
    defender = ScriptedAgent("P2").expect("wake_locked_minion", "wake_ally")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is None  # no vampire candidates at all: an ally cannot block
    assert ally.skip_next_unlock is True
    defender.assert_exhausted()


def test_declining_then_retrying_reoffers_the_hook():
    """Mirrors OQ-11's precedent for `INTERCEPT_DECREASE_HOOK`/
    `STEALTH_INCREASE_HOOK`: a failed block attempt loops `attempt_block`
    back to the top of its retry loop, where this hook is offered again --
    the defender declines first, lets B1's own attempt fail, then wakes B2
    on the retry."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3).ready_vampire(
        "B2", capacity=3, locked=True
    )
    game = builder.build()

    def provider(state, context):
        if context["player"] != "P2":
            return []
        b2 = state.players["P2"].vampires["B2"]
        if b2.woken:
            return []

        def apply(s):
            del s
            b2.woken = True

        return [hooks.HookOption(choice=Choice("wake_b2", "Wake B2"), apply=apply)]

    hooks.register(WAKE_LOCKED_MINION_HOOK, provider)
    defender = ScriptedAgent("P2")
    defender.expect("wake_locked_minion", "pass")  # 1st time around: decline to wake yet
    defender.expect("block_attempt", "block_with:B1")  # fails: stealth 1 > intercept 0
    defender.expect("wake_locked_minion", "wake_b2")  # retry: hook re-offered
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=1)

    assert blocker is None
    assert game.vampire("B2").woken is True
    defender.assert_exhausted()
