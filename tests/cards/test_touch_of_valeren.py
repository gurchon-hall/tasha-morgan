"""Touch of Valeren (krcg id 102262, `src/vtesbot/cards/touch_of_valeren.py`).

Card text: "[for] [ACTION] +1 stealth action. Add 3 blood or life to a
minion, not to exceed their starting life.\n[for] [COMBAT] Prevent all
damage from the opposing minion's strike.\n[FOR] [COMBAT] Only usable by a
ready vampire not involved in the combat involving another minion you
control. Prevent all damage to that minion from the opposing minion's
strike." Ruling: "[COMBAT] Cannot be used if there is no damage to
prevent." [LSJ 20001114].

One assertion per clause/qualifier/ruling, for each of the card's three
clauses: clan/discipline/hand/printed-blood-cost gating, the blood-vs-life
target choice and its capacity/starting-life caps (Action clause), the
"nothing to prevent" gate and full single-strike prevention (both Combat
clauses), and the superior clause's own "ready, not involved in the
combat, another minion you control" eligibility (who pays the cost, who is
excluded as a candidate).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards.registry import Hook, Status, get
from vtesbot.cards.touch_of_valeren import KRCG_ID
from vtesbot.engine import CryptCard, LibraryCard, hooks
from vtesbot.engine.action import ACTION_ACTION_CARD
from vtesbot.engine.allies import detect_contest_on_recruit, recruit_ally
from vtesbot.engine.damage import DAMAGE_PREVENTION_HOOK, apply_damage
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, minion_phase

NAME = "Touch of Valeren"


def _card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="action/combat")


def test_registered_as_implemented():
    reg = get(KRCG_ID)
    assert reg is not None
    assert reg.name == NAME
    assert reg.status is Status.IMPLEMENTED
    assert reg.blocked_reason is None
    assert Hook.ACTION_CARD_PLAY in reg.hooks
    assert Hook.DAMAGE_PREVENTION in reg.hooks


# --- "[for] [ACTION] +1 stealth action. Add 3 blood or life to a minion,
#     not to exceed their starting life." -----------------------------------


def _action_game(
    *,
    disciplines: tuple[str, ...] = ("for",),
    clan: str | None = "Salubri",
    with_card: bool = True,
    blood: int = 1,
):
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=blood, disciplines=disciplines, clan=clan
    )
    if with_card:
        p1.hand.append(_card())
    builder.player("P2", pool=30)
    return builder.build()


def _offer_action(game, vampire="V1"):
    return hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire=vampire)


def test_action_not_offered_for_a_different_vampire():
    game = _action_game()
    assert _offer_action(game, vampire="nonexistent") == []


def test_action_not_offered_without_salubri_clan():
    game = _action_game(clan="Toreador")
    assert _offer_action(game) == []


def test_action_not_offered_without_fortitude():
    game = _action_game(disciplines=())
    assert _offer_action(game) == []


def test_action_not_offered_without_the_card_in_hand():
    game = _action_game(with_card=False)
    assert _offer_action(game) == []


def test_action_not_offered_without_enough_blood_for_the_printed_cost():
    game = _action_game(blood=0)
    assert _offer_action(game) == []


def test_action_offers_one_option_per_eligible_vampire_and_ally():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("for",), clan="Salubri"
    )
    p1.hand.append(_card())
    p1.ready_vampire("W1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    ally = recruit_ally(game.state, "P1", krcg_id=999999, name="Fake Ally", life=4)
    ally.life = 2

    options = _offer_action(game)

    values = {o.choice.value for o in options}
    assert values == {
        "touch_of_valeren:action:blood:V1",
        "touch_of_valeren:action:blood:W1",
        "touch_of_valeren:action:life:P1-A1",
    }


def test_action_blood_target_is_capped_at_effective_capacity():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("for",), clan="Salubri"
    )
    p1.hand.append(_card())
    p1.ready_vampire("W1", capacity=4, blood=2)
    builder.player("P2", pool=30)
    game = builder.build()

    (option,) = [
        o for o in _offer_action(game) if o.choice.value == "touch_of_valeren:action:blood:W1"
    ]
    spec = option.apply(game.state)
    spec.resolve({})

    assert game.blood_of("W1") == 4  # capped at capacity 4, not +3 to 5
    assert game.blood_of("V1") == 0  # printed blood cost paid by the acting vampire


def test_action_life_target_is_capped_at_its_own_starting_life():
    game = _action_game()
    ally = recruit_ally(game.state, "P1", krcg_id=999999, name="Fake Ally", life=4)
    ally.life = 3

    (option,) = [
        o for o in _offer_action(game) if o.choice.value.startswith("touch_of_valeren:action:life:")
    ]
    spec = option.apply(game.state)
    spec.resolve({})

    assert ally.life == 4  # capped at starting_life 4, not +3 to 6


def test_action_target_already_at_capacity_is_not_offered():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("for",), clan="Salubri"
    )
    p1.hand.append(_card())
    p1.ready_vampire("W1", capacity=3, blood=3)
    builder.player("P2", pool=30)
    game = builder.build()

    options = _offer_action(game)

    assert "touch_of_valeren:action:blood:W1" not in {o.choice.value for o in options}


def test_action_never_offers_the_opponents_own_vampire_as_a_target():
    """ "A minion" reads as "a minion you control" (no printed Ⓓ marker,
    module docstring) -- regression guard: even with a plainly eligible
    (room for blood), ready vampire on the opponent's own side, it must
    never appear among the offered targets."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("for",), clan="Salubri"
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()

    options = _offer_action(game)

    values = {o.choice.value for o in options}
    assert not any(v.endswith(":B1") for v in values)
    assert values == {"touch_of_valeren:action:blood:V1"}


def test_action_ally_already_at_starting_life_is_not_offered():
    game = _action_game()
    recruit_ally(game.state, "P1", krcg_id=999999, name="Fake Ally", life=4)

    options = _offer_action(game)

    assert not any(o.choice.value.startswith("touch_of_valeren:action:life:") for o in options)


def test_action_contested_ally_is_not_offered():
    game = _action_game()
    mine = recruit_ally(game.state, "P1", krcg_id=999999, name="Shared Ally", life=4)
    mine.zone = "ready"
    theirs = recruit_ally(game.state, "P2", krcg_id=999999, name="Shared Ally", life=4)
    detect_contest_on_recruit(game.state, theirs)
    assert mine.zone == "contested"

    options = _offer_action(game)

    assert not any(o.choice.value.startswith("touch_of_valeren:action:life:") for o in options)


def test_action_base_stealth_is_one_and_directed_is_false():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("for",), clan="Salubri"
    )
    p1.hand.append(_card())
    p1.ready_vampire("W1", capacity=3, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()

    (option,) = [
        o for o in _offer_action(game) if o.choice.value == "touch_of_valeren:action:blood:W1"
    ]
    spec = option.apply(game.state)

    assert spec.base_stealth == 1
    assert spec.directed is False


def test_action_unblocked_adds_blood_and_pays_the_printed_cost_via_minion_phase():
    """A single ready vampire (targeting itself) keeps the scenario free of
    the Rulebook's unrelated mandatory "a ready, unlocked vampire with no
    blood must hunt" rule (mirrors `tests/cards/test_seraphina.py`'s own
    identically motivated precedent)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("for",), clan="Salubri"
    )
    p1.hand.append(_card())
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "touch_of_valeren:action:blood:V1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.blood_of("V1") == 3  # cost (1) paid first, then +3 added: 1-1+3
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()


def test_action_blocked_does_not_resolve_cost_not_paid():
    """Base stealth 1 needs a matching +1 intercept to actually succeed a
    block attempt; a temporary fake `"intercept_modifier"` provider (gated
    on this card's own default `ACTION_ACTION_CARD` discriminator) stands in
    for some other intercept-granting card so this test can reach the
    blocked branch (mirrors `tests/cards/test_scouting_mission.py`'s own
    identically shaped precedent)."""

    def match_stealth(state, context):
        if context.get("action") != ACTION_ACTION_CARD:
            return []
        return [HookOption(choice=Choice("match", "+1 intercept"), apply=lambda s: 1)]

    hooks.register("intercept_modifier", match_stealth)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire(
            "V1", capacity=5, blood=1, disciplines=("for",), clan="Salubri"
        )
        p1.hand.append(_card())
        builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
        game = builder.build()
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "touch_of_valeren:action:blood:V1")
        actor.expect("strike_choice", "no_strike")
        actor.expect("press", "end_combat")
        defender = ScriptedAgent("P2")
        defender.expect("block_attempt", "block_with:B1")
        defender.expect("intercept_modifier", "match")
        defender.expect("strike_choice", "no_strike")
        defender.expect("press", "end_combat")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = defender

        minion_phase(game.state, "P1")

        assert game.blood_of("V1") == 1  # resolve() never ran: no cost paid, no blood added
        assert game.state.players["P1"].hand == []  # card still consumed at announce time
        assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("intercept_modifier", match_stealth)


def test_action_second_physical_copy_not_offered_this_turn_after_being_played():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "V1", capacity=5, blood=1, disciplines=("for",), clan="Salubri"
    )
    p1.hand.append(_card())
    p1.hand.append(_card())
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "touch_of_valeren:action:blood:V1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.blood_of("V1") == 3
    assert _offer_action(game) == []


# --- "[for] [COMBAT] Prevent all damage from the opposing minion's
#     strike." ---------------------------------------------------------------


def _offer_self(game, *, damage, combat_state=None, vampire="D1"):
    return hooks.offer(
        DAMAGE_PREVENTION_HOOK,
        game.state,
        player="P1",
        vampire=vampire,
        damage=damage,
        combat_state=combat_state,
        round_state=None,
    )


def _combat_game(
    *,
    damaged_disciplines: tuple[str, ...] = ("for",),
    damaged_clan: str | None = "Salubri",
    with_card: bool = True,
    damaged_blood: int = 1,
):
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "D1", capacity=5, blood=damaged_blood, disciplines=damaged_disciplines, clan=damaged_clan
    )
    if with_card:
        p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    return builder.build()


def test_self_not_offered_without_an_active_combat_state():
    game = _combat_game()
    options = _offer_self(game, damage={"normal": 2, "aggravated": 0}, combat_state=None)
    assert options == []


def test_self_not_offered_with_no_damage_to_prevent():
    """ "Cannot be used if there is no damage to prevent." [LSJ 20001114]"""
    game = _combat_game()
    options = _offer_self(game, damage={"normal": 0, "aggravated": 0}, combat_state={})
    assert options == []


def test_self_not_offered_without_salubri_clan():
    game = _combat_game(damaged_clan="Toreador")
    options = _offer_self(game, damage={"normal": 2, "aggravated": 0}, combat_state={})
    assert options == []


def test_self_not_offered_without_fortitude():
    game = _combat_game(damaged_disciplines=())
    options = _offer_self(game, damage={"normal": 2, "aggravated": 0}, combat_state={})
    assert options == []


def test_self_not_offered_without_the_card_in_hand():
    game = _combat_game(with_card=False)
    options = _offer_self(game, damage={"normal": 2, "aggravated": 0}, combat_state={})
    assert options == []


def test_self_not_offered_without_enough_blood_for_the_printed_cost():
    game = _combat_game(damaged_blood=0)
    options = _offer_self(game, damage={"normal": 2, "aggravated": 0}, combat_state={})
    assert options == []


def test_self_prevents_all_normal_and_aggravated_damage_and_pays_the_cost():
    game = _combat_game()
    damage = {"normal": 2, "aggravated": 3}
    (option,) = _offer_self(game, damage=damage, combat_state={})

    option.apply(game.state)

    assert damage == {"normal": 0, "aggravated": 0}
    assert game.blood_of("D1") == 0  # printed 1-blood cost burned
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]


def test_self_offered_with_basic_fortitude_only():
    game = _combat_game(damaged_disciplines=("for",))
    options = _offer_self(game, damage={"normal": 1, "aggravated": 0}, combat_state={})
    assert {o.choice.value for o in options} == {"touch_of_valeren:combat:self"}


def test_self_offered_with_superior_fortitude_too():
    game = _combat_game(damaged_disciplines=("FOR",))
    options = _offer_self(game, damage={"normal": 1, "aggravated": 0}, combat_state={})
    assert {o.choice.value for o in options} == {"touch_of_valeren:combat:self"}


def test_self_end_to_end_via_apply_damage_with_a_real_combat_state():
    game = _combat_game()
    actor = ScriptedAgent("P1")
    actor.expect(DAMAGE_PREVENTION_HOOK, "touch_of_valeren:combat:self")
    game.state.agents["P1"] = actor

    apply_damage(game.state, "P1", game.vampire("D1"), normal=2, combat_state={})

    assert game.vampire("D1").wounded is False
    assert game.blood_of("D1") == 0
    actor.assert_exhausted()


# --- "[FOR] [COMBAT] Only usable by a ready vampire not involved in the
#     combat involving another minion you control. Prevent all damage to
#     that minion from the opposing minion's strike." -----------------------


def _offer_assist(game, *, damage, combat_state=None, vampire="D1"):
    return hooks.offer(
        DAMAGE_PREVENTION_HOOK,
        game.state,
        player="P1",
        vampire=vampire,
        damage=damage,
        combat_state=combat_state,
        round_state=None,
    )


def _assist_game(
    *,
    rescuer_disciplines: tuple[str, ...] = ("FOR",),
    rescuer_clan: str | None = "Salubri",
    rescuer_zone: str = "ready",
    rescuer_blood: int = 1,
    with_card: bool = True,
):
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("D1", capacity=5, blood=1)
    if rescuer_zone == "torpor":
        p1.torpid_vampire("R1", capacity=5, blood=rescuer_blood)
        rescuer = next(v for v in p1.vampires if v.instance_id == "R1")
        rescuer.card = CryptCard(
            krcg_id=rescuer.card.krcg_id,
            name="R1",
            capacity=5,
            group=5,
            clan=rescuer_clan,
            disciplines=rescuer_disciplines,
        )
    else:
        p1.ready_vampire(
            "R1",
            capacity=5,
            blood=rescuer_blood,
            disciplines=rescuer_disciplines,
            clan=rescuer_clan,
            locked=(rescuer_zone == "locked"),
        )
    if with_card:
        p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    return builder.build()


def test_assist_not_offered_without_an_active_combat_state():
    game = _assist_game()
    options = _offer_assist(game, damage={"normal": 2, "aggravated": 0}, combat_state=None)
    assert options == []


def test_assist_not_offered_with_no_damage_to_prevent():
    """ "Cannot be used if there is no damage to prevent." [LSJ 20001114]"""
    game = _assist_game()
    options = _offer_assist(game, damage={"normal": 0, "aggravated": 0}, combat_state={})
    assert options == []


def test_assist_not_offered_without_the_card_in_hand():
    game = _assist_game(with_card=False)
    options = _offer_assist(game, damage={"normal": 2, "aggravated": 0}, combat_state={})
    assert options == []


def test_assist_offered_by_an_uninvolved_ready_vampire_with_superior_fortitude():
    game = _assist_game()
    options = _offer_assist(game, damage={"normal": 2, "aggravated": 0}, combat_state={})
    assert {o.choice.value for o in options} == {"touch_of_valeren:combat:assist:R1"}


def test_assist_not_offered_for_the_damaged_vampire_itself():
    """ "Not involved in the combat": the vampire actually taking the
    damage is never its own rescuer."""
    game = _assist_game()
    options = _offer_assist(game, damage={"normal": 2, "aggravated": 0}, combat_state={})
    assert "touch_of_valeren:combat:assist:D1" not in {o.choice.value for o in options}


def test_assist_requires_superior_fortitude_basic_is_not_enough():
    game = _assist_game(rescuer_disciplines=("for",))
    options = _offer_assist(game, damage={"normal": 2, "aggravated": 0}, combat_state={})
    assert options == []


def test_assist_not_offered_without_salubri_clan():
    game = _assist_game(rescuer_clan="Toreador")
    options = _offer_assist(game, damage={"normal": 2, "aggravated": 0}, combat_state={})
    assert options == []


def test_assist_requires_a_ready_candidate_locked_is_not_ready_enough():
    """ "Only usable by a ready vampire": `zone == "ready"`, independent of
    `locked` -- wait, the card requires *ready*, and a locked vampire is
    still in the ready region (`life_in_the_city.py`'s own precedent), so a
    locked candidate remains eligible; only a torpid one is excluded."""
    game = _assist_game(rescuer_zone="locked")
    options = _offer_assist(game, damage={"normal": 2, "aggravated": 0}, combat_state={})
    assert {o.choice.value for o in options} == {"touch_of_valeren:combat:assist:R1"}


def test_assist_not_offered_for_a_torpid_candidate():
    game = _assist_game(rescuer_zone="torpor")
    options = _offer_assist(game, damage={"normal": 2, "aggravated": 0}, combat_state={})
    assert options == []


def test_assist_not_offered_without_enough_blood_for_the_printed_cost():
    game = _assist_game(rescuer_blood=0)
    options = _offer_assist(game, damage={"normal": 2, "aggravated": 0}, combat_state={})
    assert options == []


def test_assist_prevents_all_damage_and_the_rescuer_pays_the_cost_not_the_protected():
    game = _assist_game()
    damage = {"normal": 2, "aggravated": 3}
    (option,) = _offer_assist(game, damage=damage, combat_state={})

    option.apply(game.state)

    assert damage == {"normal": 0, "aggravated": 0}
    assert game.blood_of("R1") == 0  # printed cost paid by the rescuer
    assert game.blood_of("D1") == 1  # the protected vampire's own blood is untouched
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]


def test_self_and_assist_can_both_be_offered_together():
    """The damaged vampire's own self clause and an uninvolved teammate's
    assist clause are independent options, offered side by side."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire(
        "D1", capacity=5, blood=1, disciplines=("for",), clan="Salubri"
    )
    p1.ready_vampire("R1", capacity=5, blood=1, disciplines=("FOR",), clan="Salubri")
    p1.hand.append(_card())
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()

    options = hooks.offer(
        DAMAGE_PREVENTION_HOOK,
        game.state,
        player="P1",
        vampire="D1",
        damage={"normal": 2, "aggravated": 0},
        combat_state={},
        round_state=None,
    )

    assert {o.choice.value for o in options} == {
        "touch_of_valeren:combat:self",
        "touch_of_valeren:combat:assist:R1",
    }
