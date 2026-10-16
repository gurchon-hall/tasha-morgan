"""`attempt_block`'s/`perform_minion_action`'s `block_candidate_predicate`
parameter and `engine/phases/minion.py::ActionCardSpec.block_candidate_
predicate` (`engine/action.py`): an unconditional, property-based
block-candidate filter tied to *the acting action's own printed text* --
distinct from `BLOCK_CANDIDATE_EXCLUSION_HOOK`'s actor-chosen, per-vampire
`instance_id` set, which is seeded reactively from inside `attempt_block`'s
own retry loop. This predicate instead arrives already bound into
`ActionCardSpec` before `perform_minion_action` even creates its own
per-action `pending` dict, and is re-evaluated fresh on every retry (never
a frozen snapshot).

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a trivial fake predicate (any ready-unlocked vampire
with no printed title) standing in for Propaganda's own "Titled vampires
cannot block this action." (krcg 101495) -- that card's own wiring remains
`card-implementer`'s job once this capability exists; it stays registered
`blocked` until then.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import (
    BLOCK_CANDIDATE_EXCLUSION_HOOK,
    BLOCK_CANDIDATE_INJECTION_HOOK,
    PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY,
    WAKE_LOCKED_MINION_HOOK,
    attempt_block,
    perform_minion_action,
)
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, ActionCardSpec, minion_phase


def _not_titled(vampire) -> bool:
    """Generic stand-in for Propaganda's own "titled vampires cannot
    block" property test."""
    return vampire.card.title is None


def test_predicate_filters_the_hardcoded_candidate_list():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1, title="Prince")
    p2.ready_vampire("B2", capacity=3, blood=1)
    game = builder.build()
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B2")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, block_candidate_predicate=_not_titled
    )

    assert blocker is not None
    assert blocker.instance_id == "B2"
    defender.assert_exhausted()


def test_predicate_excludes_every_candidate_leaves_no_decision():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Prince")
    game = builder.build()
    game.state.agents["P2"] = ScriptedAgent("P2")  # no block_attempt decision at all

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, block_candidate_predicate=_not_titled
    )

    assert blocker is None


def test_predicate_is_reevaluated_fresh_after_wake_locked_minion_hook():
    """A titled vampire woken mid-loop via `WAKE_LOCKED_MINION_HOOK`
    becomes `is_ready_unlocked`, but the predicate still excludes it on
    the very same retry -- proving this is a live, per-retry check, not a
    frozen snapshot taken before the loop started."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire(
        "B1", capacity=3, blood=1, title="Prince", locked=True
    )
    game = builder.build()

    def wake_provider(state, context):
        if context["player"] != "P2":
            return []
        b1 = state.players["P2"].vampires["B1"]
        if b1.woken:
            return []

        def apply(s):
            del s
            b1.woken = True

        return [hooks.HookOption(choice=Choice("wake_b1", "Wake B1"), apply=apply)]

    hooks.register(WAKE_LOCKED_MINION_HOOK, wake_provider)
    game.state.agents["P1"] = ScriptedAgent("P1")
    defender = ScriptedAgent("P2").expect("wake_locked_minion", "wake_b1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, block_candidate_predicate=_not_titled
    )

    assert blocker is None  # B1 woken, but still titled: never a candidate
    assert game.vampire("B1").woken is True  # the wake itself still happened
    defender.assert_exhausted()


def _injection_provider_for(target_instance_id: str):
    """Mirrors `test_block_candidate_exclusion.py`'s own stand-in for
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


def test_predicate_also_filters_an_injected_block_candidate():
    """A titled vampire named by a `BLOCK_CANDIDATE_INJECTION_HOOK`
    provider (e.g. Second Tradition: Domain, Organized Resistance) must
    not be force-blockable either -- "Titled vampires cannot block this
    action" means by any means, hardcoded or injected."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire(
        "B1", capacity=3, blood=1, title="Prince", locked=True
    )
    game = builder.build()
    hooks.register(BLOCK_CANDIDATE_INJECTION_HOOK, _injection_provider_for("B1"))
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")  # injected option filtered: no decision

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, block_candidate_predicate=_not_titled
    )

    assert blocker is None
    assert game.vampire("B1").locked is True  # never unlocked: the injected apply never ran


def test_predicate_composes_with_block_candidate_exclusion_hook():
    """Both mechanisms apply together: a non-titled vampire named by
    `BLOCK_CANDIDATE_EXCLUSION_HOOK` is still excluded even though it
    passes the predicate, and a titled vampire is still excluded by the
    predicate even with no exclusion-hook provider naming it."""

    def exclude_b2(state, context):
        del state
        pending = context["pending"]
        if "B2" in pending.get(PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY, set()):
            return []

        def apply(s):
            del s
            pending.setdefault(PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY, set()).add("B2")

        return [hooks.HookOption(choice=Choice("exclude:B2", "Exclude B2"), apply=apply)]

    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("B1", capacity=3, blood=1, title="Prince")  # excluded by predicate
    p2.ready_vampire("B2", capacity=3, blood=1)  # excluded by the exclusion hook
    p2.ready_vampire("B3", capacity=3, blood=1)  # neither: still a legal candidate
    game = builder.build()
    hooks.register(BLOCK_CANDIDATE_EXCLUSION_HOOK, exclude_b2)
    actor = ScriptedAgent("P1").expect("block_candidate_exclusion", "exclude:B2")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B3")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, block_candidate_predicate=_not_titled
    )

    assert blocker is not None
    assert blocker.instance_id == "B3"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_zero_regression_no_predicate_leaves_candidate_list_unaffected():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Prince")
    game = builder.build()
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(game.state, "P1", "P2", base_stealth=0)

    assert blocker is not None
    assert blocker.instance_id == "B1"
    defender.assert_exhausted()


def test_perform_minion_action_forwards_the_predicate():
    """Real call site proof (`perform_minion_action`'s own parameter, not
    just `attempt_block`'s): a titled defender vampire is excluded through
    the full action-resolution path."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0, title="Prince")
    game = builder.build()
    acting = game.vampire("V1")
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")  # B1 excluded: no decision at all
    resolve_calls: list[bool] = []

    def resolve(pending):
        del pending
        resolve_calls.append(True)

    perform_minion_action(
        game.state,
        "P1",
        "P2",
        acting,
        base_stealth=0,
        resolve=resolve,
        block_candidate_predicate=_not_titled,
    )

    assert resolve_calls == [True]


def _provide_fake_action_card_with_predicate(state, context):
    """Stand-in for a future `ACTION_CARD_PLAY_HOOK` provider (e.g.
    Propaganda) whose own `ActionCardSpec` carries a `block_candidate_
    predicate`."""
    player = context["player"]
    vampire = state.players[player].vampires.get(context["vampire"])
    if vampire is None:
        return []

    def _apply(s):
        del s

        def resolve(pending):
            del pending

        return ActionCardSpec(
            base_stealth=0,
            directed=True,
            resolve=resolve,
            block_candidate_predicate=_not_titled,
        )

    return [
        hooks.HookOption(choice=Choice("fake_action_card", "Play fake action card"), apply=_apply)
    ]


def test_action_card_spec_predicate_reaches_attempt_block_end_to_end():
    """End-to-end through `minion_phase`/`_choose_and_perform_action`/
    `_perform_action_card`: `ActionCardSpec.block_candidate_predicate` set
    by an `ACTION_CARD_PLAY_HOOK` provider's own `apply()` actually excludes
    a titled defender vampire when the card is played for real."""
    hooks.register(ACTION_CARD_PLAY_HOOK, _provide_fake_action_card_with_predicate)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Prince")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "fake_action_card")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")  # B1 excluded: no block decision at all

    minion_phase(game.state, "P1")

    actor.assert_exhausted()
