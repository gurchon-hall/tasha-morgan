"""Rolling with the Punches (krcg id 101649,
`src/vtesbot/cards/rolling_with_the_punches.py`).

Card text: "[for] Prevent 1 damage.\n[FOR] Burn 1 blood to prevent all
damage from the opposing minion's strikes this round." Rulings:
"[FOR]The burn blood effect is not reduced by effects that reduce the
cost of the card (eg. {Adana de Sforza}). [ANK 20210226]"; "[FOR]The card
cannot be played if the minion cannot afford to burn the blood. [ANK
20210226]"; "Cannot be used if there is no damage to prevent. [LSJ
20001114]".

One assertion per clause/gate: the basic clause's own discipline/hand/
"damage to prevent" gates, that it prevents either damage type (no
"non-aggravated" qualifier, unlike Soak), end-to-end behaviour through
`apply_damage`, the mixed-normal-and-aggravated engine-invariant guard,
and the superior clause's own discipline/blood gates, blood burn, current-
strike zeroing, and round-scoped mandatory-automatic-prevention activation
(ENG-036, resolved).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.rolling_with_the_punches import KRCG_ID, _prevent_one_point
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.damage import (
    DAMAGE_PREVENTION_HOOK,
    apply_damage,
    mandatory_full_prevention_active,
)

NAME = "Rolling with the Punches"


def _rwtp_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="combat")


def _game(*, disciplines: tuple[str, ...] = ("for",), blood: int = 0, with_card: bool = True):
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=blood, disciplines=disciplines
    )
    if with_card:
        p1.hand.append(_rwtp_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    return builder.build()


def _offer(game, damage: dict[str, int]):
    return hooks.offer(
        DAMAGE_PREVENTION_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        damage=damage,
        combat_state=None,
        round_state=None,
    )


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.name == NAME
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.blocked_reason is None
    assert registry.Hook.DAMAGE_PREVENTION in reg.hooks


# --- "[for] Prevent 1 damage." ----------------------------------------------


def test_basic_not_offered_without_for():
    game = _game(disciplines=())
    assert _offer(game, {"normal": 1, "aggravated": 0}) == []


def test_basic_not_offered_without_the_card_in_hand():
    game = _game(with_card=False)
    assert _offer(game, {"normal": 1, "aggravated": 0}) == []


def test_basic_not_offered_with_no_damage_to_prevent():
    """ "Cannot be used if there is no damage to prevent." [LSJ 20001114]"""
    game = _game()
    assert _offer(game, {"normal": 0, "aggravated": 0}) == []


def test_basic_offered_with_normal_damage_and_prevents_1_point():
    game = _game()
    damage = {"normal": 1, "aggravated": 0}
    options = _offer(game, damage)
    assert {o.choice.value for o in options} == {"rolling_with_the_punches:basic"}

    options[0].apply(game.state)

    assert damage == {"normal": 0, "aggravated": 0}
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]


def test_basic_prevents_only_1_of_several_points():
    game = _game()
    damage = {"normal": 3, "aggravated": 0}
    options = _offer(game, damage)

    options[0].apply(game.state)

    assert damage == {"normal": 2, "aggravated": 0}


def test_basic_also_prevents_aggravated_damage_alone():
    """No "non-aggravated" qualifier on this card's text, unlike Soak --
    "Prevent 1 damage" covers either type."""
    game = _game()
    damage = {"normal": 0, "aggravated": 1}
    options = _offer(game, damage)
    assert {o.choice.value for o in options} == {"rolling_with_the_punches:basic"}

    options[0].apply(game.state)

    assert damage == {"normal": 0, "aggravated": 0}


def test_basic_also_offered_with_superior_for():
    """Superior Fortitude presence satisfies the basic-level discipline
    check too (Rulebook §3 "may opt to use either effect")."""
    game = _game(disciplines=("FOR",))
    options = _offer(game, {"normal": 1, "aggravated": 0})
    assert {o.choice.value for o in options} == {"rolling_with_the_punches:basic"}


def test_mixed_normal_and_aggravated_damage_raises_an_engine_invariant_error():
    """No production call site (`engine/combat.py::_resolve_strike_pair`)
    ever passes both types positive at once -- this is an engine
    invariant violation, not a ruling ambiguity to silently resolve."""
    import pytest

    damage = {"normal": 1, "aggravated": 1}
    with pytest.raises(AssertionError):
        _prevent_one_point(damage)


# --- End-to-end through `apply_damage` --------------------------------------


def test_using_it_prevents_a_wound_end_to_end():
    """No second "pass" decision follows: once there is nothing left to
    prevent, the "damage to prevent" gate [LSJ 20001114] stops the option
    from being offered again at all (unlike a provider with no such gate,
    `tests/rules/test_damage_prevention_hook.py`'s own fake one)."""
    game = _game()
    agent = ScriptedAgent("P1")
    agent.expect(DAMAGE_PREVENTION_HOOK, "rolling_with_the_punches:basic")
    game.state.agents["P1"] = agent

    game.apply_damage(target="V1", normal=1)

    assert game.vampire("V1").wounded is False
    agent.assert_exhausted()


def test_declining_it_leaves_damage_unchanged():
    game = _game()
    agent = ScriptedAgent("P1").expect(DAMAGE_PREVENTION_HOOK, "pass")
    game.state.agents["P1"] = agent

    game.apply_damage(target="V1", normal=1)

    assert game.vampire("V1").wounded is True
    agent.assert_exhausted()


# --- "[FOR] Burn 1 blood to prevent all damage ... this round." (ENG-036) ----


def _offer_both(game, damage: dict[str, int], round_state: dict | None = None):
    return hooks.offer(
        DAMAGE_PREVENTION_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        damage=damage,
        round_state=round_state,
        combat_state=None,
    )


def test_superior_not_offered_with_basic_for_only():
    """Only the basic clause's discipline check is satisfied by `"for"`;
    the superior clause additionally requires `"FOR"`."""
    game = _game(disciplines=("for",), blood=5)
    options = _offer_both(game, {"normal": 1, "aggravated": 0})
    assert {o.choice.value for o in options} == {"rolling_with_the_punches:basic"}


def test_superior_not_offered_without_blood_to_burn():
    """ "[FOR]The card cannot be played if the minion cannot afford to burn
    the blood. [ANK 20210226]" """
    game = _game(disciplines=("FOR",), blood=0)
    options = _offer_both(game, {"normal": 1, "aggravated": 0})
    assert {o.choice.value for o in options} == {"rolling_with_the_punches:basic"}


def test_both_levels_offered_with_superior_for_and_blood():
    """Rulebook §3 "may opt to use either the basic ... or the superior ...
    effect": superior Fortitude with blood available sees both options."""
    game = _game(disciplines=("FOR",), blood=1)
    options = _offer_both(game, {"normal": 1, "aggravated": 0})
    assert {o.choice.value for o in options} == {
        "rolling_with_the_punches:basic",
        "rolling_with_the_punches:superior",
    }


def test_superior_burns_1_blood():
    game = _game(disciplines=("FOR",), blood=2)
    options = _offer_both(game, {"normal": 1, "aggravated": 0})
    superior = next(o for o in options if o.choice.value == "rolling_with_the_punches:superior")

    superior.apply(game.state)

    assert game.vampire("V1").blood == 1
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]


def test_superior_zeroes_the_current_normal_strike():
    """ "prevent all damage from the opposing minion's strikes this round"
    has no carve-out for the triggering strike itself."""
    game = _game(disciplines=("FOR",), blood=1)
    damage = {"normal": 3, "aggravated": 0}
    options = _offer_both(game, damage)
    superior = next(o for o in options if o.choice.value == "rolling_with_the_punches:superior")

    superior.apply(game.state)

    assert damage == {"normal": 0, "aggravated": 0}


def test_superior_zeroes_the_current_aggravated_strike():
    """Same as the normal case, but for an aggravated strike -- the two
    types are never simultaneously positive in this engine (see
    `test_mixed_normal_and_aggravated_damage_raises_an_engine_invariant_error`),
    so each is exercised on its own."""
    game = _game(disciplines=("FOR",), blood=1)
    damage = {"normal": 0, "aggravated": 2}
    options = _offer_both(game, damage)
    superior = next(o for o in options if o.choice.value == "rolling_with_the_punches:superior")

    superior.apply(game.state)

    assert damage == {"normal": 0, "aggravated": 0}


def test_superior_activates_mandatory_full_prevention_for_the_round():
    game = _game(disciplines=("FOR",), blood=1)
    round_state: dict = {}
    damage = {"normal": 1, "aggravated": 0}
    options = _offer_both(game, damage, round_state=round_state)
    superior = next(o for o in options if o.choice.value == "rolling_with_the_punches:superior")

    superior.apply(game.state)

    assert mandatory_full_prevention_active(round_state, "V1") is True


def test_superior_cap_is_unenforced_without_a_round_state():
    """Missing `round_state` degrades to a no-op mark (same convention as
    every other round-scoped cap in this codebase); the immediate zeroing
    of the current strike's own `damage_box` still happens regardless."""
    game = _game(disciplines=("FOR",), blood=1)
    damage = {"normal": 1, "aggravated": 0}
    options = _offer_both(game, damage, round_state=None)
    superior = next(o for o in options if o.choice.value == "rolling_with_the_punches:superior")

    superior.apply(game.state)

    assert damage == {"normal": 0, "aggravated": 0}


def test_superior_prevents_every_later_strike_this_round_automatically_end_to_end():
    """ENG-036's resolved gap: once chosen, every later `apply_damage` call
    this round against the same vampire is fully prevented with no further
    `DAMAGE_PREVENTION_HOOK` decision asked at all -- an exhausted
    `ScriptedAgent` with no further expectations would raise if one were.
    Mirrors `tests/rules/test_damage_prevention_hook.py`'s own
    `test_mandatory_full_prevention_is_automatic_for_the_rest_of_the_round`.
    """
    game = _game(disciplines=("FOR",), blood=1)
    round_state: dict = {}

    agent_first = ScriptedAgent("P1")
    agent_first.expect(DAMAGE_PREVENTION_HOOK, "rolling_with_the_punches:superior")
    game.state.agents["P1"] = agent_first
    apply_damage(game.state, "P1", game.vampire("V1"), normal=1, round_state=round_state)
    agent_first.assert_exhausted()

    assert game.vampire("V1").wounded is False
    assert game.vampire("V1").blood == 0

    # Same round, a fresh strike with both normal and aggravated damage:
    # fully zeroed before `DAMAGE_PREVENTION_HOOK` even dispatches.
    agent_second = ScriptedAgent("P1")
    game.state.agents["P1"] = agent_second
    apply_damage(
        game.state,
        "P1",
        game.vampire("V1"),
        normal=2,
        aggravated=1,
        round_state=round_state,
    )
    agent_second.assert_exhausted()

    assert game.vampire("V1").wounded is False
    assert game.vampire("V1").zone == "ready"
