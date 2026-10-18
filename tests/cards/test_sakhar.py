"""Sakhar (krcg id 201685, `src/vtesbot/cards/sakhar.py`).

Card text: "Independent: Sakhar can search your library for an equipment
card, reveal it and move it to your hand as a +1 stealth action." No
rulings on file.

One assertion per clause/qualifier: not offered without an eligible
Equipment-typed library card, not offered for a different acting vampire,
one option per eligible card (named individually), the unblocked resolve
moves the exact named card from library to hand, the "+1 stealth action"
baseline (defender's default 0 intercept cannot block it), the blocked
branch never touches the library, and the OQ-21 "bound at apply(), fizzles
if gone by resolve()" convention.
"""

import json
from pathlib import Path

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards.registry import Status, get
from vtesbot.cards.sakhar import KRCG_ID
from vtesbot.engine import CryptCard, hooks
from vtesbot.engine.action import ACTION_ACTION_CARD
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, minion_phase

NAME = "Sakhar"


def _make_sakhar(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Sakhar's real printed
    identity (`CryptCard` is frozen)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name=NAME,
        capacity=6,
        group=7,
        clan="Salubri",
        disciplines=("dom", "AUS", "FOR"),
    )


def test_registered_as_implemented_against_the_action_card_play_hook():
    reg = get(KRCG_ID)
    assert reg is not None
    assert reg.status is Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


def test_is_on_the_active_2p_allowed_list():
    data_path = Path(__file__).resolve().parents[2] / "data" / "formats" / "2p" / "2026-10-03.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    ids = {card.get("krcg_id") for card in data["cards"]}
    assert KRCG_ID in ids


def test_not_offered_without_an_equipment_card_in_library():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
    _make_sakhar(p1, "V1")
    p1.library_cards(["Some Master"], card_type="Master")
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    actor.assert_exhausted()


def test_not_offered_for_a_different_vampire():
    """A plain, non-Sakhar vampire gets no option even with an eligible
    Equipment card sitting in the library."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1).library_cards(
        ["Weighted Walking Stick"], card_type="Equipment"
    )
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")

    assert options == []


def test_single_equipment_card_is_found_and_moved_to_hand_unblocked():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
    _make_sakhar(p1, "V1")
    p1.library_cards(["Weighted Walking Stick"], card_type="Equipment")
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with.
    game = builder.build()

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", option.choice.value)
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.state.players["P1"].library == []
    assert [c.name for c in game.state.players["P1"].hand] == ["Weighted Walking Stick"]
    actor.assert_exhausted()


def test_multiple_equipment_cards_offer_one_option_each():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
    _make_sakhar(p1, "V1")
    p1.library_cards(["Weighted Walking Stick", "Aaron's Feeding Razor"], card_type="Equipment")
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")

    assert len(options) == 2
    labels = sorted(o.choice.label for o in options)
    assert any("Weighted Walking Stick" in label for label in labels)
    assert any("Aaron's Feeding Razor" in label for label in labels)


def test_chosen_equipment_card_is_the_one_moved_not_the_other():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
    _make_sakhar(p1, "V1")
    p1.library_cards(["Weighted Walking Stick", "Aaron's Feeding Razor"], card_type="Equipment")
    builder.player("P2", pool=30)
    game = builder.build()

    options = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    (razor_option,) = [o for o in options if "Razor" in o.choice.label]

    spec = razor_option.apply(game.state)
    spec.resolve({})

    hand_names = [c.name for c in game.state.players["P1"].hand]
    library_names = [c.name for c in game.state.players["P1"].library]
    assert hand_names == ["Aaron's Feeding Razor"]
    assert library_names == ["Weighted Walking Stick"]


def test_base_stealth_is_one_and_directed_is_false():
    """ "+1 stealth action" (bare, undirected) -- mirrors `RECRUIT_ALLY_
    STEALTH`'s own baseline-1 reading."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
    _make_sakhar(p1, "V1")
    p1.library_cards(["Weighted Walking Stick"], card_type="Equipment")
    builder.player("P2", pool=30)
    game = builder.build()

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    spec = option.apply(game.state)

    assert spec.base_stealth == 1
    assert spec.directed is False


def test_uses_plus_one_stealth_baseline_to_beat_a_defenders_default_intercept():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
    _make_sakhar(p1, "V1")
    p1.library_cards(["Weighted Walking Stick"], card_type="Equipment")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", option.choice.value)
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")  # stealth(1) > intercept(0): attempt failed
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert [c.name for c in game.state.players["P1"].hand] == ["Weighted Walking Stick"]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_blocked_does_not_resolve_the_library_stays_untouched():
    """Base stealth 1 needs a matching +1 intercept to actually succeed a
    block attempt; a temporary fake `"intercept_modifier"` provider (gated
    on this card's own default `ACTION_ACTION_CARD` discriminator) stands in
    for some other intercept-granting card so this test can reach the
    blocked branch (mirrors `tests/cards/test_scouting_mission.py`'s own
    identically-shaped precedent)."""

    def match_stealth(state, context):
        if context.get("action") != ACTION_ACTION_CARD:
            return []
        return [HookOption(choice=Choice("match", "+1 intercept"), apply=lambda s: 1)]

    hooks.register("intercept_modifier", match_stealth)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
        _make_sakhar(p1, "V1")
        p1.library_cards(["Weighted Walking Stick"], card_type="Equipment")
        builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=1)
        game = builder.build()

        (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", option.choice.value)
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

        assert [c.name for c in game.state.players["P1"].library] == ["Weighted Walking Stick"]
        assert game.state.players["P1"].hand == []
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("intercept_modifier", match_stealth)


def test_resolve_fizzles_if_the_named_card_left_the_library_by_resolve_time():
    """OQ-21 convention -- not reachable through ordinary play today (nothing
    else in this engine touches another player's own library mid-action),
    exercised directly against the hook machinery."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=6, blood=1)
    _make_sakhar(p1, "V1")
    p1.library_cards(["Weighted Walking Stick"], card_type="Equipment")
    builder.player("P2", pool=30)
    game = builder.build()

    (option,) = hooks.offer(ACTION_CARD_PLAY_HOOK, game.state, player="P1", vampire="V1")
    spec = option.apply(game.state)

    game.state.players["P1"].library.clear()  # simulate the card leaving the library.

    spec.resolve({})

    assert game.state.players["P1"].hand == []
