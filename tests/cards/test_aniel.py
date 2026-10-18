"""Aniel (krcg id 201666, `src/vtesbot/cards/aniel.py`).

Card text: "Independent: Aniel can burn 1 corruption counter or a card
requiring a Discipline from another ready minion as a +1 stealth Ⓓ action
that costs 1 blood." No rulings on file.

One assertion per clause/qualifier: not offered for a different acting
vampire, not offered without enough blood, restricted to the *opponent's*
ready vampires (Ⓓ, Rulebook §8 glossary "Directed Action"), one option per
qualifying target (a corruption counter on the vampire itself vs. a
discipline-requiring attachment on it, independently), the counter burn
decrements `VampireInPlay.corruption_counters` by 1 (`engine/corruption.py`)
without touching anything else, the discipline-requiring-card burn removes
the whole attachment (`zone = "burned"`), the cost is only paid on a
successful (unblocked) resolution, and the "+1 stealth Ⓓ action" baseline
(directed=True).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards.aniel import KRCG_ID
from vtesbot.cards.registry import Status, get
from vtesbot.engine import CryptCard, hooks
from vtesbot.engine.action import ACTION_ACTION_CARD
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, minion_phase

NAME = "Aniel"


def _make_aniel(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Aniel's real printed
    identity (`CryptCard` is frozen)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name=NAME,
        capacity=6,
        group=7,
        clan="Salubri",
        disciplines=("for", "AUS", "DOM"),
    )


def test_registered_as_implemented_against_the_action_card_play_hook():
    reg = get(KRCG_ID)
    assert reg is not None
    assert reg.status is Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


def test_not_offered_for_a_different_vampire():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("W1", capacity=3)
    game = builder.build()
    game.vampire("W1").corruption_counters["P1"] = 1

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")

    assert options == []


def test_not_offered_without_enough_blood():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=0)
    _make_aniel(p1, "V1")
    builder.player("P2", pool=30).ready_vampire("W1", capacity=3)
    game = builder.build()
    game.vampire("W1").corruption_counters["P1"] = 1

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")

    assert options == []


def test_restricted_to_the_opponents_ready_vampires_not_the_controllers_own():
    """Ⓓ (Directed Action): "targets one or more other Methuselahs, or the
    minions or cards they control" -- Aniel's own controller's other
    vampires are never eligible targets."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
    p1.ready_vampire("W1", capacity=3)
    _make_aniel(p1, "V1")
    builder.player("P2", pool=30).ready_vampire("W2", capacity=3)
    game = builder.build()
    game.vampire("W1").corruption_counters["P2"] = 1
    game.vampire("W2").corruption_counters["P1"] = 1

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")

    values = {o.choice.value for o in options}
    assert all("W2" in v for v in values)
    assert not any("W1" in v for v in values)


def test_not_offered_without_a_qualifying_corruption_counter_or_attachment():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
    _make_aniel(p1, "V1")
    builder.player("P2", pool=30).ready_vampire("W1", capacity=3)
    game = builder.build()
    game.vampire("W1").attachments.append(
        CardAttachment(krcg_id=999999, name="Plain Attachment")  # no discipline requirement
    )

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")

    assert options == []


def test_offers_one_option_for_a_corruption_counter_and_one_for_a_discipline_card():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
    _make_aniel(p1, "V1")
    builder.player("P2", pool=30).ready_vampire("W1", capacity=3)
    game = builder.build()
    w1 = game.vampire("W1")
    w1.corruption_counters["P1"] = 1
    w1.attachments.append(
        CardAttachment(krcg_id=999998, name="Discipline Card", requires_discipline=True)
    )

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")

    assert len(options) == 2
    labels = sorted(o.choice.label for o in options)
    assert any("corruption counter" in label and "W1" in label for label in labels)
    assert any("Discipline Card" in label and "requires a Discipline" in label for label in labels)


def test_counter_burn_decrements_the_vampires_own_corruption_counters():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
    _make_aniel(p1, "V1")
    builder.player("P2", pool=30).ready_vampire("W1", capacity=3)
    game = builder.build()
    w1 = game.vampire("W1")
    w1.corruption_counters["P1"] = 2

    (option,) = [
        o
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
        if "counter" in o.choice.value
    ]
    spec = option.apply(game.state)
    spec.resolve({})

    assert w1.corruption_counters == {"P1": 1}
    assert game.blood_of("V1") == 0  # cost paid.


def test_discipline_card_burn_sets_zone_to_burned():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
    _make_aniel(p1, "V1")
    builder.player("P2", pool=30).ready_vampire("W1", capacity=3)
    game = builder.build()
    attachment = CardAttachment(krcg_id=999998, name="Discipline Card", requires_discipline=True)
    game.vampire("W1").attachments.append(attachment)

    (option,) = [
        o
        for o in hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
        if "discipline" in o.choice.value
    ]
    spec = option.apply(game.state)
    spec.resolve({})

    assert attachment.zone == "burned"
    assert game.blood_of("V1") == 0  # cost paid.


def test_base_stealth_is_one_and_directed_is_true():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
    _make_aniel(p1, "V1")
    builder.player("P2", pool=30).ready_vampire("W1", capacity=3)
    game = builder.build()
    game.vampire("W1").corruption_counters["P1"] = 1

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    spec = option.apply(game.state)

    assert spec.base_stealth == 1
    assert spec.directed is True


def test_blocked_pays_no_cost_and_burns_nothing():
    """Base stealth 1 needs a matching +1 intercept to actually succeed a
    block attempt; a temporary fake `"intercept_modifier"` provider (gated
    on this card's own default `ACTION_ACTION_CARD` discriminator) stands in
    for some other intercept-granting card so this test can reach the
    blocked branch (mirrors `tests/cards/test_sakhar.py`'s own identically
    shaped precedent). The targeted vampire (W1) is itself also a legal
    block candidate alongside P2's other ready vampire (B1); the defender
    blocks with B1 here."""

    def match_stealth(state, context):
        if context.get("action") != ACTION_ACTION_CARD:
            return []
        return [HookOption(choice=Choice("match", "+1 intercept"), apply=lambda s: 1)]

    hooks.register("intercept_modifier", match_stealth)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
        _make_aniel(p1, "V1")
        p2 = builder.player("P2", pool=30).ready_vampire("W1", capacity=3)
        p2.ready_vampire("B1", capacity=5, blood=1)
        game = builder.build()
        w1 = game.vampire("W1")
        w1.corruption_counters["P1"] = 1

        (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", option.choice.value)
        actor.expect("strike_choice", "no_strike")
        actor.expect("press", "end_combat")
        defender = ScriptedAgent("P2")
        defender.expect("block_attempt", "block_with:B1")
        defender.expect("intercept_modifier", "match")
        defender.expect("strike_choice", "no_strike")
        defender.expect("press", "end_combat")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = defender

        minion_phase(game.state, "P1")

        assert w1.corruption_counters == {"P1": 1}  # unchanged: blocked, never resolved.
        assert game.blood_of("V1") == 1  # cost not paid.
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("intercept_modifier", match_stealth)


def test_unblocked_burns_a_corruption_counter_via_minion_phase():
    """P2's only ready vampire is the target (W1) itself, a legal block
    candidate by default -- stealth(1) > intercept(0) means any attempted
    block automatically fails, so P2 declines outright."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
    _make_aniel(p1, "V1")
    builder.player("P2", pool=30).ready_vampire("W1", capacity=3)
    game = builder.build()
    w1 = game.vampire("W1")
    w1.corruption_counters["P1"] = 1

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", option.choice.value)
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert w1.corruption_counters == {}
    assert game.blood_of("V1") == 0
    actor.assert_exhausted()
    defender.assert_exhausted()
