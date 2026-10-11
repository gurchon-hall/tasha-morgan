"""Determine Range and the maneuver mechanic (`engine/combat.py`): a new
combat step, resolved before the strike step every round, that lets a
card/printed-ability grant move the round between close and long range.

Per the task that added this file, only an ability-granted maneuver *not*
bundled with choosing a strike is exercised here (e.g. Saku Pihlajamäki's
printed "1 optional maneuver each combat") -- fake, test-only providers stand
in for it, proving the *generic* mechanism rather than any one real card's
wording (no combat card using `"maneuver"` is implemented yet).
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.combat import (
    CLOSE_RANGE,
    COMBAT_STRENGTH_MODIFIER_HOOK,
    LONG_RANGE,
    MANEUVER_HOOK,
    run_combat,
)
from vtesbot.engine.decision import Choice


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def _combat_game(*, acting_label: str = "V1", blocking_label: str = "B1", blocking_blood: int = 0):
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire(acting_label, capacity=10, blood=5)
    builder.player("P2", pool=30).ready_vampire(blocking_label, capacity=10, blood=blocking_blood)
    return builder.build()


def _capture_range_via_strength_modifier(captured: list, *, player: str = "P1"):
    """`"combat_strength_modifier"` is a passive, always-consulted hook
    (`hooks.sum_modifiers`) fired from `_strike_strength`, so registering a
    fake provider against it is a convenient, zero-side-effect way to read
    `state.combat_range` at the exact moment a hand strike resolves, without
    inventing a new test-only hook."""

    def capture(state, context):
        if context.get("player") == player:
            captured.append(state.combat_range)
        return 0

    hooks.register(COMBAT_STRENGTH_MODIFIER_HOOK, capture)


def test_no_maneuver_choice_is_offered_without_a_registered_provider():
    """Regression guard: with no `"maneuver"` provider registered, Determine
    Range never raises a `maneuver_choice` decision at all (CLAUDE.md "only
    when needed"), and the round stays at the rulebook's own default --
    Rulebook SS4 Combat > Determine Range: "Close range is the default for
    each round." Byte-for-byte the pre-maneuver result: no existing combat
    test's script needed a new entry for this."""
    captured: list = []
    _capture_range_via_strength_modifier(captured)
    game = _combat_game()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert captured == [CLOSE_RANGE]
    assert game.state.combat_range is None  # reset once combat (run_combat) returns
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_ayelech_colette_worked_example():
    """Rulebook SS4 Combat > Determine Range's own worked example, reproduced
    exactly: "Ayelech has just blocked Colette, and combat ensues. Ayelech
    has a .44 Magnum that allows her to strike for 2 damage at either close
    or long range, and gives her an optional maneuver. Colette, as the acting
    minion, declines to maneuver. Ayelech uses the maneuver from the gun to
    move to long range, where she cannot be harmed by Colette's hand strike.
    Colette plays a maneuver card to get back to close range. However,
    Ayelech has another maneuver card as well, and she plays it to move back
    to long range. Colette has no more maneuvers to play, so the range is set
    to long."

    Colette is the acting minion (she was blocked while bleeding/hunting),
    Ayelech is the blocking minion. Fake `"maneuver"` providers stand in for
    Colette's one maneuver card and Ayelech's gun + second maneuver card (the
    strike-card/weapon-bundled part of the real worked example is out of
    scope for this pass -- see module docstring's "Determine Range and
    maneuvers" section -- only the maneuver grant itself, and the alternation
    it produces, is under test here).
    """
    colette_card_available = {"value": True}
    ayelech_cards_remaining = {"value": 2}

    def colette_maneuver(state, context):
        if context.get("player") != "P1" or not colette_card_available["value"]:
            return []

        def use(s):
            colette_card_available["value"] = False

        return [
            hooks.HookOption(choice=Choice("colette_card", "Colette's maneuver card"), apply=use)
        ]

    def ayelech_maneuver(state, context):
        if context.get("player") != "P2" or ayelech_cards_remaining["value"] <= 0:
            return []
        label = "gun" if ayelech_cards_remaining["value"] == 2 else "second_card"

        def use(s):
            ayelech_cards_remaining["value"] -= 1

        choice = Choice(f"ayelech_{label}", f"Ayelech's {label}")
        return [hooks.HookOption(choice=choice, apply=use)]

    hooks.register(MANEUVER_HOOK, colette_maneuver)
    hooks.register(MANEUVER_HOOK, ayelech_maneuver)
    captured: list = []
    _capture_range_via_strength_modifier(captured)

    game = _combat_game(acting_label="Colette", blocking_label="Ayelech", blocking_blood=0)

    actor = ScriptedAgent("P1")  # Colette, acting
    actor.expect("maneuver_choice", hooks.PASS_VALUE)  # turn 1: declines first opportunity
    actor.expect("maneuver_choice", "colette_card")  # turn 3: back to close
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")  # Ayelech, blocking
    defender.expect("maneuver_choice", "ayelech_gun")  # turn 2: gun to long
    defender.expect("maneuver_choice", "ayelech_second_card")  # turn 4: back to long
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("Colette"), "P2", game.vampire("Ayelech"))

    # Turn 5: Colette has nothing left, declines (no decision raised, since
    # her provider now returns no options). Turn 6: Ayelech also has nothing
    # left (no decision raised either) -- the second consecutive decline
    # that closes the step, with the range left at long from turn 4.
    assert captured == [LONG_RANGE]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_maneuver_grant_is_scoped_to_the_whole_combat_not_reset_each_round():
    """A Saku Pihlajamäki-style grant ("1 optional maneuver each combat") must
    stay used for every round of the *same* combat, unlike a combat card's
    own round-scoped grant -- contrast with `test_combat_dodge_and_
    additional_strike.py::test_additional_strike_limit_resets_every_round_
    of_the_same_combat`, which proves the opposite lifetime for a different
    mechanism. `context["combat_state"]` is the shared dict `run_combat`
    creates once, outside its per-round loop (module docstring's "Per-combat,
    not per-round, scoping" paragraph)."""

    def saku_style_maneuver(state, context):
        if context.get("player") != "P1":
            return []
        used = context["combat_state"].setdefault("saku_used", set())
        if context["vampire"] in used:
            return []

        def use(s):
            used.add(context["vampire"])

        return [hooks.HookOption(choice=Choice("saku_maneuver", "Saku's maneuver"), apply=use)]

    hooks.register(MANEUVER_HOOK, saku_style_maneuver)
    captured: list = []
    _capture_range_via_strength_modifier(captured)

    game = _combat_game(blocking_blood=0)

    actor = ScriptedAgent("P1")
    # Round 1: use the once-per-combat grant.
    actor.expect("maneuver_choice", "saku_maneuver")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "press")
    # Round 2: the grant was already used this combat -- no maneuver_choice
    # decision at all, even though round_state-scoped mechanisms would reset.
    actor.expect("strike_choice", "hand_strike")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")  # round 1
    defender.expect("strike_choice", "no_strike")  # round 2
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    # Round 1's hand strike wounds B1 (0 blood, no mend decision possible);
    # round 2's hand strike on an already-wounded B1 sends it to torpor,
    # ending combat at once with no round-2 press decision for either side.
    assert game.zone_of("B1") == "torpor"
    assert captured == [LONG_RANGE, CLOSE_RANGE]
    actor.assert_exhausted()
    defender.assert_exhausted()
