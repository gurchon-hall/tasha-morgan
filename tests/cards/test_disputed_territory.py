"""Disputed Territory (krcg id 100557, `src/vtesbot/cards/
disputed_territory.py`).

Card text: "Choose a location and a Methuselah. Successful referendum means
the chosen Methuselah takes control of the chosen location." Rulings:
"Requirements do not apply when taking control of a card already in play."
[TOM 19960226-1]; "If used to steal an equipment representing a location,
it can be placed on any minion controlled by the new controller."
[RTR 19960112]; "If used to 'change' the control of a location or
equipment representing a location to the same Methuselah, the location
cannot be moved to another minion controlled by the same Methuselah."
[LSJ 19971002]; "Changing the controller of a location has no other
effect, unless specified by card text. Exception: ..." [RTR 19980623];
"Cannot be used or played if the conditions for the terms of the
referendum cannot be met (...)." [LSJ 20100129] [ANK 20191228].

The [RTR 19960112]/[LSJ 19971002] re-host clauses are scoped to an
"equipment representing a location" (`CardAttachment`) -- no such card is
on the active 2P list (module docstring), so they are exercised instead at
the engine level by `tests/rules/test_location_control_transfer.py`
against `engine/attachments.py::transfer_attachment_control`, not here.

One assertion per remaining clause/ruling: card-in-hand gating, the "no
legal selection" gate (no location at all in play), the terms `Decision`
enumerating every in-play location times both Methuselahs as recipient, a
passing referendum transferring control (including stealing the opponent's
location, and "requirements do not apply" -- the new controller controls
no Brujah at all), a same-Methuselah "change" being a legal no-op,
"changing the controller ... has no other effect" (locked/zone untouched),
a failing referendum (no effect), and a blocked action (never calls a
referendum, card still burned).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards.disputed_territory import KRCG_ID, LOCATION_KRCG_IDS
from vtesbot.cards.registry import Status, get
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import ACTION_POLITICAL
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.master_cards import bring_master_card_into_play
from vtesbot.engine.phases.minion import minion_phase

NAME = "Disputed Territory"
# Chantry (krcg id 100329): a `LOCATION_KRCG_IDS` member with no card module
# of its own (unlike Oxford University, England), so bringing it into play
# raises no extra ability decision of its own for these tests to script.
LOCATION_KRCG_ID = 100329
LOCATION_NAME = "Chantry"


def test_the_chosen_stand_in_location_id_is_actually_a_known_location():
    assert LOCATION_KRCG_ID in LOCATION_KRCG_IDS


def test_location_krcg_ids_matches_a_fresh_krcg_sweep_of_the_active_2p_list():
    """`rules-auditor` finding: an earlier draft of `LOCATION_KRCG_IDS` held
    only 4 of the 14 standalone "Unique location." Master cards actually on
    the active 2P list. Re-runs the exact sweep live against the installed
    krcg package, so a future 2P-list update (or any other drift) fails
    this test instead of silently under-recognizing a legal target."""
    import json
    from pathlib import Path

    import krcg

    cards = krcg.load()
    data_path = Path(__file__).resolve().parents[2] / "data" / "formats" / "2p" / "2026-10-03.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    ids = {card.get("krcg_id") for card in data["cards"]}
    swept = {cid for cid in ids if (cards[cid].text or "").startswith("Unique location.")}

    assert swept == LOCATION_KRCG_IDS


def _disputed_territory_card() -> LibraryCard:
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
    bring_master_card_into_play(game.state, "P2", krcg_id=LOCATION_KRCG_ID, name=LOCATION_NAME)
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


def test_not_offered_without_any_location_in_play():
    """ "Cannot be used or played if ... no legal selection": with no
    `LOCATION_KRCG_IDS` card anywhere in play, the card is not offered at
    all, even with it in hand."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_disputed_territory_card())
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


def test_the_terms_decision_offers_every_in_play_location_times_both_recipients():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_disputed_territory_card())
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with
    game = builder.build()
    location = bring_master_card_into_play(
        game.state, "P2", krcg_id=LOCATION_KRCG_ID, name=LOCATION_NAME
    )
    seen: list[list[str]] = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == "disputed_territory_terms":
                seen.append(sorted(c.value for c in decision.choices))
            return super().decide(observation, decision)

    actor = RecordingAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "disputed_territory:play")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("disputed_territory_terms", f"transfer:{location.instance_id}:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert seen == [
        sorted(
            [
                f"transfer:{location.instance_id}:P1",
                f"transfer:{location.instance_id}:P2",
            ]
        )
    ]
    actor.assert_exhausted()


def test_a_passing_referendum_steals_the_opponents_location_with_no_requirement_check():
    """Happy path, stealing the opponent's location: P1 controls no Brujah
    at all (`V1` has no clan), demonstrating "[r]equirements do not apply
    when taking control of a card already in play" -- Oxford University,
    England's own Brujah requirement only gates *playing* it, never
    checked here."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_disputed_territory_card())
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with
    game = builder.build()
    location = bring_master_card_into_play(
        game.state, "P2", krcg_id=LOCATION_KRCG_ID, name=LOCATION_NAME
    )
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "disputed_territory:play")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("disputed_territory_terms", f"transfer:{location.instance_id}:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert location.controller == "P1"
    assert location.instance_id in game.state.players["P1"].master_cards
    assert location.instance_id not in game.state.players["P2"].master_cards
    assert game.state.players["P1"].hand == []
    assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
    actor.assert_exhausted()


def test_changing_to_the_same_methuselah_is_a_legal_no_op():
    """ "Choose a location and a Methuselah" names no restriction barring
    the current controller from being re-chosen; [LSJ 19971002]'s own
    restriction on this is scoped to the re-host-only attachment shape
    (module docstring), so re-affirming the current controller is simply a
    legal, effect-free choice here."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_disputed_territory_card())
    builder.player("P2", pool=30)
    game = builder.build()
    location = bring_master_card_into_play(
        game.state, "P1", krcg_id=LOCATION_KRCG_ID, name=LOCATION_NAME
    )
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "disputed_territory:play")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("disputed_territory_terms", f"transfer:{location.instance_id}:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert location.controller == "P1"
    assert location.instance_id in game.state.players["P1"].master_cards
    actor.assert_exhausted()


def test_changing_the_controller_has_no_other_effect():
    """ "Changing the controller of a location has no other effect, unless
    specified by card text": a locked location stays locked, and stays
    `zone == "in_play"`, once control changes."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_disputed_territory_card())
    builder.player("P2", pool=30)
    game = builder.build()
    location = bring_master_card_into_play(
        game.state, "P2", krcg_id=LOCATION_KRCG_ID, name=LOCATION_NAME
    )
    location.locked = True
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "disputed_territory:play")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("disputed_territory_terms", f"transfer:{location.instance_id}:P1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    assert location.controller == "P1"
    assert location.locked is True
    assert location.zone == "in_play"
    actor.assert_exhausted()


def test_a_referendum_that_fails_has_no_effect():
    """Rulebook SS4 "Resolve the Referendum": "Otherwise, the referendum
    fails and has no effect." An opposing ready Prince's 2 votes outvote
    the caller's lone 1-vote political-action-card source."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    p1.hand.append(_disputed_territory_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1, title="Prince")
    game = builder.build()
    location = bring_master_card_into_play(
        game.state, "P2", krcg_id=LOCATION_KRCG_ID, name=LOCATION_NAME
    )
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "disputed_territory:play")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    defender.expect("polling_step_cast", "against:title:B1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert location.controller == "P2"  # unchanged
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
        p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
        p1.hand.append(_disputed_territory_card())
        builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
        game = builder.build()
        location = bring_master_card_into_play(
            game.state, "P2", krcg_id=LOCATION_KRCG_ID, name=LOCATION_NAME
        )
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "disputed_territory:play")
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

        assert location.controller == "P2"  # unchanged: no referendum ever ran
        assert game.state.players["P1"].hand == []
        assert [c.name for c in game.state.players["P1"].ash_heap] == [NAME]
        actor.assert_exhausted()
        defender.assert_exhausted()
    finally:
        hooks.unregister("intercept_modifier", match_political_stealth)
