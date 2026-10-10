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
"""

from typing import TYPE_CHECKING

from . import hooks

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
