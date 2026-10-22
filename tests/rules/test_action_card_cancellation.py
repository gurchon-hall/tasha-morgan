"""Action-card cancel-as-played (ENG-037):
`engine/phases/minion.py::_perform_action_card` offers `hooks.
CANCEL_AS_PLAYED_HOOK` to the other Methuselah, via `hooks.
offer_cancel_as_played`, strictly before `perform_minion_action` would
ever lock the acting vampire -- Rulebook Advanced Rules "Reflex cards"
(`data/sources/rulebook/2026-10-09/2-card-types.md:323-326`: "A minion can
play a reflex card to cancel a specified kind of card played against them
as it is played") and "Cancel a card" (`3-playing-the-game.md:103-108`):
"If an action card is cancelled, the minion does not lock (they do not pay
for the action card), and they can play the same action card again."

Distinct from `hooks.apply_chosen_option` (ENG-022, built for a Reaction/
Action-Modifier/political-referendum `HookOption`, whose own `cost` is
paid unconditionally even when canceled): an Action card's `HookOption` has
no `cost` field in play at all here, by construction.

Finding 1 (`rules-auditor`): the replacement
card must be drawn strictly *after* this cancel window closes, win or
lose -- Rulebook §2 Card Types `2-card-types.md:124-126`, "Even drawing
to replace cards, comes after this time period."
`test_replacement_card_is_drawn_after_the_cancel_window_closes_not_before`
below proves the ordering directly, using a fake provider that calls
`remove_from_hand` (not `play_from_hand`) and sets `ActionCardSpec.name`,
mirroring every real `ACTION_CARD_PLAY_HOOK` provider post-fix. Finding 2
(the generic "same named action card at most once per turn" cap) has its
own dedicated test file, `tests/rules/test_action_card_name_cap.py`.

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a trivial fake `"action_card_play"` provider and a
trivial fake `CANCEL_AS_PLAYED_HOOK` provider standing in for a future
Reflex-type card's own module -- no Reflex-type card is implemented in
this project yet (module/ENG-037 docstring)."""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards._shared import play_from_hand, remove_from_hand
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, ActionCardSpec, minion_phase
from vtesbot.engine.pool import lose_pool

FAKE_ACTION_CARD_KRCG_ID = 999
FAKE_ACTION_CARD_BLEED_AMOUNT = 2
FAKE_NAMED_ACTION_CARD_KRCG_ID = 998
FAKE_NAMED_ACTION_CARD_NAME = "Fake Named Cancelable Action Card"


def _fake_action_card() -> LibraryCard:
    return LibraryCard(
        krcg_id=FAKE_ACTION_CARD_KRCG_ID, name="Fake Cancelable Action Card", card_type="action"
    )


def _fake_action_card_provider(state, context):
    """Stand-in for a real Action card module's own `"action_card_play"`
    provider (mirrors `tests/rules/test_action_card_play.py`'s own fake):
    one option, offered only while its own card is in hand; consumes its
    card immediately and resolves as a fixed directed bleed. Carries
    `played_card_type="Action"` (ENG-023's own convention, matching every
    real `ACTION_CARD_PLAY_HOOK` provider in this pool, e.g. `cards/
    dominate_kine.py`) so a `CANCEL_AS_PLAYED_HOOK` provider can gate on
    "only cancel an Action card"."""
    player = context["player"]
    other = next(p for p in state.players if p != player)
    if not any(c.krcg_id == FAKE_ACTION_CARD_KRCG_ID for c in state.players[player].hand):
        return []

    def _apply(s):
        play_from_hand(s, player, FAKE_ACTION_CARD_KRCG_ID)

        def resolve(pending):
            del pending
            lose_pool(s, other, FAKE_ACTION_CARD_BLEED_AMOUNT)

        return ActionCardSpec(base_stealth=0, directed=True, resolve=resolve)

    return [
        hooks.HookOption(
            choice=Choice("play_fake_action_card", "Play Fake Cancelable Action Card"),
            apply=_apply,
            played_card_type="Action",
        )
    ]


def _cancel_action_cards_provider(state, context):
    del state
    if context.get("canceled_card_type") != "Action":
        return []
    return [hooks.HookOption(choice=Choice("cancel_it", "Cancel as played"), apply=lambda s: None)]


def test_canceled_action_card_does_not_lock_and_suppresses_its_own_effect():
    hooks.register(ACTION_CARD_PLAY_HOOK, _fake_action_card_provider)
    hooks.register(hooks.CANCEL_AS_PLAYED_HOOK, _cancel_action_cards_provider)
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    pb.hand.append(_fake_action_card())
    builder.player("P2", pool=30)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "play_fake_action_card")
    # V1 never locked (see assertion below): the minion-phase loop offers
    # it again immediately -- end voluntarily to keep this test focused on
    # the cancellation itself (the "can play it again" case is its own
    # test below).
    actor.expect("minion_phase_choice", "end_minion_phase")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect(hooks.CANCEL_AS_PLAYED_HOOK, "cancel_it")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30  # resolve() never ran: canceled.
    # Still "considered played" (Rulebook "Cancel a card"): the physical
    # card already left the hand and sits in the ash heap.
    assert not any(c.krcg_id == FAKE_ACTION_CARD_KRCG_ID for c in game.state.players["P1"].hand)
    assert any(c.krcg_id == FAKE_ACTION_CARD_KRCG_ID for c in game.state.players["P1"].ash_heap)
    assert game.vampire("V1").locked is False  # "the minion does not lock"
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_after_cancellation_the_same_named_action_card_can_be_played_again():
    """ "...they can play the same action card again." -- proven here by a
    second physical copy: the first copy was canceled (and already sits in
    the ash heap), the vampire never locked, so the minion-phase loop still
    offers V1 to act with again this same turn, and the second play
    resolves normally (no cancel provider fires the second time)."""
    hooks.register(ACTION_CARD_PLAY_HOOK, _fake_action_card_provider)
    canceled_once: list[bool] = []

    def _cancel_once_provider(state, context):
        del state
        if context.get("canceled_card_type") != "Action" or canceled_once:
            return []

        def apply(s):
            del s
            canceled_once.append(True)

        return [hooks.HookOption(choice=Choice("cancel_it", "Cancel as played"), apply=apply)]

    hooks.register(hooks.CANCEL_AS_PLAYED_HOOK, _cancel_once_provider)
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    pb.hand.append(_fake_action_card())
    pb.hand.append(_fake_action_card())
    builder.player("P2", pool=30)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "play_fake_action_card")  # first copy: canceled
    actor.expect("minion_phase_choice", "act_with:V1")  # same vampire: never locked
    actor.expect("action_choice", "play_fake_action_card")  # second copy: not canceled
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect(hooks.CANCEL_AS_PLAYED_HOOK, "cancel_it")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert canceled_once == [True]
    assert game.pool_of("P2") == 30 - FAKE_ACTION_CARD_BLEED_AMOUNT  # second copy resolved.
    assert game.vampire("V1").locked is True  # locked only by the successful second play.
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_zero_regression_no_cancel_provider_registered_action_resolves_normally():
    hooks.register(ACTION_CARD_PLAY_HOOK, _fake_action_card_provider)
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    pb.hand.append(_fake_action_card())
    builder.player("P2", pool=30)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "play_fake_action_card")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")  # never asked: no cancel provider exists.

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 30 - FAKE_ACTION_CARD_BLEED_AMOUNT
    actor.assert_exhausted()


# --- Finding 1: replacement draw strictly after the cancel window --------


def _fake_named_action_card() -> LibraryCard:
    return LibraryCard(
        krcg_id=FAKE_NAMED_ACTION_CARD_KRCG_ID, name=FAKE_NAMED_ACTION_CARD_NAME, card_type="action"
    )


def _fake_named_action_card_provider(state, context):
    """Mirrors a real `ACTION_CARD_PLAY_HOOK` provider post-ENG-037 Finding 1
    fix (e.g. `cards/dominate_kine.py`): calls `remove_from_hand` (not
    `play_from_hand`) inside `apply()`, and sets `ActionCardSpec.name` so
    `_perform_action_card` itself draws the replacement once its own cancel
    window closes, win or lose (Finding 1)."""
    player = context["player"]
    other = next(p for p in state.players if p != player)
    if not any(c.krcg_id == FAKE_NAMED_ACTION_CARD_KRCG_ID for c in state.players[player].hand):
        return []

    def _apply(s):
        remove_from_hand(s, player, FAKE_NAMED_ACTION_CARD_KRCG_ID)

        def resolve(pending):
            del pending
            lose_pool(s, other, FAKE_ACTION_CARD_BLEED_AMOUNT)

        return ActionCardSpec(
            base_stealth=0, directed=True, resolve=resolve, name=FAKE_NAMED_ACTION_CARD_NAME
        )

    return [
        hooks.HookOption(
            choice=Choice("play_fake_named_action_card", "Play Fake Named Cancelable Action Card"),
            apply=_apply,
            played_card_type="Action",
        )
    ]


def test_replacement_card_is_drawn_after_the_cancel_window_closes_not_before():
    """ENG-037 Finding 1: Rulebook §3 "Playing a
    Card" (`data/sources/rulebook/2026-10-09/3-playing-the-game.md:
    124-126`), "Even drawing to replace cards, comes after this [cancel-
    as-played] time period." -- proven by having the cancel provider's own
    `apply` observe hand/library sizes strictly between the card leaving
    the hand (`remove_from_hand`) and its replacement being drawn
    (`draw_replacement_card`, run only after this cancel window closes)."""
    hooks.register(ACTION_CARD_PLAY_HOOK, _fake_named_action_card_provider)
    observed: list[tuple[int, int]] = []

    def _cancel_and_observe_provider(state, context):
        if context.get("canceled_card_type") != "Action":
            return []

        def apply(s):
            observed.append((len(s.players["P1"].hand), len(s.players["P1"].library)))

        return [hooks.HookOption(choice=Choice("cancel_it", "Cancel as played"), apply=apply)]

    hooks.register(hooks.CANCEL_AS_PLAYED_HOOK, _cancel_and_observe_provider)
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    pb.hand.append(_fake_named_action_card())
    pb.library_cards(["Library Filler"])
    builder.player("P2", pool=30)
    game = builder.build()

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "play_fake_named_action_card")
    actor.expect("minion_phase_choice", "end_minion_phase")  # never locked: canceled.
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect(hooks.CANCEL_AS_PLAYED_HOOK, "cancel_it")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    # At cancel time: the card already left hand, but its replacement had
    # not yet been drawn from the (still-full) library.
    assert observed == [(0, 1)]
    # Drawn anyway, after the window closed -- "still considered played".
    assert len(game.state.players["P1"].hand) == 1
    assert game.state.players["P1"].library == []
    assert any(
        c.krcg_id == FAKE_NAMED_ACTION_CARD_KRCG_ID for c in game.state.players["P1"].ash_heap
    )
    assert game.pool_of("P2") == 30  # resolve() never ran: canceled.
    assert game.vampire("V1").locked is False  # "the minion does not lock"
    actor.assert_exhausted()
    defender.assert_exhausted()
