"""Contested unique attached master cards (OQ-22, `docs/OPEN_QUESTIONS.md`,
found implementing Fame, 100698): a `CardAttachment` printed "Unique" can
collide with a same-named opposing attachment, exactly like the crypt-card
(`engine/contests.py`) and ally (`engine/allies.py`, OQ-10) cases -- except
there is no 2P "stays in play and usable" override for this card type
either, so an attachment contest follows the *unmodified* Rulebook §4
Advanced Rules > Contested Cards rule: both copies are "turned face down
and are out of play" for the contest's duration
(`engine/attachments.py::detect_contest_on_attach`).

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*; Fame itself stays `blocked`/OQ-22 and is not touched here
(`card-implementer`'s job once this capability exists).
"""

from helpers import ScenarioBuilder
from vtesbot.engine.attachments import attach_card, detect_contest_on_attach

UNIQUE_ATTACHMENT_KRCG_ID = 100698  # Fame's own id, reused as a stand-in
UNIQUE_ATTACHMENT_NAME = "Fame"


def test_detect_contest_on_attach_flags_both_same_named_attachments():
    """Rulebook §4 Advanced Rules > Contested Cards: "If more than one
    unique card with the same name is brought into play, that means control
    of the card is being contested." Both copies get `contested_with` set
    to each other, mirroring `engine/allies.py::detect_contest_on_recruit`'s
    own two-sided flagging."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("V2", capacity=3)
    game = builder.build()
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

    assert incoming.contested_with == existing.instance_id
    assert existing.contested_with == incoming.instance_id


def test_detect_contest_on_attach_turns_both_copies_out_of_play():
    """Unlike the 2P crypt-card override ("stays in play and usable"), the
    unmodified rulebook rule applies here too: "all of the contested cards
    are turned face down and are out of play" -- both copies' `zone` moves
    off `"attached"` to `"contested"`, not just the incoming one."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("V2", capacity=3)
    game = builder.build()
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

    assert incoming.zone == "contested"
    assert existing.zone == "contested"


def test_differently_named_attachments_are_not_contested():
    """ "Only when needed": two attachments with different printed names
    never collide, no matter who played or holds them."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("V2", capacity=3)
    game = builder.build()
    other = attach_card(
        game.state, game.vampire("V2"), controller="P2", krcg_id=1, name="Attachment One"
    )
    mine = attach_card(
        game.state, game.vampire("V1"), controller="P1", krcg_id=2, name="Attachment Two"
    )

    detect_contest_on_attach(game.state, mine)

    assert mine.contested_with is None
    assert other.contested_with is None
    assert mine.zone == "attached"
    assert other.zone == "attached"


def test_a_players_own_two_attachments_of_the_same_name_burn_the_incoming_copy():
    """OQ-16 (resolved), rulebook caution box quoted verbatim in
    `engine/contests.py::detect_contest_on_reveal`: "you cannot voluntarily
    contest cards with yourself (if some effect would force you to contest a
    card with yourself, then you simply burn the incoming copy of the unique
    card)." `detect_contest_on_attach` checks the attachment's own
    controller's other live same-named attachment first: the incoming
    (second) copy is burned immediately, the first stays untouched, and no
    contest is created."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3).ready_vampire("V1b", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    first = attach_card(
        game.state,
        game.vampire("V1"),
        controller="P1",
        krcg_id=UNIQUE_ATTACHMENT_KRCG_ID,
        name=UNIQUE_ATTACHMENT_NAME,
    )
    second = attach_card(
        game.state,
        game.vampire("V1b"),
        controller="P1",
        krcg_id=UNIQUE_ATTACHMENT_KRCG_ID,
        name=UNIQUE_ATTACHMENT_NAME,
    )

    detect_contest_on_attach(game.state, second)

    assert first.contested_with is None
    assert first.zone == "attached"
    assert second.contested_with is None
    assert second.zone == "burned"


def test_an_attachments_controller_may_differ_from_the_vampires_own_controller():
    """Rulebook §2 Card Types: "A master card in play is controlled by the
    Methuselah who played it, even if it is played on a card controlled by
    another Methuselah." The contest is tracked against the attachment's
    own `controller`, not the vampire it sits on -- here P1 plays both
    copies, one onto their own vampire and one onto P2's vampire, so the
    contest's "opponent" check must still key off `attachment.controller`
    (P1 for both) rather than `vampire.controller`."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("V2", capacity=3)
    game = builder.build()
    on_own_vampire = attach_card(
        game.state,
        game.vampire("V1"),
        controller="P1",
        krcg_id=UNIQUE_ATTACHMENT_KRCG_ID,
        name=UNIQUE_ATTACHMENT_NAME,
    )
    on_opponents_vampire = attach_card(
        game.state,
        game.vampire("V2"),
        controller="P2",
        krcg_id=UNIQUE_ATTACHMENT_KRCG_ID,
        name=UNIQUE_ATTACHMENT_NAME,
    )

    detect_contest_on_attach(game.state, on_opponents_vampire)

    assert on_opponents_vampire.contested_with == on_own_vampire.instance_id
    assert on_own_vampire.contested_with == on_opponents_vampire.instance_id
    assert on_opponents_vampire.zone == "contested"
    assert on_own_vampire.zone == "contested"
