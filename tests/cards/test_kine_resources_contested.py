"""Kine Resources Contested (krcg id 101056,
`src/vtesbot/cards/kine_resources_contested.py`).

Card text: "Allocate 4 points among two or more Methuselahs. Successful
referendum means each Methuselah burns 1 pool for each point allocated."
Rulings: "Cannot allocate 4 points to a single Methuselah, but you can
allocate points to yourself." [LSJ 20000622]; "If multiple ousts happen,
players whose prey gets ousted get a victory point, even if they are being
ousted themselves. Only the surviving ones get 6 pool from the oust of
their prey (not of their grand-prey)." [LSJ 20000309]; "Can allocate more
points than a Methuselah has pool." [LSJ 20020819].

One assertion per clause/ruling: card-in-hand gating (not offered without
it), the `"action_card_play"` hook wiring through the real `minion_phase`
(happy path: referendum passes, allocation decision, pool burned on both
sides), the referendum failing (no effect at all -- "the referendum fails
and has no effect"), a blocked action (never calls a referendum, card is
still burned either way), the legal-split enumeration derived from "among
two or more Methuselahs" (never 4/0 or 0/4), and "can allocate more points
than a Methuselah has pool" together with the resulting oust (2P's own
"[m]ultiple ousts" ruling is inapplicable here -- there is structurally
only ever one oust event in a duel, per `engine/ousting.py`).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards.kine_resources_contested import KRCG_ID
from vtesbot.cards.registry import Status, get
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import ACTION_POLITICAL
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import minion_phase

NAME = "Kine Resources Contested"


def _kine_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type="Political Action")


def test_registered_as_implemented_against_the_action_card_play_hook():
    reg = get(KRCG_ID)
    assert reg is not None
    assert reg.status is Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.blocked_reason is None


def test_is_on_the_active_2p_allowed_list():
    import json
    from pathlib import Path

    data_path = Path(__file__).resolve().parents[2] / "data" / "formats" / "2p" / "2026-10-03.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    ids = {card.get("krcg_id") for card in data["cards"]}
    assert KRCG_ID in ids


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=30)
    game = builder.build()
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "action_choice":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen == [["bleed", "hunt"]]
    actor.assert_exhausted()


def test_offered_and_a_passing_referendum_burns_the_chosen_split():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_kine_card())
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "kine_resources_contested:play")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("kine_resources_contested_allocation", "allocate:2")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P1") == 28  # 30 - 2
    assert game.pool_of("P2") == 28  # 30 - 2
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()


def test_a_referendum_that_fails_has_no_effect():
    """Rulebook SS4 "Resolve the Referendum": "Otherwise, the referendum
    fails and has no effect." An opposing ready Prince's 2 votes outvote the
    caller's lone 1-vote political-action-card source."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_kine_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Prince")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "kine_resources_contested:play")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("polling_step_cast", "against:title:B1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P1") == 30
    assert game.pool_of("P2") == 30
    assert game.state.players["P1"].hand == []  # the card is still consumed either way
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_a_blocked_action_never_calls_a_referendum_and_the_card_is_still_burned():
    """Rulebook SS4 "Resolve the Action": a blocked action never reaches the
    referendum at all (OQ-5's verbatim quote, `engine/politics.py`'s own
    module docstring) -- the card is still burned, same destination as an
    unblocked play either way. A temporary fake `"intercept_modifier"`
    provider stands in for some other intercept-granting card so a
    base-stealth-1 action (`POLITICAL_ACTION_STEALTH`) can actually be
    blocked in this test, mirroring `test_enchant_kindred.py`'s own pattern
    for its stealth-1 superior clause."""

    def match_political_stealth(state, context):
        if context.get("action") != ACTION_POLITICAL:
            return []
        return [HookOption(choice=Choice("match", "+1 intercept"), apply=lambda s: 1)]

    hooks.register("intercept_modifier", match_political_stealth)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
        p1.hand.append(_kine_card())
        builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
        game = builder.build()
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "kine_resources_contested:play")
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

        assert game.pool_of("P1") == 30
        assert game.pool_of("P2") == 30
        assert game.state.players["P1"].hand == []
        assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("intercept_modifier", match_political_stealth)


def test_allocation_choices_never_let_a_single_methuselah_get_all_four_or_zero():
    """ "Allocate 4 points **among two or more Methuselahs**" requires both
    of the two Methuselahs to receive a nonzero share in a duel (module
    docstring); this directly subsumes the printed ruling "[c]annot allocate
    4 points to a single Methuselah" -- the legal split set offered is
    exactly {1/3, 2/2, 3/1}, never 4/0 or 0/4."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_kine_card())
    builder.player("P2", pool=30)
    game = builder.build()
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "kine_resources_contested_allocation":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "kine_resources_contested:play")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("kine_resources_contested_allocation", "allocate:1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen == [["allocate:1", "allocate:2", "allocate:3"]]
    assert game.pool_of("P1") == 29  # self got 1 point allocated (burns 1 pool)
    assert game.pool_of("P2") == 27  # other got 3 points allocated (burns 3 pool)
    actor.assert_exhausted()


def test_can_allocate_more_points_than_a_methuselah_has_pool_and_it_ousts_them():
    """Ruling: "Can allocate more points than a Methuselah has pool."
    `lose_pool` floors at the player's current pool and still checks
    ousting (`engine/pool.py`) -- driving the opponent's pool to exactly 0
    triggers the ordinary 2P oust path (`engine/ousting.py`, reproducing
    `tests/rules/test_ousting.py::test_pool_at_zero_ousts_and_ends_the_game`'s
    own worked numbers), not a new mechanism this card needs to build."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_kine_card())
    builder.player("P2", pool=2)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "kine_resources_contested:play")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("kine_resources_contested_allocation", "allocate:1")  # other gets 3, only has 2
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 0  # floored at 0, not negative
    assert "P2" in game.state.eliminated
    assert game.state.game_over is True
    assert game.state.winner == "P1"
    assert game.state.victory_points["P1"] == 2  # 1 (ousted prey) + 1 (last Methuselah)
    assert game.pool_of("P1") == 35  # 30 - 1 (self-allocated) + 6 (oust bonus)
    actor.assert_exhausted()
