"""Parity Shift (krcg id 101353, `src/vtesbot/cards/parity_shift.py`).

Card text: "Requires a prince or justicar.\nChoose a Methuselah who has
more pool than you do and allocate 3 of their pool among 1 or more other
Methuselahs (including you). Successful referendum means the pool is
distributed as you chose." Rulings: "The pool awarded can be used to play
{Life Boon} to save the target from an oust." [LSJ 20100527]; "If the
target has less than 3 pool when referendum passes, the Methuselah calling
the referendum chooses how to distribute within the bounds of the terms."
[LSJ 20010606]; "Changes in pool during the referendum (after terms are
chosen) do not affect the outcome." [LSJ 20041004]; "Cannot be used or
played if the conditions for the terms of the referendum cannot be met
(...)." [LSJ 20100129] [ANK 20191228].

One assertion per clause/ruling: the "Requires a prince or justicar" title
gate (both titles independently, and its absence), card-in-hand gating, the
"choose a Methuselah who has more pool than you do" target gate (no legal
target when the opponent's pool does not exceed the caller's -- the
"cannot be used or played if the conditions ... cannot be met" ruling),
the happy path (referendum passes, the full 3 pool transferred from the
target to the caller -- the only possible "other Methuselah" recipient in a
duel, module docstring), the referendum failing (no effect at all), a
blocked action (never calls a referendum, card still burned), the
"[i]f the target has less than 3 pool" clamp (and the resulting oust), and
that no allocation `Decision` is ever raised (2P collapses the "among 1 or
more other Methuselahs" choice to a single forced recipient) -- proven
implicitly throughout by `ScriptedAgent`'s own "fails loudly on any
unscripted decision" contract.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards.parity_shift import KRCG_ID
from vtesbot.cards.registry import Status, get
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import ACTION_POLITICAL
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import minion_phase

NAME = "Parity Shift"


def _parity_shift_card() -> LibraryCard:
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


def test_not_offered_without_a_qualifying_title():
    """ "Requires a prince or justicar": an untitled vampire never sees the
    option, even with the card in hand and an eligible (higher-pool)
    opponent."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=10).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_parity_shift_card())
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


def test_not_offered_without_the_card_in_hand():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10).ready_vampire("V1", capacity=3, blood=1, title="Prince")
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


def test_not_offered_when_the_opponent_does_not_have_more_pool():
    """ "Choose a Methuselah who has more pool than you do" + ruling: "[c]annot
    be used or played if the conditions for the terms of the referendum
    cannot be met" -- equal pool is not "more"."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, title="Prince")
    p1.hand.append(_parity_shift_card())
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


def test_prince_title_qualifies_and_a_passing_referendum_transfers_the_full_three():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=10).ready_vampire("V1", capacity=3, blood=1, title="Prince")
    p1.hand.append(_parity_shift_card())
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "parity_shift:play")
    # Two own sources this time: the calling card's own vote, plus V1's own
    # "Prince" title vote (`engine/politics.py::TITLE_VOTES`) -- the single
    # cast "for" already outvotes P2's empty tally, so the title vote is
    # left unused (declined, "no obligation to cast").
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "pass")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P1") == 13  # 10 + 3
    assert game.pool_of("P2") == 27  # 30 - 3
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()


def test_justicar_title_also_qualifies():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=10).ready_vampire("V1", capacity=3, blood=1, title="Justicar")
    p1.hand.append(_parity_shift_card())
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "parity_shift:play")
    # Two own sources: the calling card's own vote, plus V1's own
    # "Justicar" title vote -- left unused, see the Prince test above.
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "pass")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P1") == 13
    assert game.pool_of("P2") == 27
    actor.assert_exhausted()


def test_a_referendum_that_fails_has_no_effect():
    """Rulebook SS4 "Resolve the Referendum": no effect at all. The caller
    declines both of their own sources ("no obligation to cast"); the
    opposing ready Prince's 2 votes "against" then stand alone, 0 to 2."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=10).ready_vampire("V1", capacity=3, blood=1, title="Justicar")
    p1.hand.append(_parity_shift_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Prince")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "parity_shift:play")
    actor.expect("polling_step_cast", "pass")
    actor.expect("polling_step_cast", "pass")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("polling_step_cast", "against:title:B1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P1") == 10
    assert game.pool_of("P2") == 30
    assert game.state.players["P1"].hand == []  # the card is still consumed either way
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_a_blocked_action_never_calls_a_referendum_and_the_card_is_still_burned():
    """Mirrors `test_kine_resources_contested.py`'s own analogous test: a
    temporary fake `"intercept_modifier"` provider stands in for some other
    intercept-granting card so a base-stealth-1 action
    (`POLITICAL_ACTION_STEALTH`) can actually be blocked here."""

    def match_political_stealth(state, context):
        if context.get("action") != ACTION_POLITICAL:
            return []
        return [HookOption(choice=Choice("match", "+1 intercept"), apply=lambda s: 1)]

    hooks.register("intercept_modifier", match_political_stealth)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=10).ready_vampire("V1", capacity=3, blood=1, title="Prince")
        p1.hand.append(_parity_shift_card())
        builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
        game = builder.build()
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "parity_shift:play")
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

        assert game.pool_of("P1") == 10
        assert game.pool_of("P2") == 30
        assert game.state.players["P1"].hand == []
        assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("intercept_modifier", match_political_stealth)


def test_amount_is_clamped_to_the_targets_actual_pool_and_it_ousts_them():
    """Ruling: "If the target has less than 3 pool when referendum passes,
    the Methuselah calling the referendum chooses how to distribute within
    the bounds of the terms" -- in 2P there is nothing left to choose (the
    sole recipient is the caller), so the full (lesser) amount simply
    transfers, driving the target to exactly 0 pool and triggering the
    ordinary 2P oust path (`engine/ousting.py`)."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=1).ready_vampire("V1", capacity=3, blood=1, title="Prince")
    p1.hand.append(_parity_shift_card())
    builder.player("P2", pool=2)  # more than P1's 1 pool, but less than the printed 3
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "parity_shift:play")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "pass")  # V1's own "Prince" title vote, left unused
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 0  # clamped to what they actually had (2), not 3
    assert "P2" in game.state.eliminated
    assert game.state.game_over is True
    assert game.state.winner == "P1"
    assert game.state.victory_points["P1"] == 2  # 1 (ousted prey) + 1 (last Methuselah)
    assert game.pool_of("P1") == 9  # 1 + 2 (awarded) + 6 (oust bonus)
    actor.assert_exhausted()


def test_oust_at_tally_stops_before_the_pool_transfer():
    from vtesbot.engine.pool import lose_pool

    def oust_caller(state, context):
        lose_pool(state, "P1", 10)

    hooks.register("referendum_tallied", oust_caller)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=10).ready_vampire("V1", capacity=3, blood=1, title="Prince")
        p1.hand.append(_parity_shift_card())
        builder.player("P2", pool=30)
        game = builder.build()
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "parity_shift:play")
        actor.expect("polling_step_cast", "for:political_action_card:P1")
        actor.expect("polling_step_cast", "pass")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = ScriptedAgent("P2")

        minion_phase(game.state, "P1")

        assert game.state.game_over is True
        assert game.pool_of("P2") == 36  # 30 + 6 oust bonus, no 3-pool transfer
    finally:
        hooks.unregister("referendum_tallied", oust_caller)
