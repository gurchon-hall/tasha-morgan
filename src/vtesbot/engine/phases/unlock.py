"""Unlock phase: unlock all cards, then pay-or-yield/Edge-gain effects,
player-chosen order (Rulebook §4). Contested ally/attachment/master mirror
the crypt pattern; Fame pool-burn runs first (OQ-22).
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
from ..master_cards import resolve_one_master_card_contest
from ..pool import gain_pool

if TYPE_CHECKING:
    from ..state import GameState

EDGE_GAIN_EFFECT = "edge_gain"
UNLOCK_PHASE_MANDATORY_EFFECT_HOOK = "unlock_phase_mandatory_effect"
"""Mandatory per-provider hook (`hooks.run_effects`), run once per
`unlock_phase`, distinct from the optional pay-or-yield loop. Added for
Fame's OQ-22 pool-burn (no alternative); runs before that loop."""


def unlock_phase(state: GameState, player: str) -> None:
    _unlock_own_vampires(state, player)
    _unlock_own_allies(state, player)
    _unlock_own_attachments(state, player)
    _unlock_own_master_cards(state, player)
    hooks.run_effects(UNLOCK_PHASE_MANDATORY_EFFECT_HOOK, state, player=player)
    if state.game_over:
        return
    _resolve_optional_effects_in_chosen_order(state, player)


def _unlock_own_vampires(state: GameState, player: str) -> None:
    """Rulebook §4: unlock all ready-region cards. Also clears
    `qui_vive_played_since_unlock` for every vampire -- its cap is bound to
    this player's unlock phase, not to that vampire unlocking."""
    for vampire in state.players[player].vampires.values():
        vampire.qui_vive_played_since_unlock = False
        if vampire.zone == "ready":
            vampire.locked = False


def _unlock_own_allies(state: GameState, player: str) -> None:
    """Rulebook §4: unlock all cards, not just vampires. OQ-46: skips a
    ready ally's unlock if `skip_next_unlock` is set (one-shot). OQ-15: a
    contested ally whose opponent yielded is restored to ready here."""
    for ally in state.players[player].allies.values():
        if ally.zone == "ready":
            if ally.skip_next_unlock:
                ally.skip_next_unlock = False
            else:
                ally.locked = False
        elif ally.zone == "contested" and ally.contested_with is None:
            ally.zone = "ready"
            ally.locked = False


def _unlock_own_attachments(state: GameState, player: str) -> None:
    """OQ-22: mirrors `_unlock_own_allies`'s contested-restore, for an
    attached master card. Scans via `iter_attachments` since the attachment
    may sit on either player's vampire; filtered by `controller`."""
    for _vampire, attachment in iter_attachments(state):
        if (
            attachment.controller == player
            and attachment.zone == "contested"
            and attachment.contested_with is None
        ):
            attachment.zone = "attached"


def _unlock_own_master_cards(state: GameState, player: str) -> None:
    """OQ-23: unlocks a locked standalone master card, and restores a
    contested card whose opponent yielded, on this player's next unlock
    phase (mirrors `_unlock_own_allies`/`_unlock_own_attachments`)."""
    for card in state.players[player].master_cards.values():
        if card.zone == "in_play" and card.locked:
            card.locked = False
        elif card.zone == "contested" and card.contested_with is None:
            card.zone = "in_play"
            card.locked = False


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
    effects += [
        f"contest_master_card:{card.instance_id}"
        for card in state.players[player].master_cards.values()
        if card.contested_with is not None
        and card.zone != "burned"
        and f"contest_master_card:{card.instance_id}" not in resolved
    ]
    if state.edge_holder == player and EDGE_GAIN_EFFECT not in resolved:
        effects.append(EDGE_GAIN_EFFECT)
    return effects


def _resolve_optional_effects_in_chosen_order(state: GameState, player: str) -> None:
    resolved: set[str] = set()
    while not state.game_over:
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
        elif effect_id.startswith("contest_master_card:"):
            instance_id = effect_id.split(":", 1)[1]
            card = state.players[player].master_cards[instance_id]
            resolve_one_master_card_contest(state, player, card)
        else:
            instance_id = effect_id.split(":", 1)[1]
            vampire = state.players[player].vampires[instance_id]
            resolve_one_contest(state, player, vampire)


def _resolve_edge_gain(state: GameState, player: str) -> None:
    """ "Edge holder may gain 1 pool" (optional, Rulebook §4 Unlock Phase)."""
    choices = (
        Choice("gain_pool", "Gain 1 pool from holding the Edge"),
        Choice("decline", "Decline"),
    )
    decision = Decision(player=player, kind="edge_pool_gain", choices=choices)
    if state.ask(decision).value == "gain_pool":
        gain_pool(state, player, 1)
