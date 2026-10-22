"""Unlock phase: unlock all cards, then pay-or-yield/Edge-gain/mandatory
card effects, player-chosen order (Rulebook §4). Contested ally/
attachment/master mirror the crypt pattern. A `UNLOCK_PHASE_MANDATORY_
EFFECT_HOOK` effect (e.g. Fame's clause-4 burn) is folded into that same
ordering choice rather than forced first: Fame's own on-file ruling [LSJ
20110121] says such a payment "can be ordered with other unlock effects
by the acting Methuselah, but must be handled before another Methuselah
has the opportunity to use an unlock effect" -- orderable, not
front-loaded (see `cards/fame.py` for the full citation).
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
from ..hooks import HookOption
from ..master_cards import resolve_one_master_card_contest
from ..pool import gain_pool

if TYPE_CHECKING:
    from ..state import GameState

EDGE_GAIN_EFFECT = "edge_gain"
UNLOCK_PHASE_MANDATORY_EFFECT_HOOK = "unlock_phase_mandatory_effect"
"""`hooks.offer`-style hook (one `HookOption` per currently-applicable
mandatory effect, e.g. Fame's clause-4 burn), queried once per iteration
of `_resolve_optional_effects_in_chosen_order`'s own loop and folded into
its ordering choice. Mandatory because an unresolved option keeps
reappearing every iteration (dedup by the option's own `Choice.value`,
namespaced `"mandatory:"` by this module, not by the provider) -- the
loop cannot end, and `unlock_phase` cannot return, while one remains
(Fame's own ruling, quoted on this module's own docstring above)."""


def unlock_phase(state: GameState, player: str) -> None:
    _unlock_own_vampires(state, player)
    _unlock_own_allies(state, player)
    _unlock_own_attachments(state, player)
    _unlock_own_master_cards(state, player)
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
    """Rulebook §4: unlock all cards, not just vampires. ENG-028: skips a
    ready ally's unlock if `skip_next_unlock` is set (one-shot). ENG-009: a
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
    """ENG-014: mirrors `_unlock_own_allies`'s contested-restore, for an
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
    """ENG-015: unlocks a locked standalone master card, and restores a
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


def _mandatory_effect_options(state: GameState, player: str) -> dict[str, HookOption]:
    """Wraps each `UNLOCK_PHASE_MANDATORY_EFFECT_HOOK` option's own
    `Choice.value` under an engine-owned `"mandatory:"` namespace, so the
    ordering loop below can recognize it without any card-specific
    knowledge (CLAUDE.md rule 6). Only one provider (Fame) registers this
    hook today, but `ensure_unique_choice_values` guards the dict
    comprehension below regardless: two future providers picking the same
    raw `Choice.value` would otherwise silently collapse into one entry,
    permanently dropping the first provider's `HookOption` with no error
    (rules-auditor review) -- same convention as `action.py`'s
    `STEALTH_MODIFIER_HOOK`/`block_attempt` and `politics.py`'s
    `polling_step_cast` call sites."""
    options = hooks.offer(UNLOCK_PHASE_MANDATORY_EFFECT_HOOK, state, player=player)
    hooks.ensure_unique_choice_values(
        tuple(option.choice for option in options),
        decision_kind=UNLOCK_PHASE_MANDATORY_EFFECT_HOOK,
    )
    return {f"mandatory:{option.choice.value}": option for option in options}


def _resolve_optional_effects_in_chosen_order(state: GameState, player: str) -> None:
    resolved: set[str] = set()
    while not state.game_over:
        mandatory_options = _mandatory_effect_options(state, player)
        pending = _pending_effect_ids(state, player, resolved)
        pending += [effect_id for effect_id in mandatory_options if effect_id not in resolved]
        if not pending:
            return
        if len(pending) == 1:
            effect_id = pending[0]
        else:
            choices = tuple(
                Choice(e, mandatory_options[e].choice.label if e in mandatory_options else e)
                for e in pending
            )
            decision = Decision(player=player, kind="unlock_phase_order", choices=choices)
            effect_id = state.ask(decision).value
        resolved.add(effect_id)
        if effect_id in mandatory_options:
            mandatory_options[effect_id].apply(state)
        elif effect_id == EDGE_GAIN_EFFECT:
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
