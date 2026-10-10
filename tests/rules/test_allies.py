"""Allies in play (OQ-7, `docs/OPEN_QUESTIONS.md`): `engine/state.py::
AllyInPlay` / `PlayerState.allies`, and `engine/allies.py::recruit_ally` /
`burn_ally` -- the minimum representation a currently-blocked card (47th
Street Royals) needs: an ally existing in play, and being burned as a
card's own reaction cost (reusing the already-wired `"bleed_amount_
modifier"` impulse window, same shape as `src/vtesbot/cards/
telepathic_counter.py`'s reduction, but consuming the ally itself instead of
a hand card as the cost).

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a trivial fake provider standing in for 47th Street
Royals' own card module -- 47th Street Royals itself remains
`card-implementer`'s job once this capability exists.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.allies import burn_ally, recruit_ally
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.minion import minion_phase


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def test_recruit_ally_creates_a_ready_locked_ally_under_its_controller():
    """Rulebook SS4 default actions: "recruited ally cannot act this turn"
    -- the ally enters the ready region already locked."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()

    ally = recruit_ally(
        game.state, "P1", krcg_id=102217, name="47th Street Royals", life=2, strength=1, bleed=0
    )

    assert ally.controller == "P1"
    assert ally.life == 2
    assert ally.strength == 1
    assert ally.bleed == 0
    assert ally.zone == "ready"
    assert ally.locked is True
    assert ally.is_ready_unlocked is False
    assert game.state.players["P1"].allies[ally.instance_id] is ally


def test_recruited_allies_get_distinct_instance_ids_in_their_own_namespace():
    """Ally instance ids must not collide with vampire instance ids (both
    live in per-player dicts, but a card hook keyed only by instance id --
    e.g. a future combined "any minion" lookup -- must still disambiguate)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()

    ally1 = recruit_ally(game.state, "P1", krcg_id=1, name="Ally One", life=1)
    ally2 = recruit_ally(game.state, "P1", krcg_id=1, name="Ally One", life=1)

    assert ally1.instance_id != ally2.instance_id
    assert ally1.instance_id != "P1-V1"
    assert ally2.instance_id != "P1-V1"


def test_burn_ally_moves_it_out_of_play():
    """Mirrors `engine/damage.py::burn_vampire`'s own zone/locked reset."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    ally = recruit_ally(game.state, "P1", krcg_id=102217, name="47th Street Royals", life=2)
    ally.locked = False  # pretend a later turn has already unlocked it

    burn_ally(game.state, "P1", ally)

    assert ally.zone == "burned"
    assert ally.locked is False


def test_ally_burned_as_a_bleed_reduction_reaction_cost():
    """End-to-end stand-in for 47th Street Royals' own printed text ("You
    can burn 47th Street Royals to reduce a bleed against you by 3"),
    registered against the already-wired `"bleed_amount_modifier"` hook
    (`engine/phases/minion.py::_perform_bleed`) exactly like
    `telepathic_counter.py`'s reduction -- except the cost consumed is the
    ally itself (`burn_ally`), not a card played from hand."""

    def fake_47th_street_royals(state, context):
        player = context["player"]
        acting_vampire_id = context["vampire"]
        if acting_vampire_id in state.players[player].vampires:
            return []  # this is the bleeder's own turn of the impulse window
        ally = next(
            (
                a
                for a in state.players[player].allies.values()
                if a.zone == "ready" and a.name == "47th Street Royals"
            ),
            None,
        )
        if ally is None:
            return []
        amount_box = context["amount"]

        def _apply(s):
            burn_ally(s, player, ally)
            amount_box[0] -= 3

        return [
            hooks.HookOption(
                choice=Choice("burn_47th_street_royals", "Burn 47th Street Royals: -3 bleed"),
                apply=_apply,
            )
        ]

    hooks.register("bleed_amount_modifier", fake_47th_street_royals)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    ally = recruit_ally(game.state, "P2", krcg_id=102217, name="47th Street Royals", life=2)
    ally.locked = False  # ready to react this turn

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    # P2 has no ready vampire of its own, only the ally: no "block_attempt"
    # decision is raised at all ("only when needed" -- an ally cannot block,
    # see `AllyInPlay`'s own docstring on scope).
    defender = ScriptedAgent("P2")
    defender.expect("bleed_amount_modifier", "burn_47th_street_royals")
    # No further "pass" is asked: once the ally is burned, the fake provider
    # has nothing left to offer either side, and the window (CLAUDE.md rule
    # 4: impulse returns to the acting player) closes on two consecutive
    # empty offers without ever re-asking P2.
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # 1 bleed - 3 reduction, clamped at 0 lost
    assert ally.zone == "burned"
    actor.assert_exhausted()
    defender.assert_exhausted()
