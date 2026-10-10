"""Dust Up (krcg id 100597, `src/vtesbot/cards/dust_up.py`).

Card text: "Requires an Anarch.\n[ani] Strike: hand strike at +1 damage. This
strike cannot be dodged.\n[cel] Strike: dodge, with 1 additional strike
(limited).\n[pot] Strike: hand strike at +2 damage." Rulings: "[ani] [pot]
Additional damage inherits all of the properties of the base damage." [TOM
19960225]; "[cel] The additional strike is not optional: you cannot play it
for the dodge only if you already played it for a (limited) additional
strike this round." [ANK 20220204]; "[ani] Does not prevent the opponent
from dodging, the dodge just has no effect." [LSJ 20030902-2] [LSJ
20060808-1].

One assertion per clause/qualifier/ruling: the "Requires an Anarch" card-level
gate (independent of discipline clause); each clause's own discipline gate
(`[ani]`/`[cel]`/`[pot]`) and "card in hand" gate; `[ani]`'s +1-over-base,
dodge-proof damage (lands through a dodge, stacks with a live strength
modifier); `[pot]`'s +2-over-base, ordinary dodgeable damage; `[cel]`'s
dodge protecting against the opponent's simultaneous strike, its grant of
one additional strike claimed through the engine's own full strike-choice
machinery, and the "(limited)" restriction (a second copy is not offered
again once the first has been played, within the same round).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.dust_up import KRCG_ID
from vtesbot.engine import CryptCard, LibraryCard, Sect, hooks
from vtesbot.engine.combat import (
    COMBAT_DODGE_OPTION_HOOK,
    COMBAT_STRENGTH_MODIFIER_HOOK,
    COMBAT_STRIKE_OPTION_HOOK,
    StrikeDamage,
    run_combat,
)
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption

NAME = "Dust Up"


def _dust_up_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="combat")


def _set_sect(builder_player, instance_id: str, sect: Sect | None) -> None:
    """Replace the just-built vampire's `card` with one carrying `sect`
    (mirrors `test_grooming_the_protege.py::_set_clan`: neither
    `ready_vampire`/`uncontrolled_vampire` has a `sect=` parameter, and
    `CryptCard` is frozen, so a fresh instance is swapped in, preserving
    every other field)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    old = vampire.card
    vampire.card = CryptCard(
        krcg_id=old.krcg_id,
        name=old.name,
        capacity=old.capacity,
        group=old.group,
        clan=old.clan,
        title=old.title,
        disciplines=old.disciplines,
        sect=sect,
    )


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


# --- "Requires an Anarch" -- card-level gate, independent of clause --------


def test_anarch_gate_blocks_all_three_clauses_for_a_non_anarch_vampire():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("ani", "cel", "pot")
    )
    _set_sect(p1, "V1", Sect.CAMARILLA)
    p1.hand.append(_dust_up_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    strike_options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    dodge_options = hooks.offer(
        COMBAT_DODGE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )

    assert strike_options == []
    assert dodge_options == []


def test_anarch_gate_blocks_all_three_clauses_when_sect_is_unset():
    """`CryptCard.sect` defaults to `None`; a card gating on sect must treat
    that as "does not qualify," never guess a default sect."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("ani", "cel", "pot")
    )
    p1.hand.append(_dust_up_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    assert game.vampire("V1").card.sect is None
    strike_options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    assert strike_options == []


def test_anarch_gate_allows_all_three_clauses_for_an_anarch_vampire():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("ani", "cel", "pot")
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_dust_up_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    strike_values = {
        o.choice.value
        for o in hooks.offer(
            COMBAT_STRIKE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
        )
    }
    dodge_values = {
        o.choice.value
        for o in hooks.offer(
            COMBAT_DODGE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
        )
    }

    assert strike_values == {"dust_up:ani", "dust_up:pot"}
    assert dodge_values == {"dust_up:cel"}


# --- Discipline-level gating, per clause ------------------------------------


def test_ani_not_offered_without_ani():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("cel", "pot")
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_dust_up_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(
            COMBAT_STRIKE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
        )
    }
    assert "dust_up:ani" not in values


def test_pot_not_offered_without_pot():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("ani", "cel")
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_dust_up_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    values = {
        o.choice.value
        for o in hooks.offer(
            COMBAT_STRIKE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
        )
    }
    assert "dust_up:pot" not in values


def test_cel_dodge_not_offered_without_cel():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("ani", "pot")
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_dust_up_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        COMBAT_DODGE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    assert options == []


def test_no_clause_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("ani", "cel", "pot")
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    strike_options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    dodge_options = hooks.offer(
        COMBAT_DODGE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    assert strike_options == []
    assert dodge_options == []


# --- "[ani] Strike: hand strike at +1 damage. This strike cannot be dodged."


def test_ani_deals_base_damage_plus_one_and_flags_ignore_dodge():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("ani",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_dust_up_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    option = next(o for o in options if o.choice.value == "dust_up:ani")
    result = option.apply(game.state)

    assert result == StrikeDamage(amount=2, ignore_dodge=True)  # base(1) + 1
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]


def test_ani_damage_stacks_with_a_live_strength_modifier():
    """ "[ani] [pot] Additional damage inherits all of the properties of the
    base damage." [TOM 19960225]: the +1 stacks with, rather than replaces,
    any other strength bonus already in play."""

    def plus_one_strength(state, context):
        return 1 if context.get("player") == "P1" else 0

    hooks.register(COMBAT_STRENGTH_MODIFIER_HOOK, plus_one_strength)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire(
            "V1", capacity=3, blood=0, disciplines=("ani",)
        )
        _set_sect(p1, "V1", Sect.ANARCH)
        p1.hand.append(_dust_up_card())
        builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
        game = builder.build()

        options = hooks.offer(
            COMBAT_STRIKE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
        )
        option = next(o for o in options if o.choice.value == "dust_up:ani")
        result = option.apply(game.state)

        assert result == StrikeDamage(amount=3, ignore_dodge=True)  # base(1) + mod(1) + 1
    finally:
        hooks.unregister(COMBAT_STRENGTH_MODIFIER_HOOK, plus_one_strength)


def test_ani_strike_still_damages_a_dodging_opponent():
    """ "[ani] Does not prevent the opponent from dodging, the dodge just has
    no effect." [LSJ 20030902-2] [LSJ 20060808-1]: the opponent may still
    choose to dodge, but it has zero effect against this strike."""

    def fake_dodge(state, context):
        if context.get("player") != "P2":
            return []
        return [HookOption(choice=Choice("fake_dodge", "Fake dodge"), apply=lambda s: None)]

    hooks.register(COMBAT_DODGE_OPTION_HOOK, fake_dodge)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire(
            "V1", capacity=3, blood=0, disciplines=("ani",)
        )
        _set_sect(p1, "V1", Sect.ANARCH)
        p1.hand.append(_dust_up_card())
        builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
        game = builder.build()

        actor = ScriptedAgent("P1")
        actor.expect("strike_choice", "dust_up:ani")
        actor.expect("press", "end_combat")
        defender = ScriptedAgent("P2")
        defender.expect("strike_choice", "fake_dodge")
        defender.expect("press", "end_combat")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = defender

        run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

        assert game.zone_of("B1") == "ready"
        assert game.vampire("B1").wounded is True  # damage landed despite the dodge
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister(COMBAT_DODGE_OPTION_HOOK, fake_dodge)


# --- "[pot] Strike: hand strike at +2 damage." ------------------------------


def test_pot_deals_base_damage_plus_two_and_is_dodgeable():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("pot",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_dust_up_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    option = next(o for o in options if o.choice.value == "dust_up:pot")
    result = option.apply(game.state)

    assert result == StrikeDamage(amount=3, ignore_dodge=False)  # base(1) + 2


def test_pot_strike_is_nullified_by_an_opponents_dodge():
    """Unlike `[ani]`, `[pot]` carries no `ignore_dodge` flag: it is an
    ordinary, fully dodgeable hand-strike substitute."""

    def fake_dodge(state, context):
        if context.get("player") != "P2":
            return []
        return [HookOption(choice=Choice("fake_dodge", "Fake dodge"), apply=lambda s: None)]

    hooks.register(COMBAT_DODGE_OPTION_HOOK, fake_dodge)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire(
            "V1", capacity=3, blood=0, disciplines=("pot",)
        )
        _set_sect(p1, "V1", Sect.ANARCH)
        p1.hand.append(_dust_up_card())
        builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
        game = builder.build()

        actor = ScriptedAgent("P1")
        actor.expect("strike_choice", "dust_up:pot")
        actor.expect("press", "end_combat")
        defender = ScriptedAgent("P2")
        defender.expect("strike_choice", "fake_dodge")
        defender.expect("press", "end_combat")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = defender

        run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

        assert game.zone_of("B1") == "ready"
        assert game.vampire("B1").wounded is False  # dodge nullified it
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister(COMBAT_DODGE_OPTION_HOOK, fake_dodge)


def test_pot_strike_lands_normally_without_a_dodge():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("pot",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_dust_up_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "dust_up:pot")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.zone_of("B1") == "ready"
    assert game.vampire("B1").wounded is True
    actor.assert_exhausted()
    defender.assert_exhausted()


# --- "[cel] Strike: dodge, with 1 additional strike (limited)." ------------


def test_cel_dodge_protects_against_the_opponents_simultaneous_strike():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire(
        "B1", capacity=3, blood=0, disciplines=("cel",)
    )
    _set_sect(p2, "B1", Sect.ANARCH)
    p2.hand.append(_dust_up_card())
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "dust_up:cel")
    defender.expect("additional_strike_choice", "pass")
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


def test_cel_dodge_grants_one_additional_strike_via_the_full_strike_machinery():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("cel",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_dust_up_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "dust_up:cel")  # normal pair: dodge + grant recorded
    actor.expect("additional_strike_choice", "dust_up:cel_additional_strike")
    actor.expect("strike_choice", "hand_strike")  # the additional strike itself
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    # B1 has no grant of its own: never asked `additional_strike_choice` at all.
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    # B1 took exactly one hit, from the additional strike (the normal pair's
    # dodge dealt no damage); V1 took none (B1 never struck at all).
    assert game.zone_of("B1") == "ready"
    assert game.vampire("B1").wounded is True
    assert game.zone_of("V1") == "ready"
    assert game.vampire("V1").wounded is False
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_cel_limited_blocks_a_second_copy_in_the_same_round():
    """ "[cel] The additional strike is not optional: you cannot play it for
    the dodge only if you already played it for a (limited) additional
    strike this round." [ANK 20220204]: once played once, a second physical
    copy is not offered again within the same round."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("cel",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_dust_up_card())
    p1.hand.append(_dust_up_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    first = hooks.offer(
        COMBAT_DODGE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    assert {o.choice.value for o in first} == {"dust_up:cel"}
    first[0].apply(game.state)  # play the first copy: dodge + grant recorded.

    second = hooks.offer(
        COMBAT_DODGE_OPTION_HOOK, game.state, player="P1", vampire="V1", opponent="B1"
    )
    assert second == []  # the second copy is not offered again this round.
    assert len(game.state.players["P1"].hand) == 1  # second copy stayed unused in hand


def test_cel_second_copy_not_offered_during_its_own_additional_strike_pair():
    """End-to-end version of the same restriction, through `run_combat`: the
    additional strike granted by the first copy does not re-offer `[cel]`
    for a second copy, so the vampire falls back to an ordinary hand strike."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=("cel",)
    )
    _set_sect(p1, "V1", Sect.ANARCH)
    p1.hand.append(_dust_up_card())
    p1.hand.append(_dust_up_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "dust_up:cel")  # copy #1
    actor.expect("additional_strike_choice", "dust_up:cel_additional_strike")
    actor.expect("strike_choice", "hand_strike")  # copy #2 not among the offered choices
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert len(game.state.players["P1"].hand) == 1  # the 2nd copy stayed unused in hand
    actor.assert_exhausted()
    defender.assert_exhausted()
