"""Combat-card hook wiring (`engine/hooks.py`, CLAUDE.md milestone-3
scaffolding pass; `engine/combat.py`): `"combat_strike_option"` (an extra,
card-granted strike choice standing in for a hand strike) and
`"combat_strength_modifier"` (a passive, mandatory numeric bonus, e.g. a
printed vampire ability). No combat card is implemented yet -- scenario
tests for the mechanism only, using trivial fake providers.
"""

import pytest

from helpers import ScenarioBuilder
from vtesbot.engine import hooks
from vtesbot.engine.combat import run_combat
from vtesbot.engine.decision import Choice


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


class _RecordingAgent:
    """Fixed strike choice; records the `mend_damage` decision's `damage`
    context (the actual inflicted normal damage) and always declines to
    mend, so the captured amount is unaffected by blood spent mending."""

    def __init__(self, player_id: str, strike_choice: str, captured: dict) -> None:
        self.player_id = player_id
        self.strike_choice = strike_choice
        self.captured = captured

    def decide(self, observation, decision):
        if decision.kind == "strike_choice":
            matching = [c for c in decision.choices if c.value == self.strike_choice]
            return matching[0]
        if decision.kind == "mend_damage":
            self.captured[self.player_id] = decision.context["damage"]
            return decision.choices[0]  # decline (always offered as choice "0")
        if decision.kind == "press":
            return next(c for c in decision.choices if c.value == "end_combat")
        raise AssertionError(f"unexpected decision kind {decision.kind!r}")


def _combat_game():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=2)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=10, blood=10)
    return builder.build()


def test_hand_strike_damage_is_strength_one_without_a_modifier_provider():
    """Zero-regression check: byte-for-byte the milestone-2 result."""
    game = _combat_game()
    captured: dict = {}
    game.state.agents["P1"] = _RecordingAgent("P1", "hand_strike", captured)
    game.state.agents["P2"] = _RecordingAgent("P2", "no_strike", captured)

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert captured["P2"] == 1


def test_combat_strength_modifier_hook_adds_to_hand_strike_damage():
    hooks.register(
        "combat_strength_modifier",
        lambda state, context: 1 if context.get("player") == "P1" else 0,
    )
    game = _combat_game()
    captured: dict = {}
    game.state.agents["P1"] = _RecordingAgent("P1", "hand_strike", captured)
    game.state.agents["P2"] = _RecordingAgent("P2", "no_strike", captured)

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert captured["P2"] == 2  # base strength 1 + the fake modifier's 1


def test_combat_strike_option_hook_can_fully_replace_a_hand_strike():
    def fake_strike(state, context):
        if context.get("player") != "P1":
            return []
        return [hooks.HookOption(choice=Choice("fake_strike", "Fake strike"), apply=lambda s: 5)]

    hooks.register("combat_strike_option", fake_strike)
    game = _combat_game()
    captured: dict = {}
    game.state.agents["P1"] = _RecordingAgent("P1", "fake_strike", captured)
    game.state.agents["P2"] = _RecordingAgent("P2", "no_strike", captured)

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert captured["P2"] == 5
