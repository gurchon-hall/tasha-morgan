"""Bleed-amount hook wiring (`engine/hooks.py`, CLAUDE.md milestone-3
scaffolding pass; `engine/phases/minion.py`): `"bleed_amount_fixed_modifier"`
(passive, mandatory -- an unconditional printed bonus such as a vampire's
flat "+1 bleed" text) and `"bleed_amount_modifier"` (the optional, two-sided
impulse window for library cards like Bonding/Threats/Telepathic Counter).
No such card is implemented yet -- scenario tests for the mechanism only.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.minion import minion_phase


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def _bleed_game():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    return builder.build()


def test_fixed_bleed_modifier_adds_to_the_base_bleed_amount():
    """Stands in for a vampire's unconditional flat "+1 bleed" printed text
    (e.g. Diana Iadanza, Lucinde Alastor, Queen Anne) -- mandatory, so no
    decision is raised for it (CLAUDE.md rule 3's "mandatory effects")."""
    hooks.register(
        "bleed_amount_fixed_modifier",
        lambda state, context: 1 if context.get("player") == "P1" else 0,
    )
    game = _bleed_game()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30 - 2  # base 1 + the fixed modifier's 1
    actor.assert_exhausted()


def test_bleed_amount_modifier_window_lets_the_actor_add_bleed():
    def fake_bleed_card(state, context):
        if context.get("player") != "P1":
            return []
        amount_box = context["amount"]

        def _apply(s):
            amount_box[0] += 2

        return [hooks.HookOption(choice=Choice("use_fake_bleed_card", "+2 bleed"), apply=_apply)]

    hooks.register("bleed_amount_modifier", fake_bleed_card)
    game = _bleed_game()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("bleed_amount_modifier", "use_fake_bleed_card")
    # The fake provider is not one-shot (always offers itself): the actor
    # must explicitly pass once they are done adding ("only when needed").
    actor.expect("bleed_amount_modifier", "pass")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30 - 3  # base 1 + the card's +2
    actor.assert_exhausted()


def test_bleed_amount_modifier_window_lets_the_defender_reduce_bleed():
    def fake_reduction_card(state, context):
        if context.get("player") != "P2":
            return []
        amount_box = context["amount"]

        def _apply(s):
            amount_box[0] -= 1

        return [
            hooks.HookOption(choice=Choice("use_fake_reduction_card", "-1 bleed"), apply=_apply)
        ]

    hooks.register("bleed_amount_modifier", fake_reduction_card)
    game = _bleed_game()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("bleed_amount_modifier", "use_fake_reduction_card")
    defender.expect("bleed_amount_modifier", "pass")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # base 1, reduced to 0: no pool lost, no edge change
    assert game.state.edge_holder is None
    actor.assert_exhausted()
    defender.assert_exhausted()
