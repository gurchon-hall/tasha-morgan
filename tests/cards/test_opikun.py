"""Opikun (krcg id 201680, `src/vtesbot/cards/opikun.py`).

Card text: "Independent: Once each combat involving a vampire you control,
Opikun can burn 1 blood to prevent up to 2 non-aggravated damage to that
vampire from the opposing minion's strike." Rulings: usable while in torpor
[LSJ 20011022]; cannot prevent aggravated damage even if the minion treats
it as normal damage [LSJ 20040812-2] [PIB 20130327].

One assertion per clause/ruling: not offered outside an active combat (no
`combat_state`), not offered with no normal damage to prevent, not offered
without Opikun in play or without enough blood, usable while Opikun is in
torpor, the "up to 2"/cost-1-blood math, the non-aggravated-only
restriction, the once-per-combat cap (both for a single copy and
independently for two separate copies), and the "you control" scoping
(Opikun belongs to the damaged vampire's own controller).
"""

from helpers import ScenarioBuilder
from vtesbot.cards import registry
from vtesbot.cards.opikun import KRCG_ID
from vtesbot.engine import CryptCard, hooks
from vtesbot.engine.damage import DAMAGE_PREVENTION_HOOK

NAME = "Opikun"


def _make_opikun(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Opikun's real printed
    identity (`CryptCard` is frozen)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name=NAME,
        capacity=5,
        group=7,
        clan="Salubri",
        disciplines=("aus", "dom", "FOR"),
    )


def _offer(game, *, damage, combat_state=None, vampire="V1"):
    return hooks.offer(
        DAMAGE_PREVENTION_HOOK,
        game.state,
        player="P1",
        vampire=vampire,
        damage=damage,
        combat_state=combat_state,
        round_state=None,
    )


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.name == NAME
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.blocked_reason is None
    assert registry.Hook.DAMAGE_PREVENTION in reg.hooks


# --- Gating ----------------------------------------------------------------


def test_not_offered_without_an_active_combat_state():
    """ "From the opposing minion's strike": only strike damage dispatched
    from inside a real combat threads a `combat_state`."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    p1.ready_vampire("V1", capacity=5, blood=2)
    _make_opikun(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game, damage={"normal": 2, "aggravated": 0}, combat_state=None, vampire="D1")

    assert options == []


def test_not_offered_with_no_normal_damage_to_prevent():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    p1.ready_vampire("V1", capacity=5, blood=2)
    _make_opikun(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game, damage={"normal": 0, "aggravated": 0}, combat_state={}, vampire="D1")

    assert options == []


def test_not_offered_without_opikun_in_play():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game, damage={"normal": 2, "aggravated": 0}, combat_state={}, vampire="D1")

    assert options == []


def test_not_offered_without_enough_blood():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    p1.ready_vampire("V1", capacity=5, blood=0)
    _make_opikun(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game, damage={"normal": 2, "aggravated": 0}, combat_state={}, vampire="D1")

    assert options == []


def test_usable_while_opikun_is_in_torpor():
    """ "The ability can be used when in torpor." [LSJ 20011022]"""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    p1.torpid_vampire("V1", capacity=5, blood=2)
    _make_opikun(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game, damage={"normal": 2, "aggravated": 0}, combat_state={}, vampire="D1")

    assert [o.choice.value for o in options] == ["opikun:V1"]


def test_not_offered_for_the_opponents_own_vampire():
    """ "A vampire you control": Opikun belongs to P2, the damaged vampire
    (D1) belongs to P1 -- the hook is offered to D1's own controller (P1),
    whose own vampires do not include this Opikun."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    p2 = builder.player("P2", pool=30).ready_vampire("V1", capacity=5, blood=2)
    _make_opikun(p2, "V1")
    game = builder.build()

    options = _offer(game, damage={"normal": 2, "aggravated": 0}, combat_state={}, vampire="D1")

    assert options == []


# --- "burn 1 blood to prevent up to 2 non-aggravated damage" ---------------


def test_prevents_up_to_2_normal_damage_and_burns_1_blood():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    p1.ready_vampire("V1", capacity=5, blood=2)
    _make_opikun(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()
    damage = {"normal": 2, "aggravated": 0}
    (option,) = _offer(game, damage=damage, combat_state={}, vampire="D1")

    option.apply(game.state)

    assert damage == {"normal": 0, "aggravated": 0}
    assert game.blood_of("V1") == 1


def test_prevention_is_clamped_up_to_the_damage_actually_present():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    p1.ready_vampire("V1", capacity=5, blood=2)
    _make_opikun(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()
    damage = {"normal": 1, "aggravated": 0}
    (option,) = _offer(game, damage=damage, combat_state={}, vampire="D1")

    option.apply(game.state)

    assert damage == {"normal": 0, "aggravated": 0}
    assert game.blood_of("V1") == 1


def test_never_touches_aggravated_damage():
    """Cannot prevent aggravated damage, even alongside normal damage.
    [LSJ 20040812-2] [PIB 20130327]"""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    p1.ready_vampire("V1", capacity=5, blood=2)
    _make_opikun(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()
    damage = {"normal": 2, "aggravated": 1}
    (option,) = _offer(game, damage=damage, combat_state={}, vampire="D1")

    option.apply(game.state)

    assert damage == {"normal": 0, "aggravated": 1}


def test_not_offered_with_only_aggravated_damage():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    p1.ready_vampire("V1", capacity=5, blood=2)
    _make_opikun(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer(game, damage={"normal": 0, "aggravated": 2}, combat_state={}, vampire="D1")

    assert options == []


# --- "Once each combat" -----------------------------------------------------


def test_once_per_combat_cap_blocks_a_second_offer_within_the_same_combat():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    p1.ready_vampire("V1", capacity=5, blood=2)
    _make_opikun(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()
    combat_state: dict = {}
    damage = {"normal": 1, "aggravated": 0}
    (option,) = _offer(game, damage=damage, combat_state=combat_state, vampire="D1")
    option.apply(game.state)

    assert combat_state["opikun_used_this_combat"] == {"V1"}
    # Same combat, a second strike against the same vampire: no option
    # offered even though Opikun still has blood left.
    damage_2 = {"normal": 1, "aggravated": 0}
    assert _offer(game, damage=damage_2, combat_state=combat_state, vampire="D1") == []


def test_cap_does_not_carry_to_a_fresh_combat_state():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    p1.ready_vampire("V1", capacity=5, blood=2)
    _make_opikun(p1, "V1")
    builder.player("P2", pool=30)
    game = builder.build()
    (option,) = _offer(game, damage={"normal": 1, "aggravated": 0}, combat_state={}, vampire="D1")
    option.apply(game.state)

    # A different combat (fresh `combat_state` dict): usable again.
    options = _offer(game, damage={"normal": 1, "aggravated": 0}, combat_state={}, vampire="D1")

    assert len(options) == 1


def test_two_separate_copies_of_opikun_each_get_their_own_once_per_combat_use():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("D1", capacity=3, blood=0)
    p1.ready_vampire("V1", capacity=5, blood=2).ready_vampire("V2", capacity=5, blood=2)
    _make_opikun(p1, "V1")
    _make_opikun(p1, "V2")
    builder.player("P2", pool=30)
    game = builder.build()
    combat_state: dict = {}

    damage = {"normal": 1, "aggravated": 0}
    options = _offer(game, damage=damage, combat_state=combat_state, vampire="D1")
    assert {o.choice.value for o in options} == {"opikun:V1", "opikun:V2"}

    used = next(o for o in options if o.choice.value == "opikun:V1")
    used.apply(game.state)

    remaining = _offer(
        game, damage={"normal": 1, "aggravated": 0}, combat_state=combat_state, vampire="D1"
    )
    assert {o.choice.value for o in remaining} == {"opikun:V2"}
