"""Pursuit (krcg id 101523, `src/vtesbot/cards/pursuit.py`).

Card text: "[cel] Maneuver.\n[CEL] Additional strike (limited)." No rulings
on file.

One assertion per clause/qualifier, mirroring `test_side_strike.py`'s own
shape for this card's identical basic/superior split: the `[cel]` maneuver
clause's own basic-or-superior discipline gate and "card in hand" gate; the
`[CEL]` additional-strike clause's own superior-only discipline gate and
"card in hand" gate; the two clauses' independence; the additional strike's
grant claimed through the engine's own full strike-choice machinery; and the
"(limited)" restriction on the additional-strike clause only. Plus two
integration tests specific to this card's own RUL-008
resolution: the basic maneuver clause is *not* "a maneuver from a strike"
(Rulebook §4 Combat > Strike > Choose Strike), so it does not lock the
strike choice, and a second physical copy can maneuver again later in the
same round in response to the opponent's own counter-maneuver.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.pursuit import KRCG_ID
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.combat import COMBAT_ADDITIONAL_STRIKE_HOOK, MANEUVER_HOOK, run_combat

NAME = "Pursuit"


def _pursuit_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="combat")


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None
    assert registry.Hook.MANEUVER in reg.hooks
    assert registry.Hook.COMBAT_ADDITIONAL_STRIKE in reg.hooks


# --- "[cel] Maneuver." -------------------------------------------------------


def test_maneuver_not_offered_without_cel():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0, disciplines=())
    p1.hand.append(_pursuit_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        MANEUVER_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        combat_state={},
        round_state={},
    )
    assert options == []


def test_maneuver_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0, disciplines=("cel",))
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        MANEUVER_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        combat_state={},
        round_state={},
    )
    assert options == []


def test_maneuver_offered_with_basic_cel():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("cel",)
    )
    p1.hand.append(_pursuit_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(
            MANEUVER_HOOK,
            game.state,
            player="P1",
            vampire="V1",
            opponent="B1",
            combat_state={},
            round_state={},
        )
    }
    assert values == {"pursuit:maneuver"}


def test_maneuver_also_offered_with_superior_cel():
    """Superior Celerity presence satisfies the basic-level discipline check
    too (Rulebook §3 "may opt to use either effect")."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("CEL",)
    )
    p1.hand.append(_pursuit_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(
            MANEUVER_HOOK,
            game.state,
            player="P1",
            vampire="V1",
            opponent="B1",
            combat_state={},
            round_state={},
        )
    }
    assert values == {"pursuit:maneuver"}


# --- "[CEL] Additional strike (limited)." ------------------------------------


def test_additional_strike_not_offered_with_only_basic_cel():
    """Superior-only clause: basic `"cel"` alone does not unlock it."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("cel",)
    )
    p1.hand.append(_pursuit_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        COMBAT_ADDITIONAL_STRIKE_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        round_state={},
    )
    assert options == []


def test_additional_strike_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0, disciplines=("CEL",))
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        COMBAT_ADDITIONAL_STRIKE_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        round_state={},
    )
    assert options == []


def test_additional_strike_offered_with_superior_cel():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("CEL",)
    )
    p1.hand.append(_pursuit_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(
            COMBAT_ADDITIONAL_STRIKE_HOOK,
            game.state,
            player="P1",
            vampire="V1",
            opponent="B1",
            round_state={},
        )
    }
    assert values == {"pursuit:additional_strike"}


def test_superior_cel_unlocks_both_clauses_independently():
    """A superior-Celerity vampire is eligible for both clauses at once (two
    separate physical copies in hand): neither clause requires the other."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("CEL",)
    )
    p1.hand.append(_pursuit_card())
    p1.hand.append(_pursuit_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    maneuver_values = {
        o.choice.value
        for o in hooks.offer(
            MANEUVER_HOOK,
            game.state,
            player="P1",
            vampire="V1",
            opponent="B1",
            combat_state={},
            round_state={},
        )
    }
    extra_values = {
        o.choice.value
        for o in hooks.offer(
            COMBAT_ADDITIONAL_STRIKE_HOOK,
            game.state,
            player="P1",
            vampire="V1",
            opponent="B1",
            round_state={},
        )
    }
    assert maneuver_values == {"pursuit:maneuver"}
    assert extra_values == {"pursuit:additional_strike"}


def test_additional_strike_grants_one_additional_strike_via_the_full_strike_machinery():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("CEL",)
    )
    p1.hand.append(_pursuit_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    actor = ScriptedAgent("P1")
    # V1 also qualifies for the `[cel]` maneuver clause (superior Celerity
    # satisfies the basic check too) and holds the only copy in hand, so
    # `_determine_range` offers it first; decline it so the one physical
    # copy stays in hand for the `[CEL]` additional-strike clause below.
    actor.expect("maneuver_choice", hooks.PASS_VALUE)
    actor.expect("strike_choice", "hand_strike")  # normal pair: a plain hand strike
    actor.expect("additional_strike_choice", "pursuit:additional_strike")
    actor.expect("strike_choice", "hand_strike")  # the additional strike itself
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.zone_of("B1") == "torpor"
    assert game.zone_of("V1") == "ready"
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_limited_blocks_a_second_copy_in_the_same_round():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("CEL",)
    )
    p1.hand.append(_pursuit_card())
    p1.hand.append(_pursuit_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    round_state: dict = {}
    first = hooks.offer(
        COMBAT_ADDITIONAL_STRIKE_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        round_state=round_state,
    )
    assert {o.choice.value for o in first} == {"pursuit:additional_strike"}
    first[0].apply(game.state)  # play the first copy.

    second = hooks.offer(
        COMBAT_ADDITIONAL_STRIKE_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        round_state=round_state,
    )
    assert second == []  # the second copy's [CEL] clause is not offered again.
    assert len(game.state.players["P1"].hand) == 1  # second copy stayed unused in hand


def test_limited_does_not_restrict_the_maneuver_clause():
    """The "(limited)" restriction is printed only on the `[CEL]`
    additional-strike line; the `[cel]` maneuver clause carries no such
    restriction and remains offered after the additional-strike grant has
    been used."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("CEL",)
    )
    p1.hand.append(_pursuit_card())
    p1.hand.append(_pursuit_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    round_state: dict = {}
    extra = hooks.offer(
        COMBAT_ADDITIONAL_STRIKE_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        round_state=round_state,
    )
    extra[0].apply(game.state)  # consume the "(limited)" additional-strike grant.

    maneuver = hooks.offer(
        MANEUVER_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        opponent="B1",
        combat_state={},
        round_state=round_state,
    )
    assert {o.choice.value for o in maneuver} == {"pursuit:maneuver"}


# --- RUL-008 resolution: a plain maneuver, not "a maneuver from a strike" -----


def test_maneuvering_with_pursuit_does_not_lock_the_strike_choice():
    """Rulebook §4 Combat > Strike > Choose Strike: the "cannot choose any
    other strike" lock applies only to "a maneuver from a strike (either a
    strike card or a weapon)" -- Pursuit's bare "[cel] Maneuver." clause is
    not one (module docstring, RUL-008). After maneuvering with it, the acting
    vampire is still offered, and can use, an ordinary hand strike the same
    round."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("cel",)
    )
    p1.hand.append(_pursuit_card())
    # B1 starts already wounded (0 blood, cannot mend) so the single hand
    # strike below sends it straight to torpor, ending combat at once
    # without a press step -- keeps this test focused on the maneuver/strike
    # interaction, not on an unrelated multi-round sequence.
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0, wounded=True)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("maneuver_choice", "pursuit:maneuver")
    actor.expect("strike_choice", "hand_strike")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    # The maneuver was used (range flipped to long) *and* the hand strike
    # landed normally -- neither was blocked by the other.
    assert game.zone_of("B1") == "torpor"
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_a_second_copy_can_maneuver_again_after_the_opponent_counter_maneuvers():
    """Not "a maneuver from a strike", so neither the Determine Range "cannot
    use a second strike card or weapon to maneuver again" cap nor any
    once-per-round restriction applies: a second physical copy may be played
    later in the same round, in response to the opponent's own
    counter-maneuver, exactly like the Rulebook's own Ayelech/Colette worked
    example for any registered maneuver source."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("cel",)
    )
    p1.hand.append(_pursuit_card())
    p1.hand.append(_pursuit_card())
    # B1 starts already wounded (0 blood, cannot mend) so the final hand
    # strike below sends it straight to torpor, ending combat at once
    # without a press step.
    p2 = builder.player("P2", pool=30).ready_vampire(
        "B1", capacity=3, blood=0, disciplines=("cel",), wounded=True
    )
    p2.hand.append(_pursuit_card())
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("maneuver_choice", "pursuit:maneuver")  # P1: close -> long
    actor.expect("maneuver_choice", "pursuit:maneuver")  # P1: long -> close again
    actor.expect("strike_choice", "hand_strike")
    defender = ScriptedAgent("P2")
    defender.expect("maneuver_choice", "pursuit:maneuver")  # P2: long -> close
    # P2's single copy is now spent: no further "maneuver_choice" decision is
    # raised for P2 at all (no options => no Decision, CLAUDE.md "only when
    # needed") -- the loop's own consecutive-decline counter advances
    # silently instead.
    defender.expect("strike_choice", "no_strike")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.zone_of("B1") == "torpor"
    assert game.state.players["P1"].hand == []  # both copies played
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME, NAME]
    assert game.state.players["P2"].hand == []
    assert [c.name for c in game.state.players["P2"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()
