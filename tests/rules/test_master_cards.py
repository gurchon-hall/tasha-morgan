"""Standalone Master cards in play (OQ-23, `docs/OPEN_QUESTIONS.md`):
`engine/state.py::MasterCardInPlay` / `PlayerState.master_cards`,
`engine/master_cards.py::bring_master_card_into_play` /
`detect_contest_on_bring_into_play` / `resolve_one_master_card_contest`, and
`engine/phases/unlock.py::_unlock_own_master_cards` -- the minimal
representation this entity needs, mirroring `engine/allies.py`'s own
ally-side mechanism (itself generalized a third time by `engine/
attachments.py` for OQ-22) a fourth time, for a standalone (not
attached-to-a-vampire) Master card.

Built for, and generic enough to cover, every standalone Master card found
in OQ-23's own sweep of the active 2P pool -- both "Unique" ones that need
Contested Cards tracking (Oxford University, England, used throughout as
the motivating example; also The Barrens, Chantry, Cursed Abattoir) and
non-unique ones that never contest at all (Wider View, krcg id 102180,
used below to prove that case).

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using trivial fake providers standing in for a real card's own
module -- none of the named cards is implemented here; that remains
`card-implementer`'s job once this capability exists.
"""

from helpers import ScenarioBuilder, ScenarioGame, ScriptedAgent
from vtesbot.cards._shared import play_from_hand
from vtesbot.engine import LibraryCard, build_observation, hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.master_cards import (
    bring_master_card_into_play,
    detect_contest_on_bring_into_play,
)
from vtesbot.engine.phases.master import MASTER_PHASE_PLAY_HOOK, master_phase
from vtesbot.engine.phases.unlock import unlock_phase
from vtesbot.engine.state import MasterCardInPlay

UNIQUE_CARD_KRCG_ID = 101341  # Oxford University, England's own id, reused as a stand-in
UNIQUE_CARD_NAME = "Oxford University, England"
NON_UNIQUE_CARD_KRCG_ID = 102180  # Wider View's own id, reused as a stand-in
NON_UNIQUE_CARD_NAME = "Wider View"


# --- bring_master_card_into_play ---------------------------------------------


def test_bring_master_card_into_play_creates_an_unlocked_in_play_card():
    """Unlike a recruited ally (Rulebook §4: "recruited ally cannot act
    this turn" -- enters locked), nothing locks a freshly-played Master card
    (`MasterCardInPlay`'s own docstring): it enters play `zone="in_play"`,
    `locked=False`."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()

    card = bring_master_card_into_play(
        game.state, "P1", krcg_id=UNIQUE_CARD_KRCG_ID, name=UNIQUE_CARD_NAME
    )

    assert card.controller == "P1"
    assert card.name == UNIQUE_CARD_NAME
    assert card.zone == "in_play"
    assert card.locked is False
    assert card.is_unlocked_in_play is True
    assert game.state.players["P1"].master_cards[card.instance_id] is card


def test_master_cards_get_distinct_instance_ids_in_their_own_namespace():
    """Instance ids must not collide with vampire/ally/attachment instance
    ids."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()

    card1 = bring_master_card_into_play(game.state, "P1", krcg_id=1, name="Card One")
    card2 = bring_master_card_into_play(game.state, "P1", krcg_id=1, name="Card One")

    assert card1.instance_id != card2.instance_id
    assert card1.instance_id != "P1-V1"


def test_a_non_unique_master_card_is_never_contested_by_construction():
    """Wider View's own shape ("Trifle.", no "Unique" text at all): two
    players each independently playing their own copy of the *same*
    non-unique Master card is ordinary deck construction, never a contest
    (`engine/master_cards.py`'s own module docstring). Since no card module
    for a non-unique card ever calls `detect_contest_on_bring_into_play`,
    `contested_with` simply stays `None` for both copies' whole lifetime --
    no extra field or branch is needed on `MasterCardInPlay` itself."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()

    mine = bring_master_card_into_play(
        game.state, "P1", krcg_id=NON_UNIQUE_CARD_KRCG_ID, name=NON_UNIQUE_CARD_NAME
    )
    theirs = bring_master_card_into_play(
        game.state, "P2", krcg_id=NON_UNIQUE_CARD_KRCG_ID, name=NON_UNIQUE_CARD_NAME
    )
    # No `detect_contest_on_bring_into_play` call here at all, by design.

    assert mine.contested_with is None
    assert theirs.contested_with is None
    assert mine.zone == "in_play"
    assert theirs.zone == "in_play"


# --- detect_contest_on_bring_into_play ---------------------------------------


def test_detect_contest_flags_both_same_named_cards():
    """Rulebook §4 Advanced Rules > Contested Cards: "If more than one
    unique card with the same name is brought into play, that means control
    of the card is being contested." Both copies get `contested_with` set to
    each other. Only ever correct to call for a card printed "Unique" (e.g.
    Oxford University, England, used here as the stand-in) -- see this
    module's own module docstring and the non-unique test above."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    existing = bring_master_card_into_play(
        game.state, "P2", krcg_id=UNIQUE_CARD_KRCG_ID, name=UNIQUE_CARD_NAME
    )
    incoming = bring_master_card_into_play(
        game.state, "P1", krcg_id=UNIQUE_CARD_KRCG_ID, name=UNIQUE_CARD_NAME
    )

    detect_contest_on_bring_into_play(game.state, incoming)

    assert incoming.contested_with == existing.instance_id
    assert existing.contested_with == incoming.instance_id


def test_detect_contest_turns_both_copies_out_of_play():
    """Unlike the 2P crypt-card override ("stays in play and usable"), the
    unmodified rulebook rule applies to a standalone master card: "all of
    the contested cards are turned face down and are out of play" -- both
    copies' `zone` moves off `"in_play"` to `"contested"`."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    existing = bring_master_card_into_play(
        game.state, "P2", krcg_id=UNIQUE_CARD_KRCG_ID, name=UNIQUE_CARD_NAME
    )
    incoming = bring_master_card_into_play(
        game.state, "P1", krcg_id=UNIQUE_CARD_KRCG_ID, name=UNIQUE_CARD_NAME
    )

    detect_contest_on_bring_into_play(game.state, incoming)

    assert incoming.zone == "contested"
    assert existing.zone == "contested"
    assert incoming.is_unlocked_in_play is False
    assert existing.is_unlocked_in_play is False


def test_differently_named_cards_are_not_contested():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    other = bring_master_card_into_play(game.state, "P2", krcg_id=1, name="Card One")
    mine = bring_master_card_into_play(game.state, "P1", krcg_id=2, name="Card Two")

    detect_contest_on_bring_into_play(game.state, mine)

    assert mine.contested_with is None
    assert other.contested_with is None
    assert mine.zone == "in_play"
    assert other.zone == "in_play"


def test_a_players_own_two_cards_of_the_same_name_do_not_contest_each_other():
    """`detect_contest_on_bring_into_play` only ever checks the opponent
    (mirrors `detect_contest_on_recruit`/`detect_contest_on_reveal`'s own
    scope -- OQ-16, still open, unchanged by this entry)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    first = bring_master_card_into_play(
        game.state, "P1", krcg_id=UNIQUE_CARD_KRCG_ID, name=UNIQUE_CARD_NAME
    )
    second = bring_master_card_into_play(
        game.state, "P1", krcg_id=UNIQUE_CARD_KRCG_ID, name=UNIQUE_CARD_NAME
    )

    detect_contest_on_bring_into_play(game.state, second)

    assert first.contested_with is None
    assert second.contested_with is None
    assert first.zone == "in_play"
    assert second.zone == "in_play"


# --- Observation --------------------------------------------------------------


def test_contested_cards_still_show_their_full_identity_to_both_players():
    """Same reasoning as `AllyView`'s own docstring: a Master card is played
    face up, so by construction both copies' identities are already
    mutually known the instant the contest is created -- no anonymization
    branch is needed."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    existing = bring_master_card_into_play(
        game.state, "P2", krcg_id=UNIQUE_CARD_KRCG_ID, name=UNIQUE_CARD_NAME
    )
    incoming = bring_master_card_into_play(
        game.state, "P1", krcg_id=UNIQUE_CARD_KRCG_ID, name=UNIQUE_CARD_NAME
    )
    detect_contest_on_bring_into_play(game.state, incoming)

    obs_p1 = build_observation(game.state, "P1")
    obs_p2 = build_observation(game.state, "P2")

    for obs, instance_id in ((obs_p1, incoming.instance_id), (obs_p2, existing.instance_id)):
        view = next(v for v in obs.master_cards if v.instance_id == instance_id)
        assert view.name == UNIQUE_CARD_NAME
        assert view.zone == "contested"
        assert view.contested is True


def test_uncontested_card_observation_reports_contested_false():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    bring_master_card_into_play(game.state, "P1", krcg_id=1, name="Solo Card")

    obs = build_observation(game.state, "P2")

    view = next(v for v in obs.master_cards if v.name == "Solo Card")
    assert view.contested is False
    assert view.zone == "in_play"
    assert view.locked is False


# --- Unlock phase: lock/unlock + contest resolution --------------------------


def test_unlock_phase_unlocks_a_locked_in_play_card():
    """Rulebook §4 Unlock Phase: "you must unlock all of your cards" --
    not restricted to minions. Needed for Oxford's own repeatable "lock this
    card ... to get +2X votes" ability to ever be usable a second time."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    card = bring_master_card_into_play(
        game.state, "P1", krcg_id=UNIQUE_CARD_KRCG_ID, name=UNIQUE_CARD_NAME
    )
    card.locked = True
    game.state.agents["P1"] = ScriptedAgent("P1")  # no decisions expected

    unlock_phase(game.state, "P1")

    assert card.locked is False
    assert card.zone == "in_play"


def _contested_pair(game: ScenarioGame) -> tuple[MasterCardInPlay, MasterCardInPlay]:
    existing = bring_master_card_into_play(
        game.state, "P2", krcg_id=UNIQUE_CARD_KRCG_ID, name=UNIQUE_CARD_NAME
    )
    incoming = bring_master_card_into_play(
        game.state, "P1", krcg_id=UNIQUE_CARD_KRCG_ID, name=UNIQUE_CARD_NAME
    )
    detect_contest_on_bring_into_play(game.state, incoming)
    return incoming, existing


def test_contested_cards_controller_is_offered_pay_or_yield_during_unlock():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10)
    builder.player("P2", pool=10)
    game = builder.build()
    _contested_pair(game)
    agent = ScriptedAgent("P1").expect("master_card_contest_resolution", "pay")
    game.state.agents["P1"] = agent

    unlock_phase(game.state, "P1")

    assert game.state.players["P1"].pool == 9
    agent.assert_exhausted()


def test_paying_keeps_both_copies_contested_and_out_of_play():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10)
    builder.player("P2", pool=10)
    game = builder.build()
    mine, opponent = _contested_pair(game)
    game.state.agents["P1"] = ScriptedAgent("P1").expect("master_card_contest_resolution", "pay")

    unlock_phase(game.state, "P1")

    assert mine.zone == "contested"
    assert mine.contested_with == opponent.instance_id
    assert opponent.zone == "contested"
    assert opponent.contested_with == mine.instance_id


def test_yielding_burns_the_yielding_card_and_does_not_immediately_restore_the_opponent():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10)
    builder.player("P2", pool=10)
    game = builder.build()
    mine, opponent = _contested_pair(game)
    game.state.agents["P1"] = ScriptedAgent("P1").expect("master_card_contest_resolution", "yield")

    unlock_phase(game.state, "P1")

    assert mine.zone == "burned"
    assert mine.contested_with is None
    assert game.state.players["P1"].pool == 10  # yielding costs no pool
    assert opponent.contested_with is None
    assert opponent.zone == "contested"  # not instantaneous -- see below


def test_the_surviving_cards_zone_is_only_restored_on_its_controllers_own_next_unlock_phase():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10)
    builder.player("P2", pool=10)
    game = builder.build()
    mine, opponent = _contested_pair(game)
    game.state.agents["P1"] = ScriptedAgent("P1").expect("master_card_contest_resolution", "yield")
    unlock_phase(game.state, "P1")
    assert opponent.zone == "contested"  # not yet restored

    agent_p2 = ScriptedAgent("P2")  # no pending effects expected for P2
    game.state.agents["P2"] = agent_p2

    unlock_phase(game.state, "P2")

    assert opponent.zone == "in_play"
    assert opponent.locked is False
    assert opponent.contested_with is None
    agent_p2.assert_exhausted()


def test_zero_regression_an_uncontested_cards_zone_is_left_untouched_by_unlock():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10)
    builder.player("P2", pool=10)
    game = builder.build()
    solo = bring_master_card_into_play(game.state, "P1", krcg_id=1, name="Solo Card")
    game.state.agents["P1"] = ScriptedAgent("P1")  # no decisions expected

    unlock_phase(game.state, "P1")

    assert solo.zone == "in_play"
    assert solo.contested_with is None


# --- production "master_phase_play" call site --------------------------------

FAKE_CARD_KRCG_ID = 778


def _fake_card_provider(state, context):
    player = context["player"]
    if not any(c.krcg_id == FAKE_CARD_KRCG_ID for c in state.players[player].hand):
        return []

    def _apply(s):
        play_from_hand(s, player, FAKE_CARD_KRCG_ID)
        card = bring_master_card_into_play(
            s, player, krcg_id=FAKE_CARD_KRCG_ID, name=UNIQUE_CARD_NAME
        )
        detect_contest_on_bring_into_play(s, card)
        return False  # not a trifle

    return [
        hooks.HookOption(
            choice=Choice("play_fake_oxford", "Play Fake Oxford"),
            apply=_apply,
        )
    ]


def _fake_card() -> LibraryCard:
    return LibraryCard(krcg_id=FAKE_CARD_KRCG_ID, name=UNIQUE_CARD_NAME, card_type="master")


def test_master_phase_play_end_to_end_brings_a_card_into_play_and_detects_contest():
    """Production call site, not just the lower-level helper (same bar
    OQ-7/OQ-13's own resolutions set): a fake `"master_phase_play"` provider,
    mirroring the generic Life in the City pattern (`engine/phases/
    master.py`, no engine change needed there), plays a standalone master
    card from hand and brings it into play, correctly detecting a contest
    against an already-in-play same-named opposing copy."""
    hooks.register(MASTER_PHASE_PLAY_HOOK, _fake_card_provider)
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30)
    pb.hand.append(_fake_card())
    builder.player("P2", pool=30)
    game = builder.build()
    existing = bring_master_card_into_play(
        game.state, "P2", krcg_id=FAKE_CARD_KRCG_ID, name=UNIQUE_CARD_NAME
    )

    agent = ScriptedAgent("P1").expect("master_phase_action", "play_fake_oxford")
    game.state.agents["P1"] = agent
    game.state.agents["P2"] = ScriptedAgent("P2")

    master_phase(game.state, "P1")

    brought_in = next(iter(game.state.players["P1"].master_cards.values()))
    assert brought_in.contested_with == existing.instance_id
    assert existing.contested_with == brought_in.instance_id
    assert brought_in.zone == "contested"
    assert existing.zone == "contested"
    agent.assert_exhausted()
