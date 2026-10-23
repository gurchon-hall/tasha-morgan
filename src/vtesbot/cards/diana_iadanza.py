"""Diana Iadanza (Vampire). krcg 201694. Snapshot: data/cards/201694.json
Cancels a `Reaction` play only, in a referendum she called; once per referendum
(Rulebook §3 "During X, do Y"). See ENG-022, ENG-023."""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire
from vtesbot.engine.hook_contexts import BleedAmountFixedModifierContext, CancelAsPlayedContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 201694
PENDING_CANCELED_KEY = "diana_iadanza_canceled"
BLOOD_COST = 1

card = Card(KRCG_ID, "Diana Iadanza")


@card.on(Hook.BLEED_AMOUNT_FIXED_MODIFIER)
def _bleed(state: GameState, ctx: BleedAmountFixedModifierContext) -> int:
    vampire = context_vampire(state, ctx)
    return 1 if vampire is not None and vampire.card.krcg_id == KRCG_ID else 0


@card.on(Hook.CANCEL_AS_PLAYED)
def _cancel(state: GameState, ctx: CancelAsPlayedContext) -> list[HookOption]:
    """Reads the referendum's `caller_vampire_id` and `pending` from the open
    context."""
    if ctx["canceled_card_type"] != "Reaction":
        return []
    window: Mapping[str, Any] = ctx
    caller_vampire_id = window.get("caller_vampire_id")
    if caller_vampire_id is None:
        return []
    diana = state.players[ctx["player"]].vampires.get(caller_vampire_id)
    if diana is None or diana.card.krcg_id != KRCG_ID or diana.blood < BLOOD_COST:
        return []
    pending = window.get("pending")
    if pending is None or pending.get(PENDING_CANCELED_KEY, False):
        return []

    def _apply(_s: GameState) -> None:
        diana.blood -= BLOOD_COST
        pending[PENDING_CANCELED_KEY] = True

    return [
        card.option(
            f"diana_iadanza_cancel:{diana.instance_id}",
            "Diana Iadanza: burn 1 blood to cancel a reaction card as it is played",
            _apply,
        )
    ]
