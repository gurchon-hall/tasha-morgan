"""Effective capacity / effective discipline levels (OQ-8,
`docs/OPEN_QUESTIONS.md`): `engine/attachments.py::effective_capacity` /
`effective_disciplines` fold a vampire's `attachments` into its printed
`CryptCard` stats via the `"capacity_modifier"` / `"discipline_level_
modifier"` hooks, and every call site that used to read `vampire.card.
capacity` / `vampire.card.disciplines` directly now goes through them.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using trivial fake providers standing in for a real attachment
card (e.g. Celerity) -- Celerity itself remains `card-implementer`'s job.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.attachments import effective_capacity, effective_disciplines
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.damage import add_blood
from vtesbot.engine.phases.influence import influence_phase


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def _fake_capacity_bonus_provider(krcg_id: int, bonus: int):
    """Stand-in for an attachment card's own `"+N capacity"` text: only
    contributes when its own `krcg_id` is actually attached to the vampire
    in question (CLAUDE.md SS6: the card module recognizes its own
    attachment, the engine never special-cases a card name)."""

    def provider(state, context):
        vampire_id = context["vampire"]
        for player_state in state.players.values():
            vampire = player_state.vampires.get(vampire_id)
            if vampire is not None:
                if any(a.krcg_id == krcg_id for a in vampire.attachments):
                    return bonus
                return 0
        return 0

    return provider


def _fake_discipline_grant_provider(krcg_id: int, discipline: str):
    def provider(state, context):
        vampire_id = context["vampire"]
        for player_state in state.players.values():
            vampire = player_state.vampires.get(vampire_id)
            if vampire is not None and any(a.krcg_id == krcg_id for a in vampire.attachments):
                return (discipline,)
        return ()

    return provider


def test_effective_capacity_with_no_attachments_equals_printed_capacity():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()

    assert effective_capacity(game.state, game.vampire("V1")) == 3


def test_effective_capacity_adds_a_registered_attachment_bonus():
    hooks.register("capacity_modifier", _fake_capacity_bonus_provider(krcg_id=100312, bonus=1))
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    vampire = game.vampire("V1")
    vampire.attachments.append(CardAttachment(krcg_id=100312, name="Celerity"))

    assert effective_capacity(game.state, vampire) == 4


def test_effective_capacity_ignores_an_unrelated_vampires_attachment():
    """The bonus must be scoped to the specific vampire it is attached to,
    not every vampire in play."""
    hooks.register("capacity_modifier", _fake_capacity_bonus_provider(krcg_id=100312, bonus=1))
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3).ready_vampire("V2", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    game.vampire("V1").attachments.append(CardAttachment(krcg_id=100312, name="Celerity"))

    assert effective_capacity(game.state, game.vampire("V1")) == 4
    assert effective_capacity(game.state, game.vampire("V2")) == 3


def test_effective_disciplines_unions_printed_and_attached_levels():
    hooks.register("discipline_level_modifier", _fake_discipline_grant_provider(100312, "cel"))
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, disciplines=("for",))
    builder.player("P2", pool=30)
    game = builder.build()
    vampire = game.vampire("V1")
    vampire.attachments.append(CardAttachment(krcg_id=100312, name="Celerity"))

    assert effective_disciplines(game.state, vampire) == ("cel", "for")


def test_effective_disciplines_with_no_attachments_equals_printed_disciplines():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, disciplines=("for", "aus"))
    builder.player("P2", pool=30)
    game = builder.build()

    assert effective_disciplines(game.state, game.vampire("V1")) == ("aus", "for")


def test_add_blood_caps_at_effective_capacity_not_printed_capacity():
    """Rulebook SS1 Vampires: blood may never exceed capacity -- now checked
    against the *effective* capacity, so an attached "+1 capacity" card
    actually raises the cap (OQ-8's whole point)."""
    hooks.register("capacity_modifier", _fake_capacity_bonus_provider(krcg_id=100312, bonus=1))
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=3)
    builder.player("P2", pool=30)
    game = builder.build()
    vampire = game.vampire("V1")
    vampire.attachments.append(CardAttachment(krcg_id=100312, name="Celerity"))

    added = add_blood(game.state, vampire, 2)

    assert added == 1  # capped at the effective capacity of 4, not the printed 3
    assert vampire.blood == 4


def test_influence_phase_add_blood_choice_respects_effective_capacity():
    """`engine/phases/influence.py`'s "add 1 blood" choice must not be
    offered once a vampire is already at its *effective* capacity, and must
    still be offered while under it even though it is already at its
    printed capacity (OQ-8)."""
    hooks.register("capacity_modifier", _fake_capacity_bonus_provider(krcg_id=100312, bonus=1))
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    builder.player("P1", pool=30).uncontrolled_vampire("V1", capacity=3, blood=3)
    builder.player("P2", pool=30)
    game = builder.build()
    vampire = game.vampire("V1")
    vampire.attachments.append(CardAttachment(krcg_id=100312, name="Celerity"))
    offered: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            offered.append([c.value for c in decision.choices])
            return super().decide(observation, decision)

    agent = RecordingAgent("P1")
    agent.expect("influence_action", "add_blood:V1")
    agent.expect("influence_action", "end_phase")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert vampire.blood == 4
    assert "add_blood:V1" in offered[0]  # still below the effective cap of 4
    assert "reveal:V1" in offered[1]  # now at the effective cap: free reveal unlocked
    agent.assert_exhausted()


def test_influence_phase_reveal_choice_requires_effective_capacity():
    """A vampire at its printed capacity but below its *effective* capacity
    (because of an attachment) must not yet offer the free "reveal" choice
    (OQ-8): Rulebook SS4 Influence Phase, "a vampire with blood >= capacity
    may be revealed"."""
    hooks.register("capacity_modifier", _fake_capacity_bonus_provider(krcg_id=100312, bonus=1))
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    builder.player("P1", pool=30).uncontrolled_vampire("V1", capacity=3, blood=3)
    builder.player("P2", pool=30)
    game = builder.build()
    vampire = game.vampire("V1")
    vampire.attachments.append(CardAttachment(krcg_id=100312, name="Celerity"))
    offered_on_first_decision: list[str] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if not offered_on_first_decision:
                offered_on_first_decision.extend(c.value for c in decision.choices)
            return super().decide(observation, decision)

    agent = RecordingAgent("P1")
    agent.expect("influence_action", "add_blood:V1")
    agent.expect("influence_action", "end_phase")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert "reveal:V1" not in offered_on_first_decision
    assert "add_blood:V1" in offered_on_first_decision
    agent.assert_exhausted()
