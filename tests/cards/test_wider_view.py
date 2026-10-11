"""Wider View (krcg id 102180, `src/vtesbot/cards/wider_view.py`).

Card text: "Trifle.\nPut this card in play. You can use 1 transfer to draw
1 card from your crypt and then remove a crypt card in your uncontrolled
region from the game. You can use 4 transfers to burn this card and gain 2
pool." Ruling: "Cards removed from the game are public. [LSJ 20080314]".

One assertion per clause/ruling: the trifle master-phase play (gated on
having the card in hand *and* enough pool, since `cost = Pool:1` -- a real
divergence from this task's own `pool_cost=None` brief, re-verified live and
documented in the module's own docstring), the 1-transfer draw-and-remove
ability (including the no-pre-existing-uncontrolled-card-needed reading
sourced from Rulebook SS8 Glossary "Draw", and the multi-target removal
choice), the 4-transfer burn-for-pool ability, and the LSJ "removed cards are
public" ruling, proven end-to-end through the real production hooks
(`master_phase`/`influence_phase`), mirroring
`tests/cards/test_oxford_university_england.py`'s own bar.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.wider_view import KRCG_ID, NAME
from vtesbot.engine import LibraryCard, build_observation, hooks
from vtesbot.engine.master_cards import bring_master_card_into_play
from vtesbot.engine.phases.influence import INFLUENCE_PHASE_ACTION_HOOK, influence_phase
from vtesbot.engine.phases.master import master_phase


def _wider_view_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="master")


def test_registered_as_implemented_against_its_hooks():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None
    assert set(reg.hooks) == {
        registry.Hook.MASTER_PHASE_PLAY,
        registry.Hook.INFLUENCE_PHASE_ACTION,
    }


# --- Clause 1: "Trifle. Put this card in play." -----------------------------


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")  # would fail loudly if asked anything
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_not_offered_without_enough_pool():
    """`cost = Pool:1` (re-verified live; see the module's own docstring):
    "Only a Methuselah with enough pool can play a card with a pool cost.\""""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=0)
    p1.hand.append(_wider_view_card())
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")  # would fail loudly if asked anything
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    agent.assert_exhausted()


def test_playing_it_brings_a_card_into_play_unlocked_and_costs_one_pool():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.hand.append(_wider_view_card())
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "wider_view_play")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert game.state.players["P1"].pool == 29
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    card = next(iter(game.state.players["P1"].master_cards.values()))
    assert card.krcg_id == KRCG_ID
    assert card.controller == "P1"
    assert card.zone == "in_play"
    assert card.locked is False
    agent.assert_exhausted()


def test_is_a_trifle_grants_an_extra_master_phase_action():
    """Rulebook SS4 Master Phase / SS8 glossary "Trifle": playing one grants
    one extra master phase action (max one per phase) -- proven by playing
    two copies in a single master phase (base action + the one trifle
    bonus), mirroring `tests/cards/test_life_in_the_city.py`'s own test."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.hand.append(_wider_view_card())
    p1.hand.append(_wider_view_card())
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "wider_view_play")
    agent.expect("master_phase_action", "wider_view_play")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    assert game.state.players["P1"].pool == 28  # 1 pool paid per copy played
    assert game.state.players["P1"].hand == []
    assert len(game.state.players["P1"].master_cards) == 2
    agent.assert_exhausted()


def test_not_a_unique_card_two_independently_played_copies_never_contest():
    """Printed "Trifle.", not "Unique.": two players' own copies never
    contest (OQ-23's own motivating non-unique counter-example, named by
    id)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.hand.append(_wider_view_card())
    builder.player("P2", pool=30)
    game = builder.build()
    existing = bring_master_card_into_play(game.state, "P2", krcg_id=KRCG_ID, name=NAME)

    agent = ScriptedAgent("P1")
    agent.expect("master_phase_action", "wider_view_play")
    game.state.agents["P1"] = agent

    master_phase(game.state, "P1")

    incoming = next(iter(game.state.players["P1"].master_cards.values()))
    assert incoming.zone == "in_play"
    assert incoming.contested_with is None
    assert existing.zone == "in_play"
    agent.assert_exhausted()


# --- Clause 2: "1 transfer: draw 1 card from your crypt and then remove a
# crypt card in your uncontrolled region from the game." --------------------


def test_draw_and_remove_not_offered_without_an_in_play_instance():
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    p1 = builder.player("P1", pool=30)
    p1.crypt_deck_cards(count=1, name_prefix="fresh")
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(
        INFLUENCE_PHASE_ACTION_HOOK, game.state, player="P1", transfers_remaining=4
    )

    assert options == []


def test_draw_and_remove_not_offered_without_a_crypt_deck_card():
    """The burn-for-pool ability (also offered at 4 transfers remaining) is
    unaffected by an empty crypt deck -- only the draw-and-remove option
    itself must be absent."""
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)

    options = hooks.offer(
        INFLUENCE_PHASE_ACTION_HOOK, game.state, player="P1", transfers_remaining=4
    )

    assert "wider_view_draw_and_remove" not in {o.choice.value for o in options}


def test_draw_and_remove_not_offered_with_zero_transfers_remaining():
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    p1 = builder.player("P1", pool=30)
    p1.crypt_deck_cards(count=1, name_prefix="fresh")
    builder.player("P2", pool=30)
    game = builder.build()
    bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)

    options = hooks.offer(
        INFLUENCE_PHASE_ACTION_HOOK, game.state, player="P1", transfers_remaining=0
    )

    assert options == []


def test_draw_and_remove_with_no_pre_existing_uncontrolled_vampire_auto_removes_the_drawn_card():
    """Resolves this task's own sequencing question directly from Rulebook
    SS8 Glossary "Draw" (quoted in the module docstring): the drawn card is
    already "in your uncontrolled region" the instant the draw completes, so
    it is itself a legal removal target -- no pre-existing uncontrolled
    vampire is required, and with only one candidate, no sub-`Decision` is
    raised at all (proven by the agent script staying exhausted after the
    single `"influence_action"` answer)."""
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    p1 = builder.player("P1", pool=30)
    p1.crypt_deck_cards(count=1, name_prefix="fresh")
    builder.player("P2", pool=30)
    game = builder.build()
    bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)
    agent = ScriptedAgent("P1")
    agent.expect("influence_action", "wider_view_draw_and_remove")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert len(game.state.players["P1"].crypt_deck) == 0
    removed = [
        v for v in game.state.players["P1"].vampires.values() if v.zone == "removed_from_game"
    ]
    assert len(removed) == 1
    assert removed[0].card.name == "fresh-0"
    agent.assert_exhausted()


def test_draw_and_remove_offers_a_choice_and_can_remove_the_pre_existing_card():
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    p1 = builder.player("P1", pool=30)
    p1.uncontrolled_vampire("Old", capacity=3, blood=0)
    p1.crypt_deck_cards(count=1, name_prefix="fresh")
    builder.player("P2", pool=30)
    game = builder.build()
    bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)
    agent = ScriptedAgent("P1")
    agent.expect("influence_action", "wider_view_draw_and_remove")
    agent.expect("wider_view_remove_target", "wider_view_remove_target:Old")
    # The kept, freshly-drawn vampire is still uncontrolled with transfers
    # left: more is legally offered (e.g. add_blood), so the phase does not
    # auto-stop -- end it explicitly.
    agent.expect("influence_action", "end_phase")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert game.zone_of("Old") == "removed_from_game"
    drawn = next(v for v in game.state.players["P1"].vampires.values() if v.card.name == "fresh-0")
    assert drawn.zone == "uncontrolled"  # the fresh draw was kept
    agent.assert_exhausted()


def test_draw_and_remove_can_remove_the_freshly_drawn_card_instead():
    """The freshly-drawn card is itself a legal removal target (see the
    module docstring's sourced reading of Rulebook SS8 Glossary "Draw") --
    proven by choosing it over the pre-existing uncontrolled vampire."""
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    p1 = builder.player("P1", pool=30)
    p1.uncontrolled_vampire("Old", capacity=3, blood=0)
    p1.crypt_deck_cards(count=1, name_prefix="fresh")
    builder.player("P2", pool=30)
    game = builder.build()
    bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)

    class _RemoveFreshAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "wider_view_remove_target":
                fresh = next(c for c in decision.choices if not c.value.endswith(":Old"))
                return fresh
            return super().decide(observation, decision)

    agent = _RemoveFreshAgent("P1")
    agent.expect("influence_action", "wider_view_draw_and_remove")
    # "Old" is kept, still uncontrolled with transfers left: end explicitly.
    agent.expect("influence_action", "end_phase")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert game.zone_of("Old") == "uncontrolled"  # kept
    removed = [
        v for v in game.state.players["P1"].vampires.values() if v.zone == "removed_from_game"
    ]
    assert len(removed) == 1
    assert removed[0].card.name == "fresh-0"


def test_a_vampire_removed_through_wider_view_is_fully_visible_to_the_opponent():
    """General ruling on file: "Cards removed from the game are public."
    [LSJ 20080314]. Production end-to-end through the real card's own
    provider, not just the lower-level `remove_vampire_from_game` helper
    (mirrors `tests/rules/test_influence.py`'s own fake-provider version of
    this same proof, now against the real module)."""
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    p1 = builder.player("P1", pool=30)
    p1.uncontrolled_vampire("V1", capacity=3, blood=0, name="Secret Name")
    p1.crypt_deck_cards(count=1, name_prefix="filler")
    builder.player("P2", pool=30)
    game = builder.build()
    bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)
    agent = ScriptedAgent("P1")
    agent.expect("influence_action", "wider_view_draw_and_remove")
    agent.expect("wider_view_remove_target", "wider_view_remove_target:V1")
    # The freshly-drawn "filler-0" is kept, still uncontrolled with transfers
    # left: end the phase explicitly.
    agent.expect("influence_action", "end_phase")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    obs_opponent = build_observation(game.state, "P2")
    view = next(v for v in obs_opponent.vampires if v.instance_id == "V1")
    assert view.zone == "removed_from_game"
    assert view.name == "Secret Name"
    assert view.locked is False
    agent.assert_exhausted()


# --- Clause 3: "4 transfers: burn this card and gain 2 pool." --------------


def test_burn_for_pool_not_offered_with_fewer_than_four_transfers_remaining():
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)

    options = hooks.offer(
        INFLUENCE_PHASE_ACTION_HOOK, game.state, player="P1", transfers_remaining=3
    )

    assert options == []


def test_burn_for_pool_not_offered_once_already_burned():
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    card = bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)
    card.zone = "burned"

    options = hooks.offer(
        INFLUENCE_PHASE_ACTION_HOOK, game.state, player="P1", transfers_remaining=4
    )

    assert options == []


def test_burn_for_pool_burns_the_card_costs_four_transfers_and_gains_two_pool():
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    card = bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)
    agent = ScriptedAgent("P1")
    agent.expect("influence_action", f"wider_view_burn_for_pool:{card.instance_id}")
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert game.state.players["P1"].pool == 32
    assert card.zone == "burned"
    agent.assert_exhausted()


def test_burn_for_pool_not_offered_during_the_three_transfer_first_influence_phase():
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=False)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    bring_master_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)
    agent = ScriptedAgent("P1")  # nothing legal: no decision at all
    game.state.agents["P1"] = agent

    influence_phase(game.state, "P1")

    assert game.state.players["P1"].pool == 30
    agent.assert_exhausted()
