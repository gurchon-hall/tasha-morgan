"""Pulled Fangs (krcg id 101515, `src/vtesbot/cards/pulled_fangs.py`).

Card text: "Only usable at close range at the end of a round during which
this minion successfully inflicted more damage than the opposing vampire.
Not usable by a minion being burned or going to torpor.\nPut this card on
the opposing vampire; this minion inflicts 1 damage on them. The attached
vampire cannot hunt; if they must hunt, they go to torpor instead. Any
vampire(s) can burn this card with two +1 stealth actions. A vampire can
have only one Pulled Fangs." Ruling: "A total of two actions must be
performed (by whomever) to remove it. Vampires A and B can both take the
action, then it is removed." [ANK 20170202-2].

One assertion per clause/qualifier/ruling: the playability window (close
range, strictly more damage inflicted than the opponent this round, card
in hand, playing vampire's own burned/torpor exclusion, the "only one
Pulled Fangs" host cap); correct acting/blocking side resolution; the
attach-and-damage effect (controller is the *playing* Methuselah, not the
host's own); the "cannot hunt" clause wired to `CANNOT_HUNT_HOOK`; the
"burn this card with two +1 stealth actions" clause wired to
`ATTACHMENT_REMOVAL_ACTION_HOOK` with `contributions_required=2`, by
either side; and one full `run_combat` integration proving the whole
window end to end.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.pulled_fangs import KRCG_ID, NAME
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.attachments import attach_card
from vtesbot.engine.combat import (
    CLOSE_RANGE,
    END_OF_ROUND_HOOK,
    LONG_RANGE,
    ROUND_STATE_CONTEXT_KEY,
    run_combat,
)
from vtesbot.engine.damage import record_damage_successfully_inflicted
from vtesbot.engine.phases.minion import (
    ATTACHMENT_REMOVAL_ACTION_HOOK,
    CANNOT_HUNT_HOOK,
    minion_phase,
)


def _card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="combat")


def _offer(game, *, player: str, round_state: dict | None = None, combat_range: str = CLOSE_RANGE):
    game.state.combat_range = combat_range
    return hooks.offer(
        END_OF_ROUND_HOOK,
        game.state,
        player=player,
        acting_player="P1",
        acting_vampire="V1",
        blocking_player="P2",
        blocking_vampire="B1",
        **({ROUND_STATE_CONTEXT_KEY: round_state} if round_state is not None else {}),
    )


def test_registered_as_implemented():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None
    assert registry.Hook.END_OF_ROUND in reg.hooks
    assert registry.Hook.CANNOT_HUNT in reg.hooks
    assert registry.Hook.ATTACHMENT_REMOVAL_ACTION_PLAY in reg.hooks


def test_is_on_the_active_2p_allowed_list():
    import json
    from pathlib import Path

    data_path = Path(__file__).resolve().parents[2] / "data" / "formats" / "2p" / "2026-10-03.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    ids = {card.get("krcg_id") for card in data["cards"]}
    assert KRCG_ID in ids


# --- Playability window: "Only usable at close range at the end of a round
# during which this minion successfully inflicted more damage than the
# opposing vampire." -------------------------------------------------------


def _base_game(*, v1_blood: int = 2, b1_blood: int = 0):
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=v1_blood)
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=b1_blood)
    return builder.build()


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=0)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "V1", 1)

    assert _offer(game, player="P1", round_state=round_state) == []


def test_not_offered_at_long_range():
    """ "Only usable at close range ..." -- long range withholds the
    option even though the damage condition is otherwise satisfied."""
    game = _base_game()
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "V1", 1)

    assert _offer(game, player="P1", round_state=round_state, combat_range=LONG_RANGE) == []


def test_not_offered_when_inflicted_damage_is_tied():
    game = _base_game()
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "V1", 1)
    record_damage_successfully_inflicted(round_state, "B1", 1)

    assert _offer(game, player="P1", round_state=round_state) == []


def test_not_offered_when_this_minion_inflicted_less_damage():
    game = _base_game()
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "V1", 1)
    record_damage_successfully_inflicted(round_state, "B1", 2)

    assert _offer(game, player="P1", round_state=round_state) == []


def test_offered_when_this_minion_inflicted_strictly_more_damage():
    game = _base_game()
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "V1", 2)
    record_damage_successfully_inflicted(round_state, "B1", 1)

    values = {o.choice.value for o in _offer(game, player="P1", round_state=round_state)}
    assert values == {"pulled_fangs"}


def test_not_offered_to_a_vampire_being_burned():
    """ "Not usable by a minion being burned or going to torpor" -- the
    *playing* vampire's own zone, not the opponent's."""
    game = _base_game()
    game.vampire("V1").zone = "burned"
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "V1", 2)

    assert _offer(game, player="P1", round_state=round_state) == []


def test_not_offered_to_a_vampire_going_to_torpor():
    game = _base_game()
    game.vampire("V1").zone = "torpor"
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "V1", 2)

    assert _offer(game, player="P1", round_state=round_state) == []


def test_offer_is_unaffected_by_the_opponents_own_zone():
    game = _base_game()
    game.vampire("B1").zone = "burned"
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "V1", 2)

    values = {o.choice.value for o in _offer(game, player="P1", round_state=round_state)}
    assert values == {"pulled_fangs"}


def test_not_offered_if_the_opponent_already_carries_one():
    """ "A vampire can have only one Pulled Fangs." """
    game = _base_game()
    attach_card(game.state, game.vampire("B1"), controller="P1", krcg_id=KRCG_ID, name=NAME)
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "V1", 2)

    assert _offer(game, player="P1", round_state=round_state) == []


def test_blocking_side_can_also_play_it_against_the_acting_vampire():
    """Correct acting/blocking side resolution: offered to P2 (controlling
    B1) when B1, not V1, inflicted more damage this round."""
    game = _base_game()
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "B1", 2)
    record_damage_successfully_inflicted(round_state, "V1", 1)
    game.state.players["P2"].hand.append(_card())

    values = {o.choice.value for o in _offer(game, player="P2", round_state=round_state)}
    assert values == {"pulled_fangs"}


# --- "Put this card on the opposing vampire; this minion inflicts 1 damage
# on them." ------------------------------------------------------------------


def test_apply_attaches_to_the_opponent_controlled_by_the_playing_methuselah_and_damages_them():
    game = _base_game(b1_blood=0)
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "V1", 2)

    options = _offer(game, player="P1", round_state=round_state)
    game.state.agents["P2"] = ScriptedAgent("P2")  # blood=0: no mend decision
    options[0].apply(game.state)

    b1 = game.vampire("B1")
    assert len(b1.attachments) == 1
    attachment = b1.attachments[0]
    assert attachment.krcg_id == KRCG_ID
    assert attachment.name == NAME
    assert attachment.controller == "P1"  # the playing Methuselah, not B1's own ("P2")
    assert b1.wounded is True  # 1 normal damage, unmended (no blood)


def test_apply_fizzles_if_the_opponent_left_play_since_offer():
    """OQ-21 convention: the opponent is re-validated, not re-chosen, at
    apply time."""
    game = _base_game()
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "V1", 2)

    options = _offer(game, player="P1", round_state=round_state)
    game.state.players["P2"].vampires.pop("B1")

    options[0].apply(game.state)  # must not raise

    assert game.state.players["P1"].hand == []  # the card is still consumed


# --- "The attached vampire cannot hunt; if they must hunt, they go to
# torpor instead." -----------------------------------------------------------


def test_cannot_hunt_hook_true_only_while_attached():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()

    assert hooks.any_true(CANNOT_HUNT_HOOK, game.state, player="P1", vampire="V1") is False

    attach_card(game.state, game.vampire("V1"), controller="P2", krcg_id=KRCG_ID, name=NAME)

    assert hooks.any_true(CANNOT_HUNT_HOOK, game.state, player="P1", vampire="V1") is True


def test_attached_vampire_with_no_blood_goes_to_torpor_instead_of_hunting():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=0)
    builder.player("P2", pool=30)
    game = builder.build()
    attach_card(game.state, game.vampire("V1"), controller="P2", krcg_id=KRCG_ID, name=NAME)
    game.state.agents["P1"] = ScriptedAgent("P1")  # no hunt/block decision: forced to torpor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.zone_of("V1") == "torpor"
    assert game.blood_of("V1") == 0  # never actually hunted


# --- "Any vampire(s) can burn this card with two +1 stealth actions." ------


def test_attachment_removal_not_offered_with_no_live_attachment_in_play():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ATTACHMENT_REMOVAL_ACTION_HOOK, game.state, player="P1", vampire="V1")
    assert options == []


def test_attachment_removal_offered_naming_the_host():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1)
    game = builder.build()
    attachment = attach_card(
        game.state, game.vampire("B1"), controller="P1", krcg_id=KRCG_ID, name=NAME
    )

    options = hooks.offer(ATTACHMENT_REMOVAL_ACTION_HOOK, game.state, player="P1", vampire="V1")
    (option,) = options
    assert option.choice.value == f"pulled_fangs:remove:{attachment.instance_id}"
    spec = option.apply(game.state)
    assert spec.action == "attachment_removal_action"


def test_two_contributions_by_either_side_burn_the_attachment():
    """[ANK 20170202-2]: "Vampires A and B can both take the action, then
    it is removed." -- both contributing vampires are P1's own here
    (krcg's "any vampire(s)" is not restricted to the host's controller
    or the host itself); P2 has no ready vampire, so unblockable, mirroring
    the mechanism-level `tests/rules/test_attachment_removal_action.py`
    scenario this reuses."""
    builder = ScenarioBuilder(seed=1)
    (
        builder.player("P1", pool=30)
        .ready_vampire("V1", capacity=3, blood=1)
        .ready_vampire("V2", capacity=3, blood=1)
    )
    builder.player("P2", pool=30)  # no ready vampire: unblockable
    game = builder.build()
    attachment = attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=KRCG_ID, name=NAME
    )
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", f"pulled_fangs:remove:{attachment.instance_id}")
    actor.expect("minion_phase_choice", "act_with:V2")
    actor.expect("action_choice", f"pulled_fangs:remove:{attachment.instance_id}")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert attachment.zone == "burned"
    assert attachment.counters == 2
    actor.assert_exhausted()


# --- Full `run_combat` integration ------------------------------------------


def test_full_round_hand_strike_then_pulled_fangs_end_to_end():
    """V1 lands a plain hand strike on B1 (B1 has 0 blood, no mend); V1
    then plays Pulled Fangs at the end-of-round window (close range by
    default), attaching to B1 and inflicting 1 more damage -- enough to
    send the already-wounded B1 to torpor."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=2)
    p1.hand.append(_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    actor.expect("end_of_round", "pulled_fangs")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.vampire("B1").wounded is True
    assert game.vampire("B1").zone == "torpor"  # 2nd normal damage point: wounded -> torpor
    assert len(game.vampire("B1").attachments) == 1
    assert game.vampire("B1").attachments[0].krcg_id == KRCG_ID
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()
