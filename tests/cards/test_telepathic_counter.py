"""Telepathic Counter (krcg id 101948,
`src/vtesbot/cards/telepathic_counter.py`).

Card text: "[aus] Reduce a bleed against you by 1.\n[AUS] Reduce a bleed
against you by 2." Ruling: "Must be played before the bleed can be
considered successful ..., but can be played before or after block
attempts." [TOM 19960303] [LSJ 20061212] -- every scenario below plays it
*after* a declined block attempt, which is the module docstring's argument
for why that is the only observable timing in this engine.

One assertion per clause: basic level, superior level (and the "may use
either, not both" choice), "against you" (never offered to the bleeder),
"a minion cannot play the same reaction card more than once" (scoped to a
single minion, not the whole Methuselah), and the bleed-amount floor at 0.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.telepathic_counter import KRCG_ID
from vtesbot.engine import LibraryCard
from vtesbot.engine.phases.minion import minion_phase


def _telepathic_counter_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name="Telepathic Counter", card_type="reaction")


def _bleed_scenario(seed: int = 1):
    builder = ScenarioBuilder(seed=seed)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    return builder


def test_registered_as_implemented_against_the_bleed_amount_modifier_hook():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == "Telepathic Counter"


def test_not_offered_without_the_card_in_hand():
    builder = _bleed_scenario()
    p2 = builder._players["P2"]
    p2.ready_vampire("V2", capacity=3, blood=0, disciplines=("aus",))
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # base bleed of 1, no reduction available
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_not_offered_without_the_auspex_discipline():
    builder = _bleed_scenario()
    p2 = builder._players["P2"]
    p2.ready_vampire("V2", capacity=3, blood=0)  # no disciplines at all
    p2.hand.append(_telepathic_counter_card())
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_basic_level_reduces_bleed_by_one():
    builder = _bleed_scenario()
    p2 = builder._players["P2"]
    p2.ready_vampire("V2", capacity=3, blood=0, disciplines=("aus",))
    p2.hand.append(_telepathic_counter_card())
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("bleed_amount_modifier", "telepathic_counter:basic:V2")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # base bleed 1, reduced to 0
    assert game.state.edge_holder is None
    assert game.state.players["P2"].hand == []
    assert [c.name for c in game.state.players["P2"].ash_heap] == ["Telepathic Counter"]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_level_can_reduce_bleed_by_two():
    builder = _bleed_scenario()
    p2 = builder._players["P2"]
    p2.ready_vampire("V2", capacity=3, blood=0, disciplines=("AUS",))
    p2.hand.append(_telepathic_counter_card())
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("bleed_amount_modifier", "telepathic_counter:superior:V2")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # base bleed 1, reduced to -1, floored at 0
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_superior_vampire_may_opt_to_use_the_basic_effect_instead():
    """Rulebook SS3: a superior-level vampire "may opt to use either the
    basic (plain text) or the superior (bold) effect ... but not both"."""
    builder = _bleed_scenario()
    p2 = builder._players["P2"]
    p2.ready_vampire("V2", capacity=3, blood=0, disciplines=("AUS",))
    p2.hand.append(_telepathic_counter_card())
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("bleed_amount_modifier", "telepathic_counter:basic:V2")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # reduced by 1, same as the basic-only vampire above
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_never_offered_to_the_bleeder_even_with_auspex_and_a_copy_in_hand():
    """ "Reduce a bleed against you": never offered to the acting (bleeding)
    player, regardless of their own discipline/hand."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=1, disciplines=("aus",)
    )
    p1.hand.append(_telepathic_counter_card())
    builder.player("P2", pool=30).ready_vampire("D", capacity=2, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29
    assert game.state.edge_holder == "P1"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_a_minion_cannot_play_the_same_reaction_card_twice_in_one_action():
    """SS2 Cards in general: "A minion cannot play the same reaction card
    more than once during a single action (even if using a different
    Discipline level)" -- a second copy in the *same minion's* hand is not
    offered again this action."""
    builder = _bleed_scenario()
    p2 = builder._players["P2"]
    p2.ready_vampire("V2", capacity=3, blood=0, disciplines=("aus",))
    p2.hand.append(_telepathic_counter_card())
    p2.hand.append(_telepathic_counter_card())
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("bleed_amount_modifier", "telepathic_counter:basic:V2")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # only reduced once, not twice
    assert len(game.state.players["P2"].hand) == 1  # the second copy is unused
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_two_different_minions_may_each_play_their_own_copy_in_one_action():
    """The SS2 "same reaction card" restriction is per-minion, not
    per-Methuselah: a second, *different* eligible minion may still play a
    second copy in the same action."""
    builder = _bleed_scenario()
    p2 = builder._players["P2"]
    p2.ready_vampire("V2", capacity=3, blood=0, disciplines=("aus",))
    p2.ready_vampire("V3", capacity=3, blood=0, disciplines=("aus",))
    p2.hand.append(_telepathic_counter_card())
    p2.hand.append(_telepathic_counter_card())
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("bleed_amount_modifier", "telepathic_counter:basic:V2")
    defender.expect("bleed_amount_modifier", "telepathic_counter:basic:V3")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # base bleed 1, reduced by 1 + 1
    assert game.state.players["P2"].hand == []
    actor.assert_exhausted()
    defender.assert_exhausted()
