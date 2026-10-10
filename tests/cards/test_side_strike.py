"""Side Strike (krcg id 101778, `src/vtesbot/cards/side_strike.py`).

Card text: "[cel] Strike: dodge.\n[CEL] Additional strike (limited)." No
rulings on file.

One assertion per clause/qualifier: the `[cel]` dodge clause's own basic-or-
superior discipline gate and "card in hand" gate; the `[CEL]` additional-
strike clause's own superior-only discipline gate and "card in hand" gate;
the two clauses' independence (superior Celerity unlocks both, each usable
on its own, neither requiring the other); the dodge protecting against the
opponent's simultaneous strike; the additional strike's grant claimed
through the engine's own full strike-choice machinery (not a hardcoded hand
strike); and the "(limited)" restriction on the additional-strike clause
only (a second copy is not offered again once the first has been played).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.side_strike import KRCG_ID
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.combat import (
    COMBAT_ADDITIONAL_STRIKE_HOOK,
    COMBAT_DODGE_OPTION_HOOK,
    run_combat,
)

NAME = "Side Strike"


def _side_strike_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="combat")


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


# --- "[cel] Strike: dodge." -------------------------------------------------


def test_dodge_not_offered_without_cel():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0, disciplines=())
    p1.hand.append(_side_strike_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        COMBAT_DODGE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    assert options == []


def test_dodge_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0, disciplines=("cel",))
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        COMBAT_DODGE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    assert options == []


def test_dodge_offered_with_basic_cel():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("cel",)
    )
    p1.hand.append(_side_strike_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(
            COMBAT_DODGE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
        )
    }
    assert values == {"side_strike:dodge"}


def test_dodge_also_offered_with_superior_cel():
    """Superior Celerity presence satisfies the basic-level discipline check
    too (Rulebook SS3 "may opt to use either effect"), the same convention
    `bonding.py` already uses for its own basic/superior pair."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("CEL",)
    )
    p1.hand.append(_side_strike_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(
            COMBAT_DODGE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
        )
    }
    assert values == {"side_strike:dodge"}


def test_dodge_protects_against_the_opponents_simultaneous_strike():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "B1", capacity=3, blood=0, disciplines=("cel",)
    )
    p2.hand.append(_side_strike_card())
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "side_strike:dodge")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.zone_of("B1") == "ready"
    assert game.vampire("B1").wounded is False  # V1's hand strike had no effect
    assert game.zone_of("V1") == "ready"
    assert game.vampire("V1").wounded is False  # a dodge strike deals no damage either
    assert game.state.players["P2"].hand == []
    assert [c.name for c in game.state.players["P2"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


# --- "[CEL] Additional strike (limited)." -----------------------------------


def test_additional_strike_not_offered_with_only_basic_cel():
    """Superior-only clause: basic `"cel"` alone does not unlock it."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("cel",)
    )
    p1.hand.append(_side_strike_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        COMBAT_ADDITIONAL_STRIKE_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    assert options == []


def test_additional_strike_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0, disciplines=("CEL",))
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        COMBAT_ADDITIONAL_STRIKE_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    assert options == []


def test_additional_strike_offered_with_superior_cel():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("CEL",)
    )
    p1.hand.append(_side_strike_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(
            COMBAT_ADDITIONAL_STRIKE_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
        )
    }
    assert values == {"side_strike:additional_strike"}


def test_superior_cel_unlocks_both_clauses_independently():
    """A superior-Celerity vampire is eligible for both clauses at once (two
    separate physical copies in hand): neither clause requires the other."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("CEL",)
    )
    p1.hand.append(_side_strike_card())
    p1.hand.append(_side_strike_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    dodge_values = {
        o.choice.value
        for o in hooks.offer(
            COMBAT_DODGE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
        )
    }
    extra_values = {
        o.choice.value
        for o in hooks.offer(
            COMBAT_ADDITIONAL_STRIKE_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
        )
    }
    assert dodge_values == {"side_strike:dodge"}
    assert extra_values == {"side_strike:additional_strike"}


def test_additional_strike_grants_one_additional_strike_via_the_full_strike_machinery():
    """The grant is claimed directly (no dodge needs to be played first or
    at all) and resolves through the engine's own full strike-choice
    machinery, not a hardcoded hand strike."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("CEL",)
    )
    p1.hand.append(_side_strike_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")  # normal pair: a plain hand strike
    actor.expect("additional_strike_choice", "side_strike:additional_strike")
    actor.expect("strike_choice", "hand_strike")  # the additional strike itself
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    # B1 has no grant of its own: never asked `additional_strike_choice` at all.
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    # Two separate hits landed on B1 this round (the normal hand strike, then
    # the granted additional strike): healthy -> wounded -> torpor. Combat
    # ends at once (Rulebook SS4: "combat ends at once if a combatant is no
    # longer ready"), with no press step raised for either side.
    assert game.zone_of("B1") == "torpor"
    assert game.zone_of("V1") == "ready"
    assert game.vampire("V1").wounded is False
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_limited_blocks_a_second_copy_in_the_same_round():
    """ "(limited)": once the `[CEL]` clause has been played once, a second
    physical copy is not offered again (this module's own "once per vampire
    instance" granularity, strictly more restrictive than "once per round",
    per the module docstring)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("CEL",)
    )
    p1.hand.append(_side_strike_card())
    p1.hand.append(_side_strike_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    first = hooks.offer(
        COMBAT_ADDITIONAL_STRIKE_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    assert {o.choice.value for o in first} == {"side_strike:additional_strike"}
    first[0].apply(game.state)  # play the first copy.

    second = hooks.offer(
        COMBAT_ADDITIONAL_STRIKE_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    assert second == []  # the second copy's [CEL] clause is not offered again.
    assert len(game.state.players["P1"].hand) == 1  # second copy stayed unused in hand


def test_limited_does_not_restrict_the_dodge_clause():
    """The "(limited)" restriction is printed only on the `[CEL]` additional-
    strike line; the `[cel]` dodge clause carries no such restriction and
    remains offered after the additional-strike grant has been used."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("CEL",)
    )
    p1.hand.append(_side_strike_card())
    p1.hand.append(_side_strike_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    extra = hooks.offer(
        COMBAT_ADDITIONAL_STRIKE_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    extra[0].apply(game.state)  # consume the "(limited)" additional-strike grant.

    dodge = hooks.offer(
        COMBAT_DODGE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    assert {o.choice.value for o in dodge} == {"side_strike:dodge"}
