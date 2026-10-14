"""Effective capacity / effective discipline levels: attachments folded in.

Source: `engine/cards.py::CardAttachment` and
`engine/state.py::VampireInPlay.attachments`.

OQ-8 (`docs/OPEN_QUESTIONS.md`): every call site that reads a vampire's
capacity or discipline levels (`engine/damage.py::add_blood`, `engine/
phases/influence.py`'s capacity checks, `engine/observation.py`) read
`vampire.card.capacity`/`.disciplines` directly, ignoring `VampireInPlay.
attachments` -- so an attachment's printed bonus (e.g. Celerity's "+1 level
of Celerity [cel] and +1 capacity") had no effect anywhere. `vampire.card`
stays frozen, deck-construction identity only; the bonus is exposed instead
as two passive, mandatory hook points below (`CAPACITY_MODIFIER_HOOK`,
`DISCIPLINE_LEVEL_MODIFIER_HOOK`) that a card module registers against, and
the engine folds in whatever is offered without special-casing a card name
(CLAUDE.md SS6).

OQ-22 (`docs/OPEN_QUESTIONS.md`, resolved, found implementing Fame,
100698): a card attachment printed "Unique" (e.g. Fame) is subject to the
same Contested Cards mechanism (Rulebook SS4 Advanced Rules, quoted in full
in `engine/contests.py`'s and `engine/allies.py`'s own module docstrings)
already built for a `VampireInPlay`/`AllyInPlay`. The 2P variant's
"Contested crypt cards" override is scoped to crypt cards only (re-
confirmed against `data/sources/2p-variant/2026-10-09/variant.md`), so a
Unique attached master card follows the unmodified base rule, like an ally.

`attach_card`/`detect_contest_on_attach`/`resolve_one_attachment_contest`
below mirror `engine/allies.py::recruit_ally`/`detect_contest_on_recruit`/
`resolve_one_ally_contest`, including the same OQ-15 wrinkle: with no 2P
"stays usable" override for this card type, `CardAttachment.zone` flips
between `"attached"` and `"contested"`, and the surviving copy restores to
`"attached"` only on its own controller's next unlock phase (`engine/
phases/unlock.py::_unlock_own_attachments`).

One wrinkle not present on the vampire/ally side: a `CardAttachment` is not
keyed in its own `PlayerState` dict (it lives nested inside its host
vampire's `attachments` list), and for a Master-type attachment such as
Celerity/Fame its `controller` -- the Methuselah who *played* it (Rulebook
SS2 Card Types, "Master Cards") -- can differ from that vampire's own
controller; an Equipment/Retainer attachment is controlled by its host's
controller instead ("Minion Cards", same page). See `attach_card`'s own
docstring and `CardAttachment`'s own docstring (`engine/cards.py`) for the
caller's responsibility there. `iter_attachments`/
`find_attachment_by_instance_id` below let `engine/phases/unlock.py` locate
a player's contested attachments, and a specific attachment by id, across
either player's vampires.

Deliberately not built here (no card needs it yet): any Observation-level
visibility for an attachment (`VampireView` has no `attachments` field) --
Fame stays `blocked`/OQ-22 in the registry regardless.
"""

from collections.abc import Iterator
from typing import TYPE_CHECKING

from . import hooks
from .cards import CardAttachment
from .decision import Choice, Decision
from .pool import lose_pool

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

CAPACITY_MODIFIER_HOOK = "capacity_modifier"
"""Passive numeric hook (`hooks.sum_modifiers` contract): an attached card's
own printed capacity bonus (e.g. Celerity's "+1 capacity") is not something
its controller chooses to apply or withhold turn to turn -- it is simply
true for as long as the attachment is in play (CLAUDE.md rule 3's
"mandatory effects" exception), so no `Decision` is raised for it."""

DISCIPLINE_LEVEL_MODIFIER_HOOK = "discipline_level_modifier"
"""Passive, set-valued hook (`hooks.union_modifiers` contract): an attached
card's own printed discipline-level grant (e.g. Celerity's "+1 level of
Celerity [cel]") is the same kind of mandatory, always-true fact as the
capacity bonus above, but set-valued (a discipline-level code such as
`"cel"`/`"CEL"`) rather than a scalar quantity."""


def effective_capacity(state: GameState, vampire: VampireInPlay) -> int:
    """Printed capacity (Rulebook SS1 Vampires) plus every attached card's
    own numeric capacity bonus currently in play on `vampire`.

    Replaces a bare `vampire.card.capacity` read at any call site that must
    reflect attachments (OQ-8): `engine/damage.py::add_blood`,
    `engine/phases/influence.py`'s capacity checks, `engine/observation.py`.
    """
    return vampire.card.capacity + hooks.sum_modifiers(
        CAPACITY_MODIFIER_HOOK, state, vampire=vampire.instance_id
    )


def effective_disciplines(state: GameState, vampire: VampireInPlay) -> tuple[str, ...]:
    """Printed disciplines (`vampire.card.disciplines`) unioned with every
    discipline level an attached card's own text currently grants `vampire`.

    Uses krcg's own basic/superior convention (lowercase = basic, uppercase
    = superior -- `engine/cards.py::CryptCard.disciplines` docstring),
    exactly like the printed field it extends.

    Returns a *sorted tuple*, not a `frozenset` (rules-auditor finding,
    CLAUDE.md SS5 determinism) -- see `hooks.union_modifiers`'s own
    docstring, whose return type this wraps and must match for the same
    reason.
    """
    return tuple(
        sorted(
            set(vampire.card.disciplines)
            | set(
                hooks.union_modifiers(
                    DISCIPLINE_LEVEL_MODIFIER_HOOK, state, vampire=vampire.instance_id
                )
            )
        )
    )


def iter_attachments(state: GameState) -> Iterator[tuple[VampireInPlay, CardAttachment]]:
    """Yield every `(vampire, attachment)` pair currently in play, across
    *both* players' vampires (OQ-22).

    Needed because, unlike `PlayerState.vampires`/`.allies`, a
    `CardAttachment` has no top-level dict of its own -- it is nested inside
    whichever vampire's own `attachments` list it was put on, and that
    vampire's controller may differ from the attachment's own `controller`
    (Rulebook SS2 Card Types). `detect_contest_on_attach`,
    `find_attachment_by_instance_id`, and `engine/phases/unlock.py`'s own
    pending-effect gathering/`_unlock_own_attachments` all scan via this.
    """
    for player_state in state.players.values():
        for vampire in player_state.vampires.values():
            for attachment in vampire.attachments:
                yield vampire, attachment


def find_attachment_by_instance_id(
    state: GameState, instance_id: str | None
) -> CardAttachment | None:
    """Locate a `CardAttachment` by its `instance_id` across either player's
    vampires (OQ-22) -- the attachment-side analogue of `engine/contests.py::
    _find_instance` / `engine/allies.py::_find_ally_instance`, needed because
    an attachment has no flat `PlayerState` dict of its own to index into
    directly (see `iter_attachments`)."""
    if instance_id is None:
        return None
    for _vampire, attachment in iter_attachments(state):
        if attachment.instance_id == instance_id:
            return attachment
    return None


def attach_card(
    state: GameState,
    vampire: VampireInPlay,
    *,
    controller: str,
    krcg_id: int,
    name: str,
    counters: int | None = None,
) -> CardAttachment:
    """Put a new card attachment onto `vampire`, minting it a contest-
    trackable identity (OQ-22, `docs/OPEN_QUESTIONS.md`) -- the attachment-
    side analogue of `engine/allies.py::recruit_ally`.

    `controller` is caller-supplied and stored as-is -- this function does
    not derive it from the attachment's own printed card type, and callers
    must not assume a single rule covers every attachment. For a
    Master-type attachment such as Fame, pass the Methuselah who *played*
    the card (Rulebook SS2 Card Types, "Master Cards": "A master card in
    play is controlled by the Methuselah who played it, even if it is
    played on a card controlled by another Methuselah"), which may differ
    from `vampire.controller`; that is the only case this function has a
    real caller for today. For an Equipment or Retainer-type attachment,
    the same rulebook page's "Minion Cards" subsection states the opposite
    rule: "A minion card in play is controlled by the controller of the
    minion it is on." -- callers attaching that category (e.g. a future
    Shilmulo Tarot, krcg id 101767, OQ-10) must pass `vampire.controller`
    instead, not whoever played the card; this function will not catch a
    caller that gets this wrong (`docs/OPEN_QUESTIONS.md` OQ-22's
    2026-10-11 addendum). Whatever value is passed is what
    `detect_contest_on_attach`/`resolve_one_attachment_contest`/
    `engine/phases/unlock.py` track a contest and pay/yield against, exactly
    like `AllyInPlay.controller`'s own role for `recruit_ally`.

    Not a mandatory call site for every attachment: a non-unique card such
    as Celerity (100312) can never be contested in the first place (Rulebook
    SS4 Advanced Rules > Contested Cards only ever applies to a card printed
    "Unique") and may keep constructing `CardAttachment` directly, exactly
    as `src/vtesbot/cards/celerity.py::_apply` already does -- this entry
    point exists for a future card module (none built yet; Fame, 100698,
    stays `blocked`/OQ-22 regardless of this pass) whose own printed text is
    "Unique" and therefore needs `controller`/`contested_with`/`zone`
    tracked from the moment it is attached.
    """
    attachment = CardAttachment(
        krcg_id=krcg_id,
        name=name,
        counters=counters,
        controller=controller,
        instance_id=state.players[controller].new_attachment_instance_id(),
        zone="attached",
    )
    vampire.attachments.append(attachment)
    return attachment


def detect_contest_on_attach(state: GameState, attachment: CardAttachment) -> None:
    """Flag `attachment` and any same-named in-play opposing attachment as
    contested, and move both out of the usable `"attached"` zone for the
    contest's duration (OQ-22).

    Source: Rulebook SS4 Advanced Rules > Contested Cards (OQ-22, `docs/
    OPEN_QUESTIONS.md`; full quote in this module's and `engine/allies.py`'s
    own module docstrings). Not overridden by the 2P variant for an attached
    master card (that override is scoped to crypt cards only); matched by
    printed `name`, exactly like `engine/contests.py::detect_contest_on_
    reveal`/`engine/allies.py::detect_contest_on_recruit`'s "same name, not
    same krcg id" test.

    Checked against every attachment currently in play across *either*
    player's vampires (`iter_attachments`), because the attachment's own
    `controller` -- not the vampire it sits on -- is who it may contest
    against; only the opponent of `attachment.controller`'s own copies are
    checked (OQ-16 tracks the rulebook's own "cannot contest yourself" edge
    case as an equally-unimplemented gap on all three paths alike).
    """
    if attachment.controller is None:
        return
    opponent = state.other_player(attachment.controller)
    for _vampire, other in iter_attachments(state):
        if other is attachment:
            continue
        if (
            other.controller == opponent
            and other.zone == "attached"
            and other.name == attachment.name
        ):
            attachment.contested_with = other.instance_id
            other.contested_with = attachment.instance_id
            attachment.zone = "contested"
            other.zone = "contested"
            return


def transfer_attachment_control(
    state: GameState,
    attachment: CardAttachment,
    *,
    new_controller: str,
    new_host: VampireInPlay,
) -> None:
    """Change who controls `attachment` and re-host it onto `new_host`
    (OQ-35, `docs/OPEN_QUESTIONS.md`; Disputed Territory, krcg id 100557,
    "Successful referendum means the chosen Methuselah takes control of the
    chosen location").

    Source, verbatim via the installed `krcg` package (Disputed Territory's
    own rulings): "If used to steal an equipment representing a location,
    it can be placed on any minion controlled by the new controller."
    [RTR 19960112]; "Changing the controller of a location has no other
    effect, unless specified by card text. Exception: A location 'on'
    another controlled card is moved onto an appropriate card controlled by
    the new controller of the location." [RTR 19980623] -- an attached
    card is, by definition, "on" a vampire, so the Exception clause always
    applies to this shape (contrast `engine/master_cards.py::
    transfer_master_card_control`, which is never "on" anything and so
    never re-hosts). A third ruling gates this specifically when
    `new_controller` is not actually a *different* Methuselah: "If used to
    'change' the control of a location or equipment representing a
    location to the same Methuselah, the location cannot be moved to
    another minion controlled by the same Methuselah." [LSJ 19971002] --
    `rules-auditor` finding (first landing of this entry omitted this
    clause entirely, letting a same-controller call silently relocate the
    attachment to any `new_host` with no check at all). Enforced below:
    when `new_controller == attachment.controller`, the only legal
    `new_host` is the attachment's own *current* host (a true no-op, since
    there is no actual controller change to carry out); any other
    `new_host` raises `ValueError` rather than silently relocating it.

    `new_host` is caller-supplied, not chosen here: *which* of the new
    controller's own minions receives it ("any minion controlled by the new
    controller") is a `Decision` specific to whichever card drives the
    control change (e.g. a future `cards/disputed_territory.py` raising it
    once the referendum passes) -- this function only performs the
    mechanical re-host + re-assign once a destination is already chosen,
    mirroring `attach_card`'s own "caller supplies `controller`" contract.
    `new_controller` need not equal `new_host.controller`'s caller-intended
    value by construction -- callers are responsible for only ever passing
    a `new_host` actually controlled by `new_controller` (not enforced
    here, the same trust boundary `attach_card`'s own docstring already
    places on its caller).
    """
    current_host: VampireInPlay | None = None
    for host, existing in iter_attachments(state):
        if existing is attachment:
            current_host = host
            break
    if new_controller == attachment.controller:
        if new_host is not current_host:
            raise ValueError(
                "transfer_attachment_control: the controller is not actually "
                "changing -- cannot move a location to a different minion "
                "controlled by the same Methuselah [LSJ 19971002]"
            )
        return  # no-op: same controller, same host -- nothing to carry out.
    if current_host is not None:
        current_host.attachments.remove(attachment)
    new_host.attachments.append(attachment)
    attachment.controller = new_controller


def resolve_one_attachment_contest(
    state: GameState, player: str, attachment: CardAttachment
) -> None:
    """Rulebook SS4 Unlock Phase + Advanced Rules > Contested Cards (OQ-22):
    pay 1 pool to keep contesting `attachment` this unlock phase, or yield
    (burn your own copy).

    Mirrors `engine/allies.py::resolve_one_ally_contest`'s own two branches
    exactly, for the same reason given there: no 2P "stays in play and
    usable" override for this card type, so "paying" leaves
    `attachment.zone == "contested"` rather than restoring it, and "yield"
    burns this copy while the surviving copy's own `zone` restores to
    `"attached"` only on its controller's own next unlock phase
    (`engine/phases/unlock.py::_unlock_own_attachments`), not
    instantaneously.
    """
    choices = (
        Choice("pay", "Pay 1 pool to keep contesting"),
        Choice("yield", "Yield: burn this card"),
    )
    decision = Decision(
        player=player,
        kind="attachment_contest_resolution",
        choices=choices,
        context={"attachment": attachment.instance_id, "contested_with": attachment.contested_with},
    )
    choice = state.ask(decision)
    if choice.value == "pay":
        lose_pool(state, player, 1)
    else:
        opponent_attachment = find_attachment_by_instance_id(state, attachment.contested_with)
        attachment.zone = "burned"
        if opponent_attachment is not None:
            # Cleared immediately (nothing contests the opponent's copy any
            # more), but its `zone` deliberately stays "contested" here --
            # see this function's own docstring and `_unlock_own_attachments`.
            opponent_attachment.contested_with = None
        attachment.contested_with = None
