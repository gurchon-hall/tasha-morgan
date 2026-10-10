"""Contested unique allies (OQ-10, `docs/OPEN_QUESTIONS.md`): an ally
printed "Unique" (e.g. 47th Street Royals) can collide with a same-named
opposing ally, exactly like the crypt-card case `engine/contests.py`
already handles -- except the 2P variant's "contested crypt cards stay in
play and usable" override is scoped to crypt cards only, so an ally contest
follows the *unmodified* Rulebook SS4 Advanced Rules > Contested Cards rule:
both copies are "turned face down and are out of play" for the contest's
duration (`engine/allies.py::detect_contest_on_recruit`).

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*; 47th Street Royals itself stays `blocked`/OQ-14 and is not
touched here (`card-implementer`'s job once this capability exists).
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards._shared import play_from_hand_pending
from vtesbot.engine import LibraryCard, build_observation, hooks
from vtesbot.engine.allies import RecruitAllySpec, detect_contest_on_recruit, recruit_ally
from vtesbot.engine.decision import Choice
from vtesbot.engine.phases.minion import RECRUIT_ALLY_PLAY_HOOK, minion_phase

UNIQUE_ALLY_KRCG_ID = 102217  # 47th Street Royals' own id, reused as a stand-in
UNIQUE_ALLY_NAME = "47th Street Royals"


@pytest.fixture(autouse=True)
def _clean_hooks():
    yield
    hooks.clear()


def test_detect_contest_on_recruit_flags_both_same_named_allies():
    """Rulebook SS4 Advanced Rules > Contested Cards: "If more than one
    unique card with the same name is brought into play, that means control
    of the card is being contested." Both copies get `contested_with` set to
    each other, mirroring `engine/contests.py::detect_contest_on_reveal`'s
    own two-sided flagging for vampires."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    existing = recruit_ally(
        game.state, "P2", krcg_id=UNIQUE_ALLY_KRCG_ID, name=UNIQUE_ALLY_NAME, life=2, strength=1
    )
    incoming = recruit_ally(
        game.state, "P1", krcg_id=UNIQUE_ALLY_KRCG_ID, name=UNIQUE_ALLY_NAME, life=2, strength=1
    )

    detect_contest_on_recruit(game.state, incoming)

    assert incoming.contested_with == existing.instance_id
    assert existing.contested_with == incoming.instance_id


def test_detect_contest_on_recruit_turns_both_copies_out_of_play():
    """Unlike the 2P crypt-card override ("stays in play and usable"), the
    unmodified rulebook rule applies to an ally: "all of the contested cards
    are turned face down and are out of play" -- both copies' `zone` moves
    off `"ready"` to `"contested"`, not just the incoming one."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    existing = recruit_ally(
        game.state, "P2", krcg_id=UNIQUE_ALLY_KRCG_ID, name=UNIQUE_ALLY_NAME, life=2
    )
    incoming = recruit_ally(
        game.state, "P1", krcg_id=UNIQUE_ALLY_KRCG_ID, name=UNIQUE_ALLY_NAME, life=2
    )

    detect_contest_on_recruit(game.state, incoming)

    assert incoming.zone == "contested"
    assert existing.zone == "contested"
    assert incoming.is_ready_unlocked is False
    assert existing.is_ready_unlocked is False


def test_differently_named_allies_are_not_contested():
    """ "Only when needed": two allies with different printed names never
    collide, no matter who controls them."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    other = recruit_ally(game.state, "P2", krcg_id=1, name="Ally One", life=1)
    mine = recruit_ally(game.state, "P1", krcg_id=2, name="Ally Two", life=1)

    detect_contest_on_recruit(game.state, mine)

    assert mine.contested_with is None
    assert other.contested_with is None
    assert mine.zone == "ready"
    assert other.zone == "ready"


def test_a_players_own_two_allies_of_the_same_name_do_not_contest_each_other():
    """`detect_contest_on_recruit` only ever checks the opponent (mirrors
    `detect_contest_on_reveal`'s own scope, `engine/contests.py`) -- normal
    deck construction cannot reach this in the first place (CLAUDE.md "no
    guessing ahead of a sourced need": the rulebook's own "contest yourself"
    edge case is equally unimplemented on the vampire side today)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    first = recruit_ally(
        game.state, "P1", krcg_id=UNIQUE_ALLY_KRCG_ID, name=UNIQUE_ALLY_NAME, life=2
    )
    second = recruit_ally(
        game.state, "P1", krcg_id=UNIQUE_ALLY_KRCG_ID, name=UNIQUE_ALLY_NAME, life=2
    )

    detect_contest_on_recruit(game.state, second)

    assert first.contested_with is None
    assert second.contested_with is None
    assert first.zone == "ready"
    assert second.zone == "ready"


def test_contested_allies_still_show_their_full_identity_to_both_players():
    """OQ-10's own sourcing: a contested ally's identity is not actually
    secret from either player -- "Recruit Ally" is played face up (Rulebook
    SS4 "Announce the Action"), so both copies were already mutually visible
    the instant the second one was recruited, creating the contest. Unlike
    `VampireView`'s `visible_identity` branch, `AllyView` never hides a
    contested ally's name/stats; it only exposes `zone == "contested"` and
    `contested == True` so an agent knows it is currently out of play."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    existing = recruit_ally(
        game.state, "P2", krcg_id=UNIQUE_ALLY_KRCG_ID, name=UNIQUE_ALLY_NAME, life=2, strength=1
    )
    incoming = recruit_ally(
        game.state, "P1", krcg_id=UNIQUE_ALLY_KRCG_ID, name=UNIQUE_ALLY_NAME, life=2, strength=1
    )
    detect_contest_on_recruit(game.state, incoming)

    obs_p1 = build_observation(game.state, "P1")
    obs_p2 = build_observation(game.state, "P2")

    for obs, instance_id in ((obs_p1, incoming.instance_id), (obs_p2, existing.instance_id)):
        view = next(v for v in obs.allies if v.instance_id == instance_id)
        assert view.name == UNIQUE_ALLY_NAME
        assert view.life == 2
        assert view.strength == 1
        assert view.zone == "contested"
        assert view.contested is True


def test_uncontested_ally_observation_reports_contested_false():
    """Zero-regression companion to the above: an ally that never collides
    with anything keeps `contested is False` (and `zone == "ready"`), same
    as every pre-existing ally-visibility test."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    recruit_ally(game.state, "P1", krcg_id=1, name="Solo Ally", life=1)

    obs = build_observation(game.state, "P2")

    view = next(v for v in obs.allies if v.name == "Solo Ally")
    assert view.contested is False
    assert view.zone == "ready"


FAKE_ALLY_KRCG_ID = 777


def _fake_ally_provider(state, context):
    player = context["player"]
    if not any(c.krcg_id == FAKE_ALLY_KRCG_ID for c in state.players[player].hand):
        return []

    def _apply(s):
        card = play_from_hand_pending(s, player, FAKE_ALLY_KRCG_ID)
        return RecruitAllySpec(card=card, life=2, strength=1, bleed=0)

    return [
        hooks.HookOption(
            choice=Choice("recruit_fake_ally", "Recruit Fake Ally"),
            apply=_apply,
        )
    ]


def _fake_ally_card() -> LibraryCard:
    return LibraryCard(krcg_id=FAKE_ALLY_KRCG_ID, name=UNIQUE_ALLY_NAME, card_type="ally")


def test_recruit_ally_action_end_to_end_detects_the_contest():
    """Production call site, not just the lower-level helper (same bar OQ-13's
    own resolution set): recruiting a same-named ally through the real
    `"recruit_ally_play"` minion-phase path (`_perform_recruit_ally`) must
    itself trigger `detect_contest_on_recruit`, not merely a direct
    `recruit_ally(...)` call in a scenario test."""
    hooks.register(RECRUIT_ALLY_PLAY_HOOK, _fake_ally_provider)
    builder = ScenarioBuilder(seed=1)
    pb = builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=1)
    pb.hand.append(_fake_ally_card())
    builder.player("P2", pool=30)  # no ready vampire: nothing to block with
    game = builder.build()
    existing = recruit_ally(
        game.state, "P2", krcg_id=UNIQUE_ALLY_KRCG_ID, name=UNIQUE_ALLY_NAME, life=2, strength=1
    )

    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:V1")
    actor.expect("action_choice", "recruit_fake_ally")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    minion_phase(game.state, "P1")

    recruited = next(iter(game.state.players["P1"].allies.values()))
    assert recruited.contested_with == existing.instance_id
    assert existing.contested_with == recruited.instance_id
    assert recruited.zone == "contested"
    assert existing.zone == "contested"
    actor.assert_exhausted()
