"""Effective capacity/disciplines with attachments folded in (OQ-8); attachment Contested
Cards (OQ-22, §4, mirrors `allies.py`). `CardAttachment` nests in host's list, controller
may differ (§2)."""

from collections.abc import Iterator
from typing import TYPE_CHECKING

from . import hooks
from .cards import CardAttachment
from .decision import Choice, Decision
from .pool import can_afford_without_ousting, lose_pool

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

CAPACITY_MODIFIER_HOOK = "capacity_modifier"
"""Passive numeric hook (`hooks.sum_modifiers`): an attachment's printed capacity bonus is
mandatory and always-on while in play (CLAUDE.md rule 3 exception), so no `Decision` is raised."""

DISCIPLINE_LEVEL_MODIFIER_HOOK = "discipline_level_modifier"
"""Passive, set-valued hook (`hooks.union_modifiers`): same mandatory-fact shape as
`CAPACITY_MODIFIER_HOOK`, but for a granted discipline-level code (e.g. `"cel"`/`"CEL"`)."""


def effective_capacity(state: GameState, vampire: VampireInPlay) -> int:
    """Printed capacity (Rulebook §1 Vampires) plus every attached card's own capacity bonus
    (OQ-8). Use instead of a bare `vampire.card.capacity` read."""
    return vampire.card.capacity + hooks.sum_modifiers(
        CAPACITY_MODIFIER_HOOK, state, vampire=vampire.instance_id
    )


def effective_disciplines(state: GameState, vampire: VampireInPlay) -> tuple[str, ...]:
    """Printed disciplines unioned with every level an attachment currently grants (OQ-8).
    Sorted tuple, not a `frozenset` (CLAUDE.md §5 determinism; see `hooks.union_modifiers`)."""
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
    """Yield every `(vampire, attachment)` pair in play across both players (OQ-22) -- a
    `CardAttachment` has no top-level dict of its own, unlike `PlayerState.vampires`/`.allies`."""
    for player_state in state.players.values():
        for vampire in player_state.vampires.values():
            for attachment in vampire.attachments:
                yield vampire, attachment


def find_attachment_by_instance_id(
    state: GameState, instance_id: str | None
) -> CardAttachment | None:
    """Locate a `CardAttachment` by `instance_id` across either player's vampires (OQ-22) --
    attachment-side analogue of `engine/allies.py::_find_ally_instance` (see `iter_attachments`)."""
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
    is_equipment: bool = False,
    requires_discipline: bool = False,
) -> CardAttachment:
    """Put a new, contest-trackable attachment onto `vampire` (OQ-22). `controller` is
    caller-supplied (§2), unchecked (OQ-22 addendum). Only for Unique cards; else
    construct `CardAttachment` directly. `is_equipment`/`requires_discipline` are the
    caller's own printed-card-type facts (see `CardAttachment.is_equipment`/
    `.requires_discipline`'s own docstrings), not inferred here."""
    attachment = CardAttachment(
        krcg_id=krcg_id,
        name=name,
        counters=counters,
        controller=controller,
        instance_id=state.players[controller].new_attachment_instance_id(),
        zone="attached",
        is_equipment=is_equipment,
        requires_discipline=requires_discipline,
    )
    vampire.attachments.append(attachment)
    return attachment


def detect_contest_on_attach(state: GameState, attachment: CardAttachment) -> None:
    """Flag `attachment` and a same-named opposing attachment as contested (§4, OQ-22;
    not 2P-overridden). Matched by `name` vs. its controller's opponent. Checked first
    (OQ-16, quoted verbatim in `engine/contests.py::detect_contest_on_reveal`):
    `attachment`'s own controller's other live same-named attachment burns the incoming
    copy immediately instead of contesting."""
    if attachment.controller is None:
        return
    for _vampire, mine in iter_attachments(state):
        if mine is attachment:
            continue
        if (
            mine.controller == attachment.controller
            and mine.zone == "attached"
            and mine.name == attachment.name
        ):
            attachment.zone = "burned"
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
    """Change controller, re-host `attachment` onto `new_host` (OQ-35; Disputed Territory
    rulings). Unchanged controller requires `new_host` be current host or `ValueError`;
    else caller-chosen, unverified."""
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
    """Rulebook §4 Unlock + Contested Cards (OQ-22): pay 1 pool to keep contesting, or yield
    (burn own copy). No 2P override: survivor's `zone` restores only on its next unlock phase."""
    # OQ-42: paying must not leave the payer at 0 pool; yielding stays.
    pay = (Choice("pay", "Pay 1 pool to keep contesting"),)
    choices = (
        *(pay if can_afford_without_ousting(state, player, 1) else ()),
        Choice("yield", "Yield: burn this card"),
    )
    decision = Decision(
        player=player,
        kind="attachment_contest_resolution",
        choices=choices,
        context={"attachment": attachment.instance_id, "contested_with": attachment.contested_with},
    )
    choice = state.ask_unless_forced(decision)
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
