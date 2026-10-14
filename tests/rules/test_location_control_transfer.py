"""Generic "change control of a location" primitives (OQ-35, `docs/
OPEN_QUESTIONS.md`): `engine/attachments.py::transfer_attachment_control`
and `engine/master_cards.py::transfer_master_card_control` -- Disputed
Territory (krcg id 100557, "Successful referendum means the chosen
Methuselah takes control of the chosen location") needs exactly these two
primitives, over the two existing shapes a "location" can take (OQ-23
already found "location" is free text on an ordinary standalone Master
card or an attached Equipment, not a distinct krcg type).

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*; Disputed Territory's own card module stays `blocked`/OQ-6 and
is not touched here (`card-implementer`'s job once this capability exists).
"""

import pytest

from helpers import ScenarioBuilder
from vtesbot.engine.attachments import attach_card, transfer_attachment_control
from vtesbot.engine.master_cards import bring_master_card_into_play, transfer_master_card_control

LOCATION_KRCG_ID = 100557  # Disputed Territory's own id, reused as a stand-in label


# --- transfer_attachment_control ("on another controlled card") -------------


def test_transfer_attachment_control_reassigns_the_controller():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("V2", capacity=3)
    game = builder.build()
    v1 = game.vampire("V1")
    v2 = game.vampire("V2")
    location = attach_card(game.state, v1, controller="P1", krcg_id=1, name="Some Location")

    transfer_attachment_control(game.state, location, new_controller="P2", new_host=v2)

    assert location.controller == "P2"


def test_transfer_attachment_control_moves_the_card_off_its_old_host():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("V2", capacity=3)
    game = builder.build()
    v1 = game.vampire("V1")
    v2 = game.vampire("V2")
    location = attach_card(game.state, v1, controller="P1", krcg_id=1, name="Some Location")

    transfer_attachment_control(game.state, location, new_controller="P2", new_host=v2)

    assert location not in v1.attachments


def test_transfer_attachment_control_moves_the_card_onto_the_new_host():
    """Rulings on file via krcg (Disputed Territory, quoted in full in the
    function's own docstring): "it can be placed on any minion controlled
    by the new controller" / "A location 'on' another controlled card is
    moved onto an appropriate card controlled by the new controller of the
    location" -- an attached card is always "on" a vampire, so re-hosting
    is mandatory, not optional, for this shape."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("V2", capacity=3)
    game = builder.build()
    v1 = game.vampire("V1")
    v2 = game.vampire("V2")
    location = attach_card(game.state, v1, controller="P1", krcg_id=1, name="Some Location")

    transfer_attachment_control(game.state, location, new_controller="P2", new_host=v2)

    assert location in v2.attachments


def test_transfer_attachment_control_rejects_relocating_to_another_minion_of_the_same_controller():
    """Ruling on file via krcg, verbatim: "If used to 'change' the control
    of a location or equipment representing a location to the same
    Methuselah, the location cannot be moved to another minion controlled
    by the same Methuselah." [LSJ 19971002] -- `new_controller` equal to
    the attachment's own current controller, with a `new_host` that is not
    its *current* host, must be rejected outright, not silently relocated
    (the bug `rules-auditor` found in this function's first landing)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3).ready_vampire("V1b", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    v1 = game.vampire("V1")
    v1b = game.vampire("V1b")
    location = attach_card(game.state, v1, controller="P1", krcg_id=1, name="Some Location")

    with pytest.raises(ValueError, match="LSJ 19971002"):
        transfer_attachment_control(game.state, location, new_controller="P1", new_host=v1b)

    # Rejected before any mutation: the location is untouched.
    assert location.controller == "P1"
    assert location in v1.attachments
    assert location not in v1b.attachments


def test_transfer_attachment_control_to_the_same_host_under_the_same_controller_is_a_no_op():
    """The one legal same-controller case per the ruling above: `new_host`
    *is* the attachment's own current host, i.e. no actual move at all."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    v1 = game.vampire("V1")
    location = attach_card(game.state, v1, controller="P1", krcg_id=1, name="Some Location")

    transfer_attachment_control(game.state, location, new_controller="P1", new_host=v1)

    assert location.controller == "P1"
    assert location in v1.attachments


def test_transfer_attachment_control_still_re_hosts_freely_on_a_genuine_controller_change():
    """Contrast the rejection above: when `new_controller` is genuinely
    different from the attachment's current controller, it may be
    re-hosted onto any of the new controller's own minions (the ruling's
    restriction is specific to a same-Methuselah "change")."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("V2", capacity=3).ready_vampire("V2b", capacity=3)
    game = builder.build()
    v1 = game.vampire("V1")
    v2b = game.vampire("V2b")
    location = attach_card(game.state, v1, controller="P1", krcg_id=1, name="Some Location")

    transfer_attachment_control(game.state, location, new_controller="P2", new_host=v2b)

    assert location.controller == "P2"
    assert location not in v1.attachments
    assert location in v2b.attachments


def test_transfer_attachment_control_does_not_disturb_an_unrelated_attachment():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30).ready_vampire("V2", capacity=3)
    game = builder.build()
    v1 = game.vampire("V1")
    v2 = game.vampire("V2")
    location = attach_card(game.state, v1, controller="P1", krcg_id=1, name="Some Location")
    unrelated = attach_card(game.state, v1, controller="P1", krcg_id=2, name="Unrelated")

    transfer_attachment_control(game.state, location, new_controller="P2", new_host=v2)

    assert unrelated in v1.attachments
    assert unrelated.controller == "P1"


# --- transfer_master_card_control (never "on" anything) ----------------------


def test_transfer_master_card_control_reassigns_the_controller():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    card = bring_master_card_into_play(game.state, "P1", krcg_id=LOCATION_KRCG_ID, name="Oxford")

    transfer_master_card_control(game.state, card, "P2")

    assert card.controller == "P2"


def test_transfer_master_card_control_moves_the_dict_entry_to_the_new_controller():
    """Every reader of `PlayerState.master_cards` (contest detection, the
    unlock phase's own per-player loops) indexes by controller -- leaving
    `card` keyed under its old controller while only reassigning
    `.controller` would make it invisible to its own new controller's
    unlock phase."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    card = bring_master_card_into_play(game.state, "P1", krcg_id=LOCATION_KRCG_ID, name="Oxford")

    transfer_master_card_control(game.state, card, "P2")

    assert card.instance_id not in game.state.players["P1"].master_cards
    assert game.state.players["P2"].master_cards[card.instance_id] is card


def test_transfer_master_card_control_never_re_hosts_onto_a_vampire():
    """Contrast `transfer_attachment_control`: a standalone card is never
    "on" another controlled card, so the Exception clause ("A location 'on'
    another controlled card is moved...") never applies here -- only the
    controller/ownership-dict bookkeeping changes."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30).ready_vampire("V2", capacity=3)
    game = builder.build()
    card = bring_master_card_into_play(game.state, "P1", krcg_id=LOCATION_KRCG_ID, name="Oxford")

    transfer_master_card_control(game.state, card, "P2")

    assert game.vampire("V2").attachments == []


def test_transfer_master_card_control_does_not_disturb_an_unrelated_card():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30)
    builder.player("P2", pool=30)
    game = builder.build()
    card = bring_master_card_into_play(game.state, "P1", krcg_id=LOCATION_KRCG_ID, name="Oxford")
    unrelated = bring_master_card_into_play(game.state, "P1", krcg_id=1, name="Unrelated")

    transfer_master_card_control(game.state, card, "P2")

    assert unrelated.controller == "P1"
    assert unrelated.instance_id in game.state.players["P1"].master_cards
