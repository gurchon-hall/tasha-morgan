"""Attached-master-card contest *resolution* (ENG-014): once two same-named
unique attachments are flagged as contesting each other
(`engine/attachments.py::detect_contest_on_attach`), each controller must be
offered the rulebook's own pay-1-pool-or-yield decision during their own unlock
phases (Rulebook §4 Advanced Rules > Contested Cards), mirroring the ally
mechanism ENG-009 already proved
(`tests/rules/test_ally_contest_resolution.py`) -- except, as with an ally,
there is no 2P "stays usable" override, so the surviving copy's own `zone` only
flips back to `"attached"` on its controller's own *next* unlock phase, not
instantaneously with the opponent's yield (see
`engine/attachments.py::resolve_one_attachment_contest` and
`engine/phases/unlock.py::_unlock_own_attachments`).
"""

from helpers import ScenarioBuilder, ScenarioGame, ScriptedAgent
from vtesbot.engine.attachments import attach_card, detect_contest_on_attach
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.phases.unlock import unlock_phase

UNIQUE_ATTACHMENT_KRCG_ID = 100698  # Fame's own id, reused as a stand-in
UNIQUE_ATTACHMENT_NAME = "Fame"


def _contested_pair(game: ScenarioGame) -> tuple[CardAttachment, CardAttachment]:
    """Attach a same-named card for each player's own vampire and flag the
    contest, mirroring `tests/rules/test_attachment_contests.py`'s own
    setup pattern."""
    existing = attach_card(
        game.state,
        game.vampire("V2"),
        controller="P2",
        krcg_id=UNIQUE_ATTACHMENT_KRCG_ID,
        name=UNIQUE_ATTACHMENT_NAME,
    )
    incoming = attach_card(
        game.state,
        game.vampire("V1"),
        controller="P1",
        krcg_id=UNIQUE_ATTACHMENT_KRCG_ID,
        name=UNIQUE_ATTACHMENT_NAME,
    )
    detect_contest_on_attach(game.state, incoming)
    return incoming, existing


def _two_player_game(seed: int = 1) -> ScenarioGame:
    builder = ScenarioBuilder(seed=seed)
    builder.player("P1", pool=10).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=10).ready_vampire("V2", capacity=3)
    return builder.build()


def test_contested_attachments_controller_is_offered_pay_or_yield_during_unlock():
    game = _two_player_game()
    _contested_pair(game)
    agent = ScriptedAgent("P1").expect("attachment_contest_resolution", "pay")
    game.state.agents["P1"] = agent

    unlock_phase(game.state, "P1")

    assert game.state.players["P1"].pool == 9
    agent.assert_exhausted()


def test_paying_keeps_both_copies_contested_and_out_of_play():
    """Unlike the crypt-card case (2P override keeps `zone == "ready"`
    throughout), an attached master card has no such override: paying
    leaves it `zone == "contested"`, still out of play."""
    game = _two_player_game()
    mine, opponent = _contested_pair(game)
    game.state.agents["P1"] = ScriptedAgent("P1").expect("attachment_contest_resolution", "pay")

    unlock_phase(game.state, "P1")

    assert mine.zone == "contested"
    assert mine.contested_with == opponent.instance_id
    assert opponent.zone == "contested"
    assert opponent.contested_with == mine.instance_id


def test_yielding_burns_the_yielding_attachment_and_does_not_immediately_restore_the_opponent():
    game = _two_player_game()
    mine, opponent = _contested_pair(game)
    game.state.agents["P1"] = ScriptedAgent("P1").expect("attachment_contest_resolution", "yield")

    unlock_phase(game.state, "P1")

    assert mine.zone == "burned"
    assert mine.contested_with is None
    assert game.state.players["P1"].pool == 10  # yielding costs no pool
    # Not instantaneous with the yield: the rulebook's own wording is "...
    # during your next unlock phase, ending the contest" (a further event
    # tied to the surviving controller's own next unlock phase).
    assert opponent.contested_with is None
    assert opponent.zone == "contested"


def test_the_surviving_attachments_zone_is_only_restored_on_its_controllers_own_next_unlock_phase():
    game = _two_player_game()
    mine, opponent = _contested_pair(game)
    game.state.agents["P1"] = ScriptedAgent("P1").expect("attachment_contest_resolution", "yield")
    unlock_phase(game.state, "P1")
    assert opponent.zone == "contested"  # not yet restored

    agent_p2 = ScriptedAgent("P2")  # no pending effects expected for P2
    game.state.agents["P2"] = agent_p2

    unlock_phase(game.state, "P2")

    assert opponent.zone == "attached"
    assert opponent.contested_with is None
    agent_p2.assert_exhausted()


def test_zero_regression_an_uncontested_attachments_zone_is_left_untouched_by_unlock():
    game = _two_player_game()
    solo = attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=1, name="Solo Attachment"
    )
    game.state.agents["P1"] = ScriptedAgent("P1")  # no decisions expected

    unlock_phase(game.state, "P1")

    assert solo.zone == "attached"
    assert solo.contested_with is None


def test_an_attachments_controller_differing_from_its_vampires_controller_resolves_correctly():
    """Rulebook §2 Card Types: the contest is resolved during the
    *attachment's own controller's* unlock phase, not the vampire's -- here
    P1 plays the contested copy onto P2's own vampire."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=10).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=10).ready_vampire("V2", capacity=3)
    game = builder.build()
    on_p2s_vampire = attach_card(
        game.state,
        game.vampire("V2"),
        controller="P1",
        krcg_id=UNIQUE_ATTACHMENT_KRCG_ID,
        name=UNIQUE_ATTACHMENT_NAME,
    )
    on_p1s_own_vampire = attach_card(
        game.state,
        game.vampire("V1"),
        controller="P2",
        krcg_id=UNIQUE_ATTACHMENT_KRCG_ID,
        name=UNIQUE_ATTACHMENT_NAME,
    )
    detect_contest_on_attach(game.state, on_p1s_own_vampire)
    assert on_p2s_vampire.contested_with is not None

    # P2's own unlock phase must offer nothing for `on_p2s_vampire` (it is
    # controlled by P1), only for `on_p1s_own_vampire` (controlled by P2,
    # even though it sits on P1's own vampire).
    agent_p2 = ScriptedAgent("P2").expect("attachment_contest_resolution", "pay")
    game.state.agents["P2"] = agent_p2

    unlock_phase(game.state, "P2")

    assert game.state.players["P2"].pool == 9
    agent_p2.assert_exhausted()
