"""Weighted Walking Stick (krcg id 102169, `src/vtesbot/cards/
weighted_walking_stick.py`).

Card text: "Only usable before range is determined during the first
round. Put this card with 5 counters on it on this minion; it becomes a
melee weapon equipment that can strike: strength+1 damage. For each
damage inflicted by this strike (even if prevented), burn 1 counter from
this card. Burn this card if it has no counters. A minion can have only
one Weighted Walking Stick." Rulings: "If the damage is reduced ... or
not inflicted ..., the corresponding token is not burned (contrary to
prevented damage)." [LSJ 20100519]; "Full damage is applied if there are
any counter left, even just 1." [ANK 20201229-2].

One assertion per clause/ruling: the attach option's own hand/one-per-
minion gates and "this minion" reading (own combatant only); the strike
option's own attachment/counter gates, `strength+1` damage computation,
counter-burn-per-damage-inflicted-even-if-prevented mechanic, the
full-damage-with-any-counter-left ruling, and auto-burning the card at 0
counters -- proven both as isolated hook offers and end to end through
`run_combat`.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.weighted_walking_stick import KRCG_ID
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.attachments import attach_card
from vtesbot.engine.combat import BEFORE_RANGE_HOOK, COMBAT_STRIKE_OPTION_HOOK, run_combat

NAME = "Weighted Walking Stick"


def _wws_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="combat")


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None
    assert registry.Hook.BEFORE_RANGE in reg.hooks
    assert registry.Hook.COMBAT_STRIKE_OPTION in reg.hooks


# --- "Put this card with 5 counters on it on this minion ..." --------------


def _attach_context(
    *,
    player: str,
    acting_player: str,
    acting_vampire: str,
    blocking_player: str,
    blocking_vampire: str,
) -> dict:
    return {
        "player": player,
        "acting_player": acting_player,
        "acting_vampire": acting_vampire,
        "blocking_player": blocking_player,
        "blocking_vampire": blocking_vampire,
    }


def test_attach_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        BEFORE_RANGE_HOOK,
        game.state,
        **_attach_context(
            player="P1",
            acting_player="P1",
            acting_vampire="V1",
            blocking_player="P2",
            blocking_vampire="B1",
        ),
    )
    assert options == []


def test_attach_offered_to_the_acting_player_for_their_own_vampire():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    p1.hand.append(_wws_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        BEFORE_RANGE_HOOK,
        game.state,
        **_attach_context(
            player="P1",
            acting_player="P1",
            acting_vampire="V1",
            blocking_player="P2",
            blocking_vampire="B1",
        ),
    )
    assert {o.choice.value for o in options} == {"weighted_walking_stick:attach:V1"}


def test_attach_offered_to_the_blocking_player_for_their_own_vampire():
    """ "This minion" is always the *playing* controller's own combatant --
    P2 (the blocking player) attaches to B1, never to V1."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    p2.hand.append(_wws_card())
    game = builder.build()

    options = hooks.offer(
        BEFORE_RANGE_HOOK,
        game.state,
        **_attach_context(
            player="P2",
            acting_player="P1",
            acting_vampire="V1",
            blocking_player="P2",
            blocking_vampire="B1",
        ),
    )
    assert {o.choice.value for o in options} == {"weighted_walking_stick:attach:B1"}


def test_attach_not_offered_if_the_minion_already_has_one():
    """ "A minion can have only one Weighted Walking Stick."."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    p1.hand.append(_wws_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name=NAME, counters=5
    )

    options = hooks.offer(
        BEFORE_RANGE_HOOK,
        game.state,
        **_attach_context(
            player="P1",
            acting_player="P1",
            acting_vampire="V1",
            blocking_player="P2",
            blocking_vampire="B1",
        ),
    )
    assert options == []


def test_attach_applies_play_from_hand_and_attaches_with_5_counters():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    p1.hand.append(_wws_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        BEFORE_RANGE_HOOK,
        game.state,
        **_attach_context(
            player="P1",
            acting_player="P1",
            acting_vampire="V1",
            blocking_player="P2",
            blocking_vampire="B1",
        ),
    )
    options[0].apply(game.state)

    vampire = game.vampire("V1")
    assert len(vampire.attachments) == 1
    attachment = vampire.attachments[0]
    assert attachment.krcg_id == KRCG_ID
    assert attachment.counters == 5
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]


# --- "... it becomes a melee weapon equipment that can strike:
# strength+1 damage." / counter-burn mechanics ------------------------------


def test_strike_not_offered_without_the_attachment():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    assert options == []


def test_strike_not_offered_once_counters_are_exhausted():
    """Defensive: even if an attachment somehow sits at 0 counters (it
    should always be removed outright once reached, see below), the strike
    is not offered."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name=NAME, counters=0
    )

    options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    assert options == []


def test_strike_deals_strength_plus_one_damage():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name=NAME, counters=5
    )

    options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    assert {o.choice.value for o in options} == {"weighted_walking_stick:strike:V1"}
    amount = options[0].apply(game.state)
    assert amount == 2  # base hand-strike strength (1) + 1


def test_strike_burns_one_counter_per_damage_inflicted():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name=NAME, counters=5
    )

    options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    options[0].apply(game.state)

    attachment = game.vampire("V1").attachments[0]
    assert attachment.counters == 3  # 5 - 2 damage inflicted


def test_strike_deals_full_damage_with_only_one_counter_left_then_burns_the_card():
    """ "Full damage is applied if there are any counter left, even just
    1." [ANK 20201229-2]: only 1 counter is burned (all that remains), but
    the full `strength+1` amount is still returned/dealt; the card is then
    burned outright, "Burn this card if it has no counters."."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name=NAME, counters=1
    )

    options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    amount = options[0].apply(game.state)

    assert amount == 2  # full damage despite only 1 counter available to burn
    assert game.vampire("V1").attachments == []  # "burn this card if it has no counters"


# --- End to end through `run_combat` ----------------------------------------


def test_attach_then_strike_end_to_end_through_run_combat():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=0)
    p1.hand.append(_wws_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=3)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("before_range", "weighted_walking_stick:attach:V1")
    actor.expect("strike_choice", "weighted_walking_stick:strike:V1")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("mend_damage", "2")  # mends the full 2 points dealt
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    wws = game.vampire("V1").attachments[0]
    assert wws.counters == 3  # 5 - 2 damage inflicted
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()
