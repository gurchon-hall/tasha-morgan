"""Soak (krcg id 101817, `src/vtesbot/cards/soak.py`).

Card text: "A vampire can play only one Soak each round.\n[for] Prevent 2
non-aggravated damage.\n[FOR] Prevent 4 non-aggravated damage." Rulings:
cannot prevent aggravated damage [LSJ 20040812-2] [PIB 20130327]; preventing
more than the damage resolved still prevents all of it [RTR 20041202];
unused prevention points don't carry over [ANK 20200318] [LSJ 20001114];
cannot be used with no damage to prevent [LSJ 20001114].

One assertion per clause/ruling: basic/superior prevention math, the
non-aggravated-only restriction, no-carryover, the "nothing to prevent"
gate, and the once-per-round cap (OQ-55, now resolved) holding across two
separate damage instances to the same vampire within one round.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.soak import KRCG_ID, _prevent_non_aggravated
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.damage import DAMAGE_PREVENTION_HOOK, apply_damage

NAME = "Soak"


def _soak_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="combat")


def _game(*, disciplines: tuple[str, ...] = ("for",), with_card: bool = True):
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=3, blood=0, disciplines=disciplines
    )
    if with_card:
        p1.hand.append(_soak_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    return builder.build()


def _offer(game, damage: dict[str, int], round_state: dict | None = None):
    return hooks.offer(
        DAMAGE_PREVENTION_HOOK,
        game.state,
        player="P1",
        vampire="V1",
        damage=damage,
        round_state=round_state,
    )


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.name == NAME
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.blocked_reason is None
    assert registry.Hook.DAMAGE_PREVENTION in reg.hooks


# --- Gating --------------------------------------------------------------


def test_not_offered_without_fortitude():
    game = _game(disciplines=())
    assert _offer(game, {"normal": 2, "aggravated": 0}) == []


def test_not_offered_without_the_card_in_hand():
    game = _game(with_card=False)
    assert _offer(game, {"normal": 2, "aggravated": 0}) == []


def test_not_offered_with_no_damage_to_prevent():
    """ "Cannot be used if there is no damage to prevent." [LSJ 20001114]"""
    game = _game()
    assert _offer(game, {"normal": 0, "aggravated": 0}) == []


def test_not_offered_with_only_aggravated_damage():
    """Cannot prevent aggravated damage [LSJ 20040812-2] [PIB 20130327]:
    gated on `damage_box["normal"]`, so pure aggravated damage offers
    nothing to prevent at all."""
    game = _game(disciplines=("FOR",))
    assert _offer(game, {"normal": 0, "aggravated": 2}) == []


# --- Basic clause: "[for] Prevent 2 non-aggravated damage." --------------


def test_basic_offered_with_basic_fortitude_only():
    game = _game(disciplines=("for",))
    options = _offer(game, {"normal": 2, "aggravated": 0})
    assert {o.choice.value for o in options} == {"soak:basic"}


def test_basic_prevents_2_normal_damage():
    game = _game()
    damage = {"normal": 2, "aggravated": 0}
    options = _offer(game, damage)
    basic = next(o for o in options if o.choice.value == "soak:basic")

    basic.apply(game.state)

    assert damage == {"normal": 0, "aggravated": 0}
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]


def test_basic_never_touches_aggravated_damage():
    """ "Prevent 2 non-aggravated damage" -- aggravated is left untouched
    even when present alongside normal damage."""
    game = _game()
    damage = {"normal": 2, "aggravated": 1}
    options = _offer(game, damage)
    basic = next(o for o in options if o.choice.value == "soak:basic")

    basic.apply(game.state)

    assert damage == {"normal": 0, "aggravated": 1}


def test_basic_prevents_at_most_what_remains_no_carryover():
    """Preventing more than resolved still prevents all of it [RTR
    20041202], and nothing carries over to a later hit [ANK 20200318]
    [LSJ 20001114] -- there is simply no leftover value stored anywhere."""
    game = _game()
    damage = {"normal": 1, "aggravated": 0}
    options = _offer(game, damage)
    basic = next(o for o in options if o.choice.value == "soak:basic")

    basic.apply(game.state)

    assert damage == {"normal": 0, "aggravated": 0}


# --- Superior clause: "[FOR] Prevent 4 non-aggravated damage." -----------


def test_superior_not_offered_with_basic_fortitude_only():
    game = _game(disciplines=("for",))
    options = _offer(game, {"normal": 2, "aggravated": 0})
    assert {o.choice.value for o in options} == {"soak:basic"}


def test_both_levels_offered_with_superior_fortitude():
    """Rulebook §3 "may opt to use either the basic ... or the superior
    ... effect": superior Fortitude sees both options, not only the
    stronger one."""
    game = _game(disciplines=("FOR",))
    options = _offer(game, {"normal": 4, "aggravated": 0})
    assert {o.choice.value for o in options} == {"soak:basic", "soak:superior"}


def test_superior_prevents_4_normal_damage():
    game = _game(disciplines=("FOR",))
    damage = {"normal": 4, "aggravated": 0}
    options = _offer(game, damage)
    superior = next(o for o in options if o.choice.value == "soak:superior")

    superior.apply(game.state)

    assert damage == {"normal": 0, "aggravated": 0}


def test_superior_prevents_at_most_what_remains_no_carryover():
    game = _game(disciplines=("FOR",))
    damage = {"normal": 1, "aggravated": 0}
    options = _offer(game, damage)
    superior = next(o for o in options if o.choice.value == "soak:superior")

    superior.apply(game.state)

    assert damage == {"normal": 0, "aggravated": 0}


def test_helper_never_touches_aggravated_directly():
    damage = {"normal": 0, "aggravated": 3}
    _prevent_non_aggravated(damage, 4)
    assert damage == {"normal": 0, "aggravated": 3}


# --- "A vampire can play only one Soak each round." (OQ-55, resolved) ----


def test_once_per_round_cap_blocks_a_second_offer_within_the_same_round():
    game = _game(disciplines=("FOR",))
    round_state: dict = {}
    damage = {"normal": 4, "aggravated": 0}
    options = _offer(game, damage, round_state=round_state)
    options[0].apply(game.state)

    assert round_state["soak_used"] == {"V1": True}
    # Same round, same vampire: no option offered even with a fresh Soak
    # in hand and fresh damage to prevent.
    game.state.players["P1"].hand.append(_soak_card())
    assert _offer(game, {"normal": 4, "aggravated": 0}, round_state=round_state) == []


def test_cap_is_unenforced_without_a_round_state():
    """Missing `round_state` degrades to "not used" (same convention as
    every other round-scoped cap in this codebase, e.g.
    `engine/combat.py::additional_strike_limit_used`)."""
    game = _game(disciplines=("FOR",))
    options = _offer(game, {"normal": 4, "aggravated": 0}, round_state=None)
    assert {o.choice.value for o in options} == {"soak:basic", "soak:superior"}


def test_once_per_round_cap_survives_two_separate_damage_instances_end_to_end():
    """OQ-55's own motivating gap: an additional-strike pair can land a
    second hit on the same vampire within one round. Mirrors
    `tests/rules/test_damage_prevention_hook.py`'s two-call pattern
    directly against `apply_damage`."""
    game = _game(disciplines=("FOR",))
    round_state: dict = {}

    agent_first = ScriptedAgent("P1")
    agent_first.expect(DAMAGE_PREVENTION_HOOK, "soak:superior")
    game.state.agents["P1"] = agent_first
    apply_damage(game.state, "P1", game.vampire("V1"), normal=4, round_state=round_state)
    agent_first.assert_exhausted()

    assert game.vampire("V1").wounded is False
    assert game.state.players["P1"].hand == []

    # Same round, a second hit on the same vampire: no Soak option is
    # offered at all (the cap, not a missing card), even though the
    # vampire still has the discipline to use it.
    agent_second = ScriptedAgent("P1")
    game.state.agents["P1"] = agent_second
    apply_damage(game.state, "P1", game.vampire("V1"), normal=1, round_state=round_state)
    agent_second.assert_exhausted()

    assert game.vampire("V1").wounded is True


def test_once_per_round_cap_is_per_vampire_not_per_player():
    game = ScenarioBuilder(seed=1)
    p1 = (
        game.player("P1", pool=30)
        .ready_vampire("V1", capacity=3, blood=0, disciplines=("FOR",))
        .ready_vampire("V2", capacity=3, blood=0, disciplines=("FOR",))
    )
    p1.hand.append(_soak_card())
    p1.hand.append(_soak_card())
    game.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    built = game.build()

    round_state: dict = {}
    options_v1 = hooks.offer(
        DAMAGE_PREVENTION_HOOK,
        built.state,
        player="P1",
        vampire="V1",
        damage={"normal": 4, "aggravated": 0},
        round_state=round_state,
    )
    options_v1[0].apply(built.state)

    options_v2 = hooks.offer(
        DAMAGE_PREVENTION_HOOK,
        built.state,
        player="P1",
        vampire="V2",
        damage={"normal": 4, "aggravated": 0},
        round_state=round_state,
    )
    assert {o.choice.value for o in options_v2} == {"soak:basic", "soak:superior"}
