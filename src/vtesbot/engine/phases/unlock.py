"""Unlock phase.

Source: Rulebook SS4 Unlock Phase (per the `vtes-rules-reference` skill
condensed mapping): "unlock all your cards, then unlock-phase effects in the
order you choose; Edge holder may gain 1 pool. Contests paid here (1 pool
per contested card ...)." The order of the player's own optional unlock-
phase effects (each contested crypt card's pay/yield, each contested ally's
pay/yield, and the optional Edge pool gain) is the acting player's choice --
this is the impulse/sequencing model (CLAUDE.md SS4 / Rulebook SS2
Sequencing) applied to the Unlock phase: the player picks which of several
available effects to resolve next, one at a time, until none remain. When
only one effect is available there is nothing to "choose the order" of, so
no vacuous ordering decision is raised (the rules-scenario-test skill's
"only when needed" principle).

OQ-15 (`docs/OPEN_QUESTIONS.md`, resolved by this pass): a contested ally
(`AllyInPlay.contested_with` set, `zone == "contested"` -- OQ-10's own
resolution, `engine/allies.py::detect_contest_on_recruit`) now also surfaces
a pending `f"contest_ally:{...}"` effect, resolved by
`engine/allies.py::resolve_one_ally_contest` (mirrors `resolve_one_contest`
below exactly, for the ally-specific pay-1-pool-or-yield mechanism; see that
function's own docstring for why it must *not* restore `zone` to `"ready"`
on either branch). `_unlock_own_allies` is the delayed-restore half the
rulebook's own wording requires ("the card is unlocked and turned face up
during your next unlock phase, ending the contest" -- a further event tied
to the surviving controller's own next unlock phase, not instantaneous with
the opponent's yield): once `resolve_one_ally_contest`'s "yield" branch
clears an ally's `contested_with` while deliberately leaving its `zone` at
`"contested"`, this mandatory step -- run once per `unlock_phase` call,
alongside `_unlock_own_vampires`, *before* the optional pay-or-yield loop --
is what actually flips that ally's `zone` back to `"ready"`, on its own
controller's own next unlock phase (which, per 2P's alternating turns, may
not come up until after the opponent's own next turn too).

OQ-22 (`docs/OPEN_QUESTIONS.md`, resolved by this pass, found implementing
Fame): a contested attached master card (`CardAttachment.contested_with`
set, `zone == "contested"` -- `engine/attachments.py::
detect_contest_on_attach`) gets exactly the same third treatment: a pending
`f"contest_attachment:{...}"` effect resolved by `engine/attachments.py::
resolve_one_attachment_contest`, and `_unlock_own_attachments` as its own
delayed-restore step, mirroring `_unlock_own_allies` for the same "no 2P
override for this card type" reason. The one difference from the vampire/
ally cases: an attachment has no top-level `PlayerState` dict of its own
(it is nested inside whichever vampire's own `attachments` list it was put
on, possibly the *other* player's), so both the pending-effect scan and the
delayed-restore step go through `engine/attachments.py::iter_attachments`/
`find_attachment_by_instance_id` instead of a direct dict lookup, and both
filter by the attachment's own `controller` (who played it), not by whose
vampire it is attached to.

OQ-22 follow-up (resolved finishing Fame, `card-implementer` pass): Fame's
own remaining clause ("During each Methuselah's unlock phase, if this
vampire is in torpor, that Methuselah burns 1 pool") is a *mandatory*
per-unlock-phase effect with no legal alternative, unlike every pending
effect above (each of which is a genuine pay-or-yield/gain-or-decline
choice) -- so it is dispatched as its own `UNLOCK_PHASE_MANDATORY_EFFECT_HOOK`
(`hooks.run_effects`, no `Decision`) rather than folded into
`_pending_effect_ids`. See that constant's own docstring below for why it
runs before, not inside, the optional-effect loop.
"""

from typing import TYPE_CHECKING

from .. import hooks
from ..allies import resolve_one_ally_contest
from ..attachments import (
    find_attachment_by_instance_id,
    iter_attachments,
    resolve_one_attachment_contest,
)
from ..contests import resolve_one_contest
from ..decision import Choice, Decision
from ..pool import gain_pool

if TYPE_CHECKING:
    from ..state import GameState

EDGE_GAIN_EFFECT = "edge_gain"
UNLOCK_PHASE_MANDATORY_EFFECT_HOOK = "unlock_phase_mandatory_effect"
"""Mandatory, non-chosen per-provider reaction hook (`hooks.run_effects`,
`cards/registry.py::Hook.UNLOCK_PHASE_MANDATORY_EFFECT`), dispatched once
per `unlock_phase` call for the unlocking `player` -- distinct from the
*optional* pay-or-yield loop below (`_pending_effect_ids`/
`_resolve_optional_effects_in_chosen_order`), which only ever offers a real
choice. Added resolving `docs/OPEN_QUESTIONS.md` OQ-22's own remaining
clause for Fame (100698, "During each Methuselah's unlock phase, if this
vampire is in torpor, that Methuselah burns 1 pool"): unlike the contested-
card pay-or-yield effects, Fame's own unlock-phase pool burn has no legal
alternative at all, so it is dispatched as a plain mandatory effect
(CLAUDE.md rule 3's "mandatory effects" exception) rather than added to the
player's own orderable pending-effect list. Dispatched before that list is
built/resolved: the one ruling on file for Fame ("[p]aying a pool during the
unlock phase can be ordered with other unlock effects by the acting
Methuselah") only gives the *acting* Methuselah a genuine choice of order
among effects that are themselves optional (pay/yield, Edge gain); since
this effect is unconditional either way, no ordering choice is lost by
resolving it first."""


def unlock_phase(state: GameState, player: str) -> None:
    _unlock_own_vampires(state, player)
    _unlock_own_allies(state, player)
    _unlock_own_attachments(state, player)
    hooks.run_effects(UNLOCK_PHASE_MANDATORY_EFFECT_HOOK, state, player=player)
    _resolve_optional_effects_in_chosen_order(state, player)


def _unlock_own_vampires(state: GameState, player: str) -> None:
    """Rulebook SS4 Unlock Phase: unlock all your (ready-region) cards."""
    for vampire in state.players[player].vampires.values():
        if vampire.zone == "ready":
            vampire.locked = False


def _unlock_own_allies(state: GameState, player: str) -> None:
    """OQ-15 (`docs/OPEN_QUESTIONS.md`): Rulebook SS4 Advanced Rules >
    Contested Cards -- "If all other cards contesting your unique card are
    yielded, then the card is unlocked and turned face up during your next
    unlock phase, ending the contest." An ally whose opposing copy already
    yielded (`contested_with` cleared by `engine/allies.py::
    resolve_one_ally_contest`'s "yield" branch) but whose own `zone` was
    deliberately left at `"contested"` (not instantaneous with the yield --
    see that function's docstring) is restored to `"ready"` and unlocked
    here, on this player's own next unlock phase, ending the contest.

    An ally still actively contested (`contested_with` still set) is left
    untouched: it is picked up instead by the optional pay-or-yield loop
    (`_pending_effect_ids` / `resolve_one_ally_contest`).
    """
    for ally in state.players[player].allies.values():
        if ally.zone == "contested" and ally.contested_with is None:
            ally.zone = "ready"
            ally.locked = False


def _unlock_own_attachments(state: GameState, player: str) -> None:
    """OQ-22 (`docs/OPEN_QUESTIONS.md`): mirrors `_unlock_own_allies`
    exactly, for a contested attached master card (e.g. a future Fame once
    unblocked) instead of an ally -- Rulebook SS4 Advanced Rules > Contested
    Cards: "If all other cards contesting your unique card are yielded, then
    the card is unlocked and turned face up during your next unlock phase,
    ending the contest." An attachment whose opposing copy already yielded
    (`contested_with` cleared by `engine/attachments.py::
    resolve_one_attachment_contest`'s "yield" branch) but whose own `zone`
    was deliberately left at `"contested"` is restored to `"attached"` here,
    on this player's own next unlock phase, ending the contest.

    Scanned via `iter_attachments` (not a direct `PlayerState` dict lookup,
    unlike `_unlock_own_allies`): the attachment may be sitting on either
    player's vampire, so every in-play attachment is checked and filtered by
    its own `controller` (who played it), not by whose vampire it is on.
    """
    for _vampire, attachment in iter_attachments(state):
        if (
            attachment.controller == player
            and attachment.zone == "contested"
            and attachment.contested_with is None
        ):
            attachment.zone = "attached"


def _pending_effect_ids(state: GameState, player: str, resolved: set[str]) -> list[str]:
    effects = [
        f"contest:{v.instance_id}"
        for v in state.players[player].vampires.values()
        if v.contested_with is not None
        and v.zone != "burned"
        and f"contest:{v.instance_id}" not in resolved
    ]
    effects += [
        f"contest_ally:{a.instance_id}"
        for a in state.players[player].allies.values()
        if a.contested_with is not None
        and a.zone != "burned"
        and f"contest_ally:{a.instance_id}" not in resolved
    ]
    effects += [
        f"contest_attachment:{a.instance_id}"
        for _v, a in iter_attachments(state)
        if a.controller == player
        and a.contested_with is not None
        and a.zone != "burned"
        and f"contest_attachment:{a.instance_id}" not in resolved
    ]
    if state.edge_holder == player and EDGE_GAIN_EFFECT not in resolved:
        effects.append(EDGE_GAIN_EFFECT)
    return effects


def _resolve_optional_effects_in_chosen_order(state: GameState, player: str) -> None:
    resolved: set[str] = set()
    while True:
        pending = _pending_effect_ids(state, player, resolved)
        if not pending:
            return
        if len(pending) == 1:
            effect_id = pending[0]
        else:
            choices = tuple(Choice(e, e) for e in pending)
            decision = Decision(player=player, kind="unlock_phase_order", choices=choices)
            effect_id = state.ask(decision).value
        resolved.add(effect_id)
        if effect_id == EDGE_GAIN_EFFECT:
            _resolve_edge_gain(state, player)
        elif effect_id.startswith("contest_ally:"):
            instance_id = effect_id.split(":", 1)[1]
            ally = state.players[player].allies[instance_id]
            resolve_one_ally_contest(state, player, ally)
        elif effect_id.startswith("contest_attachment:"):
            instance_id = effect_id.split(":", 1)[1]
            attachment = find_attachment_by_instance_id(state, instance_id)
            if attachment is None:
                raise KeyError(instance_id)
            resolve_one_attachment_contest(state, player, attachment)
        else:
            instance_id = effect_id.split(":", 1)[1]
            vampire = state.players[player].vampires[instance_id]
            resolve_one_contest(state, player, vampire)


def _resolve_edge_gain(state: GameState, player: str) -> None:
    """ "Edge holder may gain 1 pool" (optional, Rulebook SS4 Unlock Phase)."""
    choices = (
        Choice("gain_pool", "Gain 1 pool from holding the Edge"),
        Choice("decline", "Decline"),
    )
    decision = Decision(player=player, kind="edge_pool_gain", choices=choices)
    if state.ask(decision).value == "gain_pool":
        gain_pool(state, player, 1)
