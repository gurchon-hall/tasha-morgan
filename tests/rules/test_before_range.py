"""Before Range (`engine/combat.py`, Rulebook SS4 Combat > Combat Sequence,
step 1, "Before Range: Play cards before range is chosen") -- resolves
`docs/OPEN_QUESTIONS.md` OQ-47 (Weighted Walking Stick, krcg id 102169).
No combat card registers against `BEFORE_RANGE_HOOK` yet (OQ-47's own card
module is `card-implementer`'s job once this capability exists) -- these are
scenario tests for the generic mechanism only, using fake providers to prove
the shape rather than any one card's wording.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.action import perform_minion_action
from vtesbot.engine.attachments import attach_card
from vtesbot.engine.combat import BEFORE_RANGE_HOOK, COMBAT_STRIKE_OPTION_HOOK, run_combat
from vtesbot.engine.decision import Choice

WWS_KRCG_ID = 102169


def _combat_game(*, acting_blood: int = 2, blocking_blood: int = 0):
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=acting_blood)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=blocking_blood)
    return builder.build()


def _register_logging_provider(calls: list[str]) -> None:
    """A fake `BEFORE_RANGE_HOOK` provider that never actually offers a real
    option (so no `Decision` is ever raised, CLAUDE.md "only when needed")
    but records every `context["player"]` it is queried for -- mirrors
    `tests/rules/test_end_of_round.py`'s own `_register_logging_provider`."""

    def provider(state, context):
        calls.append(context["player"])
        return []

    hooks.register(BEFORE_RANGE_HOOK, provider)


def test_no_before_range_decision_without_a_registered_provider():
    """Regression guard: with no `BEFORE_RANGE_HOOK` provider registered, no
    `before_range` decision is ever raised -- byte-for-byte the pre-OQ-47
    result, mirroring `test_combat.py`'s own baseline normal-round shape."""
    game = _combat_game(acting_blood=2, blocking_blood=0)

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("mend_damage", "1")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "hand_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    actor.assert_exhausted()
    defender.assert_exhausted()


def test_before_range_offered_exactly_once_per_combat_even_across_two_rounds():
    """ "Only usable before range is determined during the first round" --
    offered during round 1 only, never again in round 2, even though a
    second round follows (someone presses)."""
    calls: list[str] = []
    _register_logging_provider(calls)
    game = _combat_game(acting_blood=2, blocking_blood=0)

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("mend_damage", "1")
    actor.expect("press", "press")  # round 1: actor presses
    actor.expect("strike_choice", "hand_strike")  # round 2
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "hand_strike")
    defender.expect("strike_choice", "no_strike")  # round 2
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.zone_of("B1") == "torpor"  # round 2 ends combat
    assert calls == ["P1", "P2"]  # exactly one combat's worth of offers, not two
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_before_range_offers_the_acting_combatants_controller_first():
    """Same ordering precedent as Press/End of Round/Determine Range (OQ-3,
    module docstring): the acting combatant's controller (P1) is asked --
    and decides -- first."""
    acting_used = {"value": False}
    blocking_used = {"value": False}

    def acting_provider(state, context):
        if context["player"] != "P1" or acting_used["value"]:
            return []

        def use(s):
            acting_used["value"] = True

        return [hooks.HookOption(choice=Choice("acting_option", "P1's option"), apply=use)]

    def blocking_provider(state, context):
        if context["player"] != "P2" or blocking_used["value"]:
            return []

        def use(s):
            blocking_used["value"] = True

        return [hooks.HookOption(choice=Choice("blocking_option", "P2's option"), apply=use)]

    hooks.register(BEFORE_RANGE_HOOK, acting_provider)
    hooks.register(BEFORE_RANGE_HOOK, blocking_provider)
    game = _combat_game(acting_blood=2, blocking_blood=0)

    actor = ScriptedAgent("P1")
    actor.expect("before_range", "acting_option")  # P1 offered -- and decides -- first
    actor.expect("strike_choice", "hand_strike")
    actor.expect("mend_damage", "1")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("before_range", "blocking_option")  # only then offered to P2
    defender.expect("strike_choice", "hand_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert acting_used["value"] is True
    assert blocking_used["value"] is True
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_before_range_runs_before_range_is_determined():
    """`state.combat_range` is still unset (`None`) while this window is
    open -- Combat Sequence step 1 strictly precedes step 2 "Determine
    Range", which is what first sets it to `CLOSE_RANGE`."""
    captured: list[str | None] = []

    def provider(state, context):
        if context["player"] == "P1":
            captured.append(state.combat_range)
        return []

    hooks.register(BEFORE_RANGE_HOOK, provider)
    game = _combat_game(acting_blood=2, blocking_blood=0)

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("mend_damage", "1")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "hand_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert captured == [None]
    assert game.state.combat_range is None  # reset once combat returns


def test_before_range_provider_can_attach_a_card_to_the_hosting_vampire():
    """A provider's own `apply(state)` attaches a card directly -- mirrors
    `cards/celerity.py`'s own non-unique-attachment pattern -- with no
    further engine support needed."""

    def provider(state, context):
        if context["player"] != "P1":
            return []
        vampire = state.players["P1"].vampires[context["acting_vampire"]]
        if any(a.krcg_id == WWS_KRCG_ID for a in vampire.attachments):
            return []  # "A minion can have only one Weighted Walking Stick."

        def apply(s):
            attach_card(
                s,
                vampire,
                controller=vampire.controller,
                krcg_id=WWS_KRCG_ID,
                name="Weighted Walking Stick",
                counters=5,
            )

        return [
            hooks.HookOption(choice=Choice("play_wws", "Play Weighted Walking Stick"), apply=apply)
        ]

    hooks.register(BEFORE_RANGE_HOOK, provider)
    game = _combat_game(acting_blood=2, blocking_blood=0)

    actor = ScriptedAgent("P1")
    actor.expect("before_range", "play_wws")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("mend_damage", "1")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "hand_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    attachments = game.vampire("V1").attachments
    assert len(attachments) == 1
    assert attachments[0].krcg_id == WWS_KRCG_ID
    assert attachments[0].counters == 5
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_weighted_walking_stick_shaped_stand_in_burns_a_counter_per_damage_inflicted():
    """Proves `BEFORE_RANGE_HOOK` (attachment) and `COMBAT_STRIKE_OPTION_
    HOOK` (the strike itself) compose into Weighted Walking Stick's own
    printed effect with no engine change to either hook's existing contract
    -- the fake providers below are exactly what a future `cards/
    weighted_walking_stick.py` module would register."""

    def attach_provider(state, context):
        if context["player"] != "P1":
            return []
        vampire = state.players["P1"].vampires[context["acting_vampire"]]
        if any(a.krcg_id == WWS_KRCG_ID for a in vampire.attachments):
            return []  # "A minion can have only one Weighted Walking Stick."

        def apply(s):
            attach_card(
                s,
                vampire,
                controller=vampire.controller,
                krcg_id=WWS_KRCG_ID,
                name="Weighted Walking Stick",
                counters=5,
            )

        return [
            hooks.HookOption(choice=Choice("play_wws", "Play Weighted Walking Stick"), apply=apply)
        ]

    def strike_provider(state, context):
        if context["player"] != "P1":
            return []
        vampire = state.players["P1"].vampires[context["vampire"]]
        wws = next((a for a in vampire.attachments if a.krcg_id == WWS_KRCG_ID), None)
        if wws is None or (wws.counters or 0) <= 0:
            return []

        def apply(s):
            amount = 2  # strength (1) + 1, per the card's own printed text
            wws.counters = max(0, (wws.counters or 0) - min(amount, wws.counters or 0))
            if wws.counters == 0:
                vampire.attachments.remove(wws)
            return amount

        return [
            hooks.HookOption(
                choice=Choice("wws_strike", "Weighted Walking Stick: strike"), apply=apply
            )
        ]

    hooks.register(BEFORE_RANGE_HOOK, attach_provider)
    hooks.register(COMBAT_STRIKE_OPTION_HOOK, strike_provider)
    game = _combat_game(acting_blood=2, blocking_blood=3)

    actor = ScriptedAgent("P1")
    actor.expect("before_range", "play_wws")
    actor.expect("strike_choice", "wws_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("mend_damage", "2")  # mends the full 2 points dealt
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    wws = game.vampire("V1").attachments[0]
    assert wws.counters == 3  # 5 - 2 damage inflicted
    actor.assert_exhausted()
    defender.assert_exhausted()


# --- Interaction with OQ-46's `woken` eligibility override ------------------


def test_a_woken_successful_blocker_is_still_is_ready_unlocked_during_before_range():
    """Combines OQ-46 (`VampireInPlay.woken`/`is_ready_unlocked`, `docs/
    OPEN_QUESTIONS.md`) and OQ-47 (this hook): a vampire woken by a reaction
    card during the block-attempt phase, and then the (successful) blocker,
    stays `is_ready_unlocked` for the whole combat that follows -- `engine/
    action.py::perform_minion_action`'s blocked branch only calls
    `clear_woken_vampires` once its own `run_combat` call *returns*, strictly
    after `BEFORE_RANGE_HOOK`'s own round-1-only window. Per On the Qui
    Vive's own "...until the end of the action" (combat is part of the same
    action), a provider gated on `is_ready_unlocked` during this window must
    still see this vampire as eligible -- confirmed here with no change to
    either mechanism."""
    seen_eligible: list[bool] = []

    def provider(state, context):
        del context
        blocker = state.players["P2"].vampires["B1"]
        seen_eligible.append(blocker.is_ready_unlocked)
        return []

    hooks.register(BEFORE_RANGE_HOOK, provider)
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=5, blood=1)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=5, blood=0, locked=True)
    game = builder.build()
    game.vampire("B1").woken = True

    def resolve(pending):
        del pending

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")  # offered as an ordinary candidate
    defender.expect("strike_choice", "no_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    perform_minion_action(
        game.state, "P1", "P2", game.vampire("V1"), base_stealth=0, resolve=resolve
    )

    assert seen_eligible == [True, True]  # queried once per combatant, round 1 only
    assert game.vampire("B1").woken is False  # cleared once the action itself ends
    actor.assert_exhausted()
    defender.assert_exhausted()
