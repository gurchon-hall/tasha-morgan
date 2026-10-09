"""Unlock phase.

Source: Rulebook SS4 Unlock Phase (per the `vtes-rules-reference` skill
condensed mapping): "unlock all your cards, then unlock-phase effects in the
order you choose; Edge holder may gain 1 pool. Contests paid here (1 pool
per contested card ...)." The order of the player's own optional unlock-
phase effects (each contested crypt card's pay/yield, and the optional Edge
pool gain) is the acting player's choice -- this is the impulse/sequencing
model (CLAUDE.md SS4 / Rulebook SS2 Sequencing) applied to the Unlock phase:
the player picks which of several available effects to resolve next, one at
a time, until none remain. When only one effect is available there is
nothing to "choose the order" of, so no vacuous ordering decision is raised
(the rules-scenario-test skill's "only when needed" principle).
"""

from typing import TYPE_CHECKING

from ..contests import resolve_one_contest
from ..decision import Choice, Decision
from ..pool import gain_pool

if TYPE_CHECKING:
    from ..state import GameState

EDGE_GAIN_EFFECT = "edge_gain"


def unlock_phase(state: GameState, player: str) -> None:
    _unlock_own_vampires(state, player)
    _resolve_optional_effects_in_chosen_order(state, player)


def _unlock_own_vampires(state: GameState, player: str) -> None:
    """Rulebook SS4 Unlock Phase: unlock all your (ready-region) cards."""
    for vampire in state.players[player].vampires.values():
        if vampire.zone == "ready":
            vampire.locked = False


def _pending_effect_ids(state: GameState, player: str, resolved: set[str]) -> list[str]:
    effects = [
        f"contest:{v.instance_id}"
        for v in state.players[player].vampires.values()
        if v.contested_with is not None
        and v.zone != "burned"
        and f"contest:{v.instance_id}" not in resolved
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
