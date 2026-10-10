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
"""

from typing import TYPE_CHECKING

from ..allies import resolve_one_ally_contest
from ..contests import resolve_one_contest
from ..decision import Choice, Decision
from ..pool import gain_pool

if TYPE_CHECKING:
    from ..state import GameState

EDGE_GAIN_EFFECT = "edge_gain"


def unlock_phase(state: GameState, player: str) -> None:
    _unlock_own_vampires(state, player)
    _unlock_own_allies(state, player)
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
