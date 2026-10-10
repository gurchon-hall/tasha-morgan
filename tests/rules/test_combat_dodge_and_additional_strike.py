"""Dodge and same-round additional strike (`engine/combat.py`; resolves
`docs/OPEN_QUESTIONS.md` OQ-18 Gap 2): `"combat_dodge_option"` (a card-
granted dodge, offered alongside `"combat_strike_option"` at the strike
step) and `"combat_additional_strike"` (a card-granted extra strike this
round, resolved via the *same* full strike-choice machinery as a normal
strike -- never a fixed/hardcoded hand strike).

These two mechanics are deliberately exercised independently of each other
and with fake, test-only providers (no card module is implemented against
either hook yet) -- per the [LSJ 20030902-2]/[LSJ 20060808-1] rulings on
Dust Up quoted in OQ-18 ("[ani] Does not prevent the opponent from dodging,
the dodge just has no effect"), dodge is its own real mechanic with a real
effect in the general case, independent of any one card's wording.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.combat import (
    COMBAT_ADDITIONAL_STRIKE_HOOK,
    COMBAT_DODGE_OPTION_HOOK,
    COMBAT_STRIKE_OPTION_HOOK,
    StrikeDamage,
    run_combat,
)
from vtesbot.engine.decision import Choice


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


class _DeclineMendAgent:
    """Always declines to strike and to mend; records each `mend_damage`
    decision's `damage` context (the actual inflicted normal damage) so a
    test can tell which strike dealt it."""

    def __init__(self, player_id: str, captured: list) -> None:
        self.player_id = player_id
        self.captured = captured

    def decide(self, observation, decision):
        if decision.kind == "strike_choice":
            return next(c for c in decision.choices if c.value == "no_strike")
        if decision.kind == "mend_damage":
            self.captured.append(decision.context["damage"])
            return decision.choices[0]  # decline (always offered as choice "0")
        raise AssertionError(f"{self.player_id}: unexpected decision kind {decision.kind!r}")


def _combat_game(*, b1_blood: int = 0, b1_capacity: int = 10):
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=2)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=b1_capacity, blood=b1_blood)
    return builder.build()


def test_dodge_prevents_the_opponents_simultaneous_strike_from_dealing_damage():
    """Rulebook SS4 Combat > Strike Effects > Dodge: "A dodge strike deals
    no damage, but it protects the dodging minion and their possessions
    from the effects of the opposing strike." A fake `combat_dodge_option`
    provider grants B1 a dodge; V1's hand strike (which would otherwise deal
    1 damage, Rulebook SS4 Combat: "Hand strike = strength (default 1)")
    must have no effect on B1 at all."""

    def fake_dodge(state, context):
        if context.get("player") != "P2":
            return []
        return [hooks.HookOption(choice=Choice("fake_dodge", "Fake dodge"), apply=lambda s: None)]

    hooks.register(COMBAT_DODGE_OPTION_HOOK, fake_dodge)
    game = _combat_game()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "fake_dodge")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    # Dodge nullified V1's hand strike entirely: no damage, no wound, still ready.
    assert game.zone_of("B1") == "ready"
    assert game.vampire("B1").wounded is False
    assert game.blood_of("B1") == 0
    # Dodge itself deals no damage either (V1 is unaffected regardless).
    assert game.zone_of("V1") == "ready"
    assert game.vampire("V1").wounded is False
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_dodge_proof_strike_still_damages_a_dodging_opponent():
    """Golden Rule for Cards (CLAUDE.md SS2 / Rulebook SS3): a specific
    strike's own printed text can override the normal dodge rule for that
    strike -- sourced from Dust Up's own `[ani]` clause ("This strike
    cannot be dodged") and its ruling: "[ani] Does not prevent the opponent
    from dodging, the dodge just has no effect." [LSJ 20030902-2] [LSJ
    20060808-1]. B1 still chooses to dodge (a real, legal choice), but V1's
    strike is flagged `StrikeDamage(ignore_dodge=True)`, so the dodge has
    zero effect against it specifically."""

    def fake_dodge(state, context):
        if context.get("player") != "P2":
            return []
        return [hooks.HookOption(choice=Choice("fake_dodge", "Fake dodge"), apply=lambda s: None)]

    def fake_unstoppable_strike(state, context):
        if context.get("player") != "P1":
            return []
        strike_choice = Choice("fake_unstoppable", "Dodge-proof strike")
        return [
            hooks.HookOption(
                choice=strike_choice, apply=lambda s: StrikeDamage(amount=2, ignore_dodge=True)
            )
        ]

    hooks.register(COMBAT_DODGE_OPTION_HOOK, fake_dodge)
    hooks.register(COMBAT_STRIKE_OPTION_HOOK, fake_unstoppable_strike)
    game = _combat_game()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "fake_unstoppable")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "fake_dodge")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    # The dodge-proof strike's 2 damage landed despite B1's dodge.
    assert game.zone_of("B1") == "ready"
    assert game.vampire("B1").wounded is True
    # B1's own dodge still deals no damage to V1 (dodge-proof only cancels
    # the *protection* dodge would have granted, never the dodger's offense).
    assert game.zone_of("V1") == "ready"
    assert game.vampire("V1").wounded is False
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_no_dodge_choice_is_offered_without_a_registered_provider():
    """Regression guard: with no `combat_dodge_option` provider registered,
    `strike_choice` offers only the two built-ins (`"hand_strike"`,
    `"no_strike"`) -- dodge is never a base/default option (Choose Strike:
    "by default from a hand strike, or ... any other card providing this
    minion a strike")."""
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

    # No dodge available -> V1's hand strike lands normally, unlike the
    # dodge-protected case above.
    assert game.vampire("B1").wounded is True
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_same_round_additional_strike_reuses_the_full_strike_choice_machinery():
    """Rulebook SS4 Combat > Additional Strikes: a second strike is resolved
    within the same round, "after the first pair of strikes is completed"
    -- and per Choose Strike, that second strike is chosen from the exact
    same menu as any strike ("from a combat card, ... by default from a
    hand strike, or ... any other card providing this minion a strike"),
    never a fixed/hardcoded hand strike. The acting minion's additional
    strike here deliberately picks a card-granted `combat_strike_option`
    (3 damage) instead of a hand strike (1 damage) to prove the additional
    strike went through the full choice surface."""
    used = {"P1": False}

    def fake_additional_strike(state, context):
        if context.get("player") != "P1" or used["P1"]:
            return []

        def consume(s):
            used["P1"] = True

        extra_choice = Choice("use_extra", "Use additional strike")
        return [hooks.HookOption(choice=extra_choice, apply=consume)]

    def fake_strike_option(state, context):
        if context.get("player") != "P1":
            return []
        return [hooks.HookOption(choice=Choice("fake_strike", "Fake strike"), apply=lambda s: 3)]

    hooks.register(COMBAT_ADDITIONAL_STRIKE_HOOK, fake_additional_strike)
    hooks.register(COMBAT_STRIKE_OPTION_HOOK, fake_strike_option)
    game = _combat_game(b1_blood=5, b1_capacity=10)

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")  # normal pair: plain hand strike (1 dmg)
    actor.expect("additional_strike_choice", "use_extra")
    actor.expect("strike_choice", "fake_strike")  # additional strike: card-granted option (3 dmg)
    captured: list = []
    defender = _DeclineMendAgent("P2", captured)
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    # Two independent strikes landed this round: 1 (hand strike), then 3
    # (the additional strike's card-granted option, not a hand strike).
    assert captured == [1, 3]
    # Second hit on an already-wounded vampire sends it to torpor at once
    # (Rulebook SS4: "combat ends at once if a combatant is no longer
    # ready") -- confirms the additional strike's damage was really applied,
    # within the same round, with no press step raised for either side.
    assert game.zone_of("B1") == "torpor"
    assert game.zone_of("V1") == "ready"
    actor.assert_exhausted()


def test_additional_strike_pair_only_asks_combatants_with_an_available_grant():
    """Rulebook SS4 Combat > Additional Strikes: "another choose strike step
    and resolve strike step in which only the minions with additional
    strikes may play strike cards" -- the defender, who was never granted
    an additional strike, must not be asked a second `strike_choice` at all
    (not even offered "no_strike" again) for the additional-strike pair.

    `ScriptedAgent` fails loudly (`UnexpectedDecisionError`, a subclass of
    `AssertionError`) the moment it is asked a decision beyond its script,
    so scripting the defender with exactly one `strike_choice` is itself the
    proof: if the engine wrongly asked a second one, this test would raise
    before reaching its assertions.
    """
    used = {"P1": False}

    def fake_additional_strike(state, context):
        if context.get("player") != "P1" or used["P1"]:
            return []

        def consume(s):
            used["P1"] = True

        extra_choice = Choice("use_extra", "Use additional strike")
        return [hooks.HookOption(choice=extra_choice, apply=consume)]

    hooks.register(COMBAT_ADDITIONAL_STRIKE_HOOK, fake_additional_strike)
    game = _combat_game()  # B1 starts with 0 blood: no mend_damage decision is raised

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("additional_strike_choice", "use_extra")
    actor.expect("strike_choice", "hand_strike")  # the additional strike itself
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")  # asked exactly once, not twice
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    # Two separate normal-damage hits on B1 this round (healthy -> wounded,
    # then wounded -> torpor) -- combat ends at once, with no press step for
    # either side, confirming the additional strike's damage really landed.
    assert game.zone_of("B1") == "torpor"
    actor.assert_exhausted()
    defender.assert_exhausted()
