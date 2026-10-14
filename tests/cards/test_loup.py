"""Loup (krcg id 102273, `src/vtesbot/cards/loup.py`).

Card text: "Only one Loup can be played each turn.\nPut this card in play.
Toreador get +1 stealth. Burn this card at the end of the turn or after a
Toreador performs a successful action." Ruling: "Can be used even if the
stealth is not currently needed. [LSJ 20011214-2]."

One assertion per clause/ruling: the clan requirement to play or benefit
from the card (bound to the specific acting vampire, OQ-13 precedent); "put
this card in play" and the immediate "+1 stealth" delivered together by the
same play; the ongoing clan-wide "+1 stealth" grant, proven for a *second*
Toreador vampire never itself playing a copy; "only one Loup can be played
each turn"; both burn conditions, each in the scenario that actually
isolates it from the other (condition 2 fires immediately after the very
action Loup was played for if that action succeeds, so condition 1 is only
reachable when Loup was played for a *blocked* action instead); the
once-per-*instance* cap on the standing grant (module docstring); OQ-39
(resolved): the card can now be played proactively, even against a fully
unblockable action, via `STEALTH_INCREASE_HOOK`'s own two offer points
(`engine/action.py`), closing what was previously a documented known gap;
and OQ-40 (resolved -- ruling via a trusted VEKN judge, see module
docstring): both the standing bonus and the burn trigger are table-wide,
proven for a Toreador vampire benefiting from, and burning, the *other*
Methuselah's own in-play Loup.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.loup import CARD_TYPE, KRCG_ID, LOUP_STEALTH_GRANTED_KEY, NAME
from vtesbot.engine import LibraryCard, hooks
from vtesbot.engine.action import (
    ACTION_BLEED,
    PENDING_STEALTH_INCREASE_KEY,
    STEALTH_INCREASE_HOOK,
    ActiveStealthIncrease,
)
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import minion_phase
from vtesbot.engine.turn_cards import bring_turn_card_into_play, clear_turn_cards_at_end_of_turn


def _loup_card() -> LibraryCard:
    return LibraryCard(krcg_id=KRCG_ID, name=NAME, card_type=CARD_TYPE)


def _offer(game, *, acting_vampire="V1", player="P1", defender="P2", pending=None):
    return hooks.offer(
        STEALTH_INCREASE_HOOK,
        game.state,
        player=player,
        stealth=0,
        intercept=0,
        actor=player,
        defender=defender,
        acting_vampire=acting_vampire,
        action=ACTION_BLEED,
        directed=True,
        pending=pending if pending is not None else {},
    )


def test_registered_as_implemented_against_both_hooks():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.hooks == (registry.Hook.STEALTH_INCREASE, registry.Hook.ACTION_SUCCEEDED)
    assert reg.blocked_reason is None


# --- Clan requirement: "Toreador get +1 stealth" / only a Toreador may play it


def test_not_offered_when_the_acting_vampire_is_not_toreador():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Brujah")
    p1.hand.append(_loup_card())
    builder.player("P2", pool=30)
    game = builder.build()

    assert _offer(game) == []


def test_not_offered_when_no_copy_is_in_hand_or_in_play():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Toreador")
    builder.player("P2", pool=30)
    game = builder.build()

    assert _offer(game) == []


# --- "Put this card in play. Toreador get +1 stealth." (the play itself) --


def test_play_option_removes_the_card_from_hand_brings_it_into_play_and_grants_one_stealth():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Toreador")
    p1.hand.append(_loup_card())
    builder.player("P2", pool=30)
    game = builder.build()
    pending: dict = {}

    options = _offer(game, pending=pending)

    assert len(options) == 1
    assert options[0].choice.value == "loup:play"
    assert options[0].played_card_type == CARD_TYPE
    options[0].apply(game.state)
    assert pending[PENDING_STEALTH_INCREASE_KEY] == [ActiveStealthIncrease(delta=1)]
    assert game.state.players["P1"].hand == []
    turn_cards = list(game.state.players["P1"].turn_cards.values())
    assert len(turn_cards) == 1
    assert turn_cards[0].krcg_id == KRCG_ID
    assert turn_cards[0].zone == "in_play"
    assert pending[LOUP_STEALTH_GRANTED_KEY] == {turn_cards[0].instance_id}
    assert game.state.players["P1"].card_played_turn[KRCG_ID] == game.state.turn_number


# --- "Toreador get +1 stealth" (the ongoing clan-wide grant, once in play) -


def test_ongoing_bonus_benefits_a_second_toreador_vampire_without_consuming_hand_or_cap():
    """Clan-wide, not tied to the specific vampire that played the card
    (module docstring): a *different* Toreador vampire's own action also
    gets the +1, with no card left to play and no re-play of any kind."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Toreador")
    p1.ready_vampire("V2", capacity=3, blood=1, clan="Toreador")
    builder.player("P2", pool=30)
    game = builder.build()
    already_in_play = bring_turn_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)
    pending: dict = {}

    options = _offer(game, acting_vampire="V2", pending=pending)

    assert len(options) == 1
    assert options[0].choice.value == f"loup:stealth_bonus:{already_in_play.instance_id}"
    assert options[0].played_card_type is None  # not a card being played (module docstring)
    options[0].apply(game.state)
    assert pending[PENDING_STEALTH_INCREASE_KEY] == [ActiveStealthIncrease(delta=1)]
    assert game.state.players["P1"].hand == []  # nothing consumed
    assert list(game.state.players["P1"].turn_cards.values()) == [already_in_play]  # no new copy


def test_ongoing_bonus_not_offered_to_a_non_toreador_vampires_own_action():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Toreador")
    p1.ready_vampire("V2", capacity=3, blood=1, clan="Brujah")
    builder.player("P2", pool=30)
    game = builder.build()
    bring_turn_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)

    assert _offer(game, acting_vampire="V2") == []


def test_ongoing_bonus_capped_at_once_per_action():
    """Module docstring's cap: once activated in a given action's own
    `pending`, offering the hook again (as it now is, both proactively and
    reactively) must not let the flat "+1 stealth" stack further."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Toreador")
    builder.player("P2", pool=30)
    game = builder.build()
    bring_turn_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)
    pending: dict = {}
    first = _offer(game, pending=pending)
    first[0].apply(game.state)

    assert _offer(game, pending=pending) == []


# --- OQ-40 (resolved): table-wide, not controller-scoped -------------------


def test_table_wide_benefit_from_the_other_methuselahs_own_loup():
    """Ruling (module docstring): "[Masika] has +1 stealth" -- a Toreador
    vampire benefits from *any* in-play Loup, including one controlled by
    the other Methuselah entirely."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Toreador")
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("V2", capacity=3, blood=1, clan="Toreador")
    game = builder.build()
    p1_loup = bring_turn_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)

    options = _offer(game, player="P2", acting_vampire="V2", defender="P1")

    assert {o.choice.value for o in options} == {f"loup:stealth_bonus:{p1_loup.instance_id}"}


def test_table_wide_burn_from_any_toreadors_successful_action():
    """Ruling (module docstring): "Loup burns if [the action] succeeds" --
    any Toreador's successful action burns every in-play Loup, including
    one controlled by a different Methuselah than the acting vampire's own."""
    from vtesbot.engine.action import ACTION_SUCCEEDED_HOOK

    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Toreador")
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("V2", capacity=3, blood=1, clan="Toreador")
    game = builder.build()
    p1_loup = bring_turn_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)

    hooks.run_effects(
        ACTION_SUCCEEDED_HOOK,
        game.state,
        actor_player="P2",
        vampire=game.vampire("V2"),
        action=ACTION_BLEED,
    )

    assert p1_loup.zone == "burned"


def test_two_distinct_in_play_loups_each_grant_their_own_bonus_independently():
    """Per-*instance* cap (module docstring): two independently-played
    copies, one per Methuselah, are two separate sources -- both may be
    activated for the same action, stacking to +2, not collapsed into a
    single global "already granted" flag."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Toreador")
    builder.player("P2", pool=30)
    game = builder.build()
    p1_loup = bring_turn_card_into_play(game.state, "P1", krcg_id=KRCG_ID, name=NAME)
    p2_loup = bring_turn_card_into_play(game.state, "P2", krcg_id=KRCG_ID, name=NAME)
    pending: dict = {}

    options = _offer(game, pending=pending)

    assert {o.choice.value for o in options} == {
        f"loup:stealth_bonus:{p1_loup.instance_id}",
        f"loup:stealth_bonus:{p2_loup.instance_id}",
    }
    for option in options:
        option.apply(game.state)

    assert pending[PENDING_STEALTH_INCREASE_KEY] == [
        ActiveStealthIncrease(delta=1),
        ActiveStealthIncrease(delta=1),
    ]


# --- "Only one Loup can be played each turn." -----------------------------


def test_cap_blocks_a_second_play_within_the_same_turn_even_after_the_first_is_burned():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Toreador")
    p1.hand.append(_loup_card())
    p1.hand.append(_loup_card())
    builder.player("P2", pool=30)
    game = builder.build()

    first = _offer(game)
    first[0].apply(game.state)
    turn_card = next(iter(game.state.players["P1"].turn_cards.values()))
    turn_card.zone = "burned"  # simulate burn condition 2 firing later the same turn

    assert _offer(game) == []  # cap already spent this turn, despite a second copy in hand


def test_cap_resets_on_a_later_turn():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Toreador")
    p1.hand.append(_loup_card())
    p1.hand.append(_loup_card())
    builder.player("P2", pool=30)
    game = builder.build()
    first = _offer(game)
    first[0].apply(game.state)
    turn_card = next(iter(game.state.players["P1"].turn_cards.values()))
    turn_card.zone = "burned"
    assert _offer(game) == []  # same turn: cap spent

    game.state.turn_number += 1
    later = _offer(game)
    assert len(later) == 1
    assert later[0].choice.value == "loup:play"


# --- End-to-end: play, escape a block, then self-burn (condition 2) -------


def test_end_to_end_plays_loup_to_escape_a_block_then_burns_after_the_successful_action():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Toreador")
    p1.hand.append(_loup_card())
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    # OQ-39: offered proactively, at the very top of `attempt_block`'s retry
    # loop -- before the defender is even asked to pick a blocking candidate.
    actor.expect("stealth_increase", "loup:play")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "block_with:B1")
    defender.expect("block_attempt", "decline")  # stealth(1) > intercept(0): attempt failed
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # base bleed 1 lost; block failed thanks to +1 stealth
    assert game.state.players["P1"].hand == []
    turn_card = next(iter(game.state.players["P1"].turn_cards.values()))
    assert turn_card.zone == "burned"  # condition 2: burned right after the successful action
    actor.assert_exhausted()
    defender.assert_exhausted()


# --- End-to-end: played for a blocked action, survives to end of turn ------


def test_end_to_end_played_for_a_blocked_action_survives_combat_then_burns_at_end_of_turn():
    """Condition 2 does not fire (the action was blocked, not successful),
    so condition 1 (`clear_turn_cards_at_end_of_turn`, OQ-34, already proven
    generically by `tests/rules/test_turn_cards.py`) is what finally burns
    it -- the one scenario that actually isolates condition 1 from 2. Loup's
    own standing grant is capped at once per action (module docstring), so
    once the defender's extra intercept catches back up to the increased
    stealth, there is nothing left for the actor to activate again -- no
    further decision is raised at all."""

    def extra_intercept(state, context):
        if context.get("action") != ACTION_BLEED:
            return []
        return [HookOption(choice=Choice("extra_intercept", "+1 intercept"), apply=lambda s: 1)]

    hooks.register("intercept_modifier", extra_intercept)
    try:
        builder = ScenarioBuilder(seed=1)
        p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Toreador")
        p1.hand.append(_loup_card())
        builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
        game = builder.build()
        actor = ScriptedAgent("P1")
        actor.expect("minion_phase_choice", "act_with:V1")
        actor.expect("action_choice", "bleed")
        actor.expect("stealth_increase", "loup:play")  # 0 -> 1, proactively
        actor.expect("strike_choice", "no_strike")
        actor.expect("press", "end_combat")
        defender = ScriptedAgent("P2")
        defender.expect("block_attempt", "block_with:B1")
        defender.expect("intercept_modifier", "extra_intercept")  # 0 -> 1
        defender.expect("strike_choice", "no_strike")
        defender.expect("press", "end_combat")
        game.state.agents["P1"] = actor
        game.state.agents["P2"] = defender

        minion_phase(game.state, "P1")

        assert game.pool_of("P2") == 30  # blocked: no pool lost
        turn_card = next(iter(game.state.players["P1"].turn_cards.values()))
        assert turn_card.zone == "in_play"  # survived combat: the action was not successful
        actor.assert_exhausted()
        defender.assert_exhausted()

        clear_turn_cards_at_end_of_turn(game.state, "P1")

        assert turn_card.zone == "burned"  # condition 1
    finally:
        hooks.unregister("intercept_modifier", extra_intercept)


# --- OQ-39 (resolved): proactive offer closes the "unblockable action" gap -


def test_can_be_played_proactively_even_when_the_action_is_unblockable():
    """`STEALTH_INCREASE_HOOK`'s own proactive offer, at the very top of
    `attempt_block`'s retry loop, fires before the "no candidates at all"
    short-circuit -- so, unlike the old `STEALTH_MODIFIER_HOOK`-only wiring
    (which never started at all here, see git history for the previously
    documented known gap this test used to prove), Loup can now be played
    even against a fully unblockable action."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1, clan="Toreador")
    p1.hand.append(_loup_card())
    builder.player("P2", pool=30)  # no ready vampire: unblockable regardless
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "bleed")
    actor.expect("stealth_increase", "loup:play")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # unblockable bleed succeeds regardless
    assert game.state.players["P1"].hand == []  # Loup was actually played this time
    turn_card = next(iter(game.state.players["P1"].turn_cards.values()))
    assert turn_card.zone == "burned"  # condition 2: burned right after the successful action
    actor.assert_exhausted()
    defender.assert_exhausted()
