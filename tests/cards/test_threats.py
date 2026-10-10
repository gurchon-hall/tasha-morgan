"""Threats (krcg id 101978, `src/vtesbot/cards/threats.py`).

Card text: "Only usable during a bleed action.\n[dom] +1 bleed
(limited).\n[DOM] +2 bleed (limited)." No rulings on file.

One assertion per clause: "only usable during a bleed action" (never
offered during a hunt), basic level, superior level (and the "may use
either" choice), "the acting minion" (never offered to the defender), and
the "(limited)" keyword (SS8 glossary / SS2 "same action modifier card at
most once per action").
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.threats import KRCG_ID
from vtesbot.engine import LibraryCard
from vtesbot.engine.phases.minion import minion_phase


def _threats_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name="Threats", card_type="modifier")


def test_registered_as_implemented_against_the_bleed_amount_modifier_hook():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == "Threats"


def _decline_defender() -> ScriptedAgent:
    return ScriptedAgent("P2").expect("block_attempt", "decline")


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, disciplines=("dom",))
    builder.player("P2", pool=30).ready_vampire("D", capacity=2, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = _decline_defender()
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # base bleed 1 only
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_not_offered_without_the_dominate_discipline():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_threats_card())
    builder.player("P2", pool=30).ready_vampire("D", capacity=2, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = _decline_defender()
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_basic_level_adds_one_bleed():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("dom",)
    )
    p1.hand.append(_threats_card())
    builder.player("P2", pool=30).ready_vampire("D", capacity=2, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("bleed_amount_modifier", "threats:basic")
    game.state.agents["P1"] = actor
    defender = _decline_defender()
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # base 1 + 1
    assert game.state.edge_holder == "P1"
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == ["Threats"]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_level_adds_two_bleed():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("DOM",)
    )
    p1.hand.append(_threats_card())
    builder.player("P2", pool=30).ready_vampire("D", capacity=2, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("bleed_amount_modifier", "threats:superior")
    game.state.agents["P1"] = actor
    defender = _decline_defender()
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 27  # base 1 + 2
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_vampire_may_opt_to_use_the_basic_effect_instead():
    """Rulebook SS3: a superior-level vampire "may opt to use either the
    basic (plain text) or the superior (bold) effect ... but not both"."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("DOM",)
    )
    p1.hand.append(_threats_card())
    builder.player("P2", pool=30).ready_vampire("D", capacity=2, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("bleed_amount_modifier", "threats:basic")
    game.state.agents["P1"] = actor
    defender = _decline_defender()
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # only +1, despite having DOM
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_never_offered_to_the_defender_even_with_dominate_and_a_copy_in_hand():
    """ "The acting minion can play these cards" (SS2 Action modifier cards):
    never offered to the defending Methuselah, regardless of their own
    discipline/hand."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p2 = builder.player("P2", pool=30).ready_vampire("V2", capacity=3, disciplines=("DOM",))
    p2.hand.append(_threats_card())
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = _decline_defender()
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # base bleed only; Threats never offered to P2
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_limited_keyword_forbids_a_second_bleed_increase_in_the_same_action():
    """SS8 glossary "Limited": "an action modifier card cannot be played to
    increase the bleed if the bleed amount is already being increased by
    another action modifier card"; SS2: "A minion cannot play the same
    action modifier card more than once during a single action"."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("dom",)
    )
    p1.hand.append(_threats_card())
    p1.hand.append(_threats_card())
    builder.player("P2", pool=30).ready_vampire("D", capacity=2, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("bleed_amount_modifier", "threats:basic")
    game.state.agents["P1"] = actor
    defender = _decline_defender()
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # only +1, not +2: the second copy is unused
    assert len(game.state.players["P1"].hand) == 1
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_only_usable_during_a_bleed_action_not_a_hunt():
    """ "Only usable during a bleed action": a mandatory hunt (no blood) never
    raises a `bleed_amount_modifier` decision at all."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("dom",)
    )
    p1.hand.append(_threats_card())
    builder.player("P2", pool=30).ready_vampire("D", capacity=2, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")  # no bleed/hunt choice at all: hunting is mandatory
    game.state.agents["P1"] = actor
    defender = _decline_defender()
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.blood_of("V1") == 1  # hunt succeeded
    assert len(game.state.players["P1"].hand) == 1  # Threats was never touched
    actor.assert_exhausted()
    defender.assert_exhausted()
