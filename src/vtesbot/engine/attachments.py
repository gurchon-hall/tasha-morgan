"""Effective capacity / effective discipline levels: attachments folded in.

Source: `engine/cards.py::CardAttachment` ("a discipline/archetype master
card (Celerity, Fame, Perfectionist), a piece of combat equipment ..., or a
retainer. The engine only needs to track *that* a card is attached and to
whom ... so it can be found, destroyed, or referenced by a hook; what the
attachment *does* is card-specific behaviour registered against a hook by
its `src/vtesbot/cards/` module, never special-cased here") and
`engine/state.py::VampireInPlay.attachments`.

`docs/OPEN_QUESTIONS.md` OQ-8 identified the missing piece: every place
that reads a vampire's capacity or discipline levels
(`engine/damage.py::add_blood`, `engine/phases/influence.py`'s two capacity
checks, `engine/observation.py`) read `vampire.card.capacity` /
`vampire.card.disciplines` directly, never consulting
`VampireInPlay.attachments` at all -- so an attached card's own printed
numeric/discipline bonus (e.g. Celerity's "+1 level of Celerity [cel] and +1
capacity") had no effect anywhere, which is a silent mis-resolution
(CLAUDE.md "never mis-resolves a card").

`vampire.card` (`engine/cards.py::CryptCard`) is documented as "deck-
construction identity only" and stays frozen and untouched (CLAUDE.md "do
not hack around a missing engine mechanism inside the card module" -- the
fix belongs here, in `engine/`, not in a card module faking the bonus by
mutating identity data). What any given attachment actually grants is
still card-specific behaviour (CLAUDE.md SS6): it is exposed as two more
passive, mandatory hook points (mirroring every other hook in
`engine/hooks.py`), so a `src/vtesbot/cards/` module recognizes its own
`krcg_id` among `vampire.attachments` and contributes the bonus its own
printed text grants; the engine itself only folds in whatever is offered,
never special-casing a card name.

OQ-22 (`docs/OPEN_QUESTIONS.md`, resolved by this pass, found implementing
Fame, 100698): a card attachment printed "Unique" (e.g. Fame) is subject to
the same generalized Contested Cards mechanism OQ-8/OQ-10/OQ-15 already
built for a `VampireInPlay`/`AllyInPlay` -- Rulebook SS4 Advanced Rules >
Contested Cards (quoted in full in `engine/contests.py`'s and
`engine/allies.py`'s own module docstrings): "If more than one unique card
with the same name is brought into play, that means control of the card is
being contested. For the duration of the contest, all of the contested
cards are turned face down and are out of play ... The cost to contest a
card is 1 pool, which you pay during each of your unlock phases. Instead of
paying the cost ... you may choose to yield the card ... [a yielded card]
is burned ... If all other cards contesting your unique card are yielded,
then the card is unlocked and turned face up during your next unlock
phase, ending the contest." The 2P variant's "Contested crypt cards"
override (stay in play, usable, no face-down) is scoped to crypt cards only
(OQ-10's own re-confirmation, cross-checked again here against
`data/sources/2p-variant/2026-10-09/variant.md`'s own title and its own
"(Note: this means that contested crypt cards are no longer out of play)"
aside) -- so a Unique attached master card follows the *unmodified* base
rule, exactly like an ally (not a new reading, a third application of the
same already-settled one).

`attach_card`/`detect_contest_on_attach`/`resolve_one_attachment_contest`
below mirror `engine/allies.py::recruit_ally`/`detect_contest_on_recruit`/
`resolve_one_ally_contest` deliberately closely, including the one wrinkle
OQ-15 already identified for an ally and which applies identically here:
because there is no 2P "stays usable" override for this card type either,
`CardAttachment.zone` must actually flip between `"attached"` and
`"contested"` (unlike a contested crypt card, which never leaves `"ready"`),
and the surviving copy's own zone is restored to `"attached"` only on its
*own controller's* next unlock phase (`engine/phases/unlock.py::
_unlock_own_attachments`, mirroring `_unlock_own_allies`), not
instantaneously with the opponent's yield.

One deliberate new wrinkle not present on the vampire/ally side: a
`CardAttachment` is not keyed in its own top-level `PlayerState` dict (it
lives nested inside whichever vampire's own `attachments` list it was put
on), and for a *Master*-type attachment such as Celerity/Fame (both target
"a vampire", not "a vampire you control"), its `controller` -- the
Methuselah who *played* it, Rulebook SS2 Card Types, "Master Cards" -- can
differ from that vampire's own controller. This is a Master-card-specific
rule, not a general property of every `CardAttachment`: an Equipment or
Retainer-type attachment is controlled by its host vampire's own
controller instead (same page, "Minion Cards" subsection) -- see
`attach_card`'s own docstring and `docs/OPEN_QUESTIONS.md` OQ-22's
2026-10-11 addendum for the caller's responsibility there.
`iter_attachments`/`find_attachment_by_instance_id` below are what let
`engine/phases/unlock.py` locate a specific player's own contested
attachments, and a specific attachment by id, across *either* player's
vampires.

Deliberately **not** built here (CLAUDE.md "one rule mechanism per
change"; no card module needs it yet -- same boundary OQ-15 itself drew for
Shilmulo Tarot on this exact `CardAttachment` side): any Observation-level
visibility for an attachment at all (`engine/observation.py`'s
`VampireView` has no `attachments` field today, contested or not -- a
pre-existing gap, not introduced or widened by this pass) -- Fame itself
stays `blocked`/OQ-22 in the registry regardless of this pass, and no other
card in the pool needs an attachment visible in `Observation` yet.
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

    Source: Rulebook SS4 Advanced Rules > Contested Cards (quoted in full in
    this module's own docstring and in `docs/OPEN_QUESTIONS.md` OQ-22): "If
    more than one unique card with the same name is brought into play, that
    means control of the card is being contested. For the duration of the
    contest, all of the contested cards are turned face down and are out of
    play." Not overridden by the 2P variant for an attached master card
    (that override is scoped to crypt cards only -- see this module's own
    docstring); matched by printed `name`, exactly like
    `engine/contests.py::detect_contest_on_reveal`/`engine/allies.py::
    detect_contest_on_recruit`'s own "same name, not same krcg id" test.

    Checked against every attachment currently in play across *either*
    player's vampires (`iter_attachments`), because the attachment's own
    `controller` -- not the vampire it sits on -- is who it may contest
    against; only the opponent of `attachment.controller`'s own copies are
    checked, mirroring `detect_contest_on_reveal`/`detect_contest_on_recruit`'s
    identical "only ever checks the opponent" scope boundary (OQ-16 tracks
    the rulebook's own "cannot contest yourself" DECK CONSTRUCTION caution
    box as an equally-unimplemented gap on all three paths alike -- not a
    new gap introduced here).
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


def resolve_one_attachment_contest(
    state: GameState, player: str, attachment: CardAttachment
) -> None:
    """Rulebook SS4 Unlock Phase + Advanced Rules > Contested Cards (OQ-22):
    pay 1 pool to keep contesting `attachment` this unlock phase, or yield
    (burn your own copy).

    Mirrors `engine/allies.py::resolve_one_ally_contest`'s own two branches
    exactly, for the same reason that function itself gave for diverging
    from the crypt-card case (`engine/contests.py::resolve_one_contest`):
    there is no 2P "stays in play and usable" override for this card type
    either (that override is scoped to crypt cards only), so "paying" here
    correctly leaves `attachment.zone == "contested"` (still out of play)
    rather than restoring it.

    The "yield" branch burns the yielding attachment (`zone = "burned"`) and
    clears the opponent's own `contested_with` immediately -- but, unlike
    the crypt-card case, does *not* also restore the opponent's `zone` to
    `"attached"` here: the rulebook's own wording is "the card is unlocked
    and turned face up during your next unlock phase, ending the contest" --
    a further, later event tied to the *surviving controller's own* next
    unlock phase, not the yielding player's current one. The surviving
    attachment's own `zone` flip back to `"attached"` is handled by
    `engine/phases/unlock.py::_unlock_own_attachments`, run as part of its
    controller's own (later) `unlock_phase` call, exactly where the rulebook
    situates it -- mirroring `resolve_one_ally_contest`/
    `_unlock_own_allies`'s identical split.
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
