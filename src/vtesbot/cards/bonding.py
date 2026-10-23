"""Bonding (Action Modifier). krcg 100236. Snapshot: data/cards/100236.json
[DOM] plays in the stealth window of a bleed only [LSJ 19980824]; its +1 bleed
waits in `pending` (ENG-005). "(limited)" is shared with Threats."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import (
    acting_vampire,
    bleed_bookkeeping,
    context_vampire,
    discipline_level,
    has_discipline,
)
from vtesbot.cards.threats import LIMITED_USED_KEY
from vtesbot.engine.action import ACTION_BLEED
from vtesbot.engine.hook_contexts import BleedAmountModifierContext, StealthModifierContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.phases.minion import PENDING_BLEED_AMOUNT_KEY
from vtesbot.engine.state import GameState

KRCG_ID = 100236

card = Card(KRCG_ID, "Bonding", "Action Modifier")


@card.on(Hook.BLEED_AMOUNT_MODIFIER)
def _provide_bonding_basic(state: GameState, ctx: BleedAmountModifierContext) -> list[HookOption]:
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or not has_discipline(state, vampire, "dom"):
        return []  # no vampire: `player` is the defender in this window
    if not card.in_hand(state, player):
        return []
    book = bleed_bookkeeping(ctx["pending"])
    if book.get(LIMITED_USED_KEY):
        return []
    amount_box = ctx["amount"]

    def _apply(s: GameState) -> None:
        card.play_from_hand(s, player)
        amount_box[0] += 1
        book[LIMITED_USED_KEY] = True

    return [card.option("bonding:basic", "Bonding [dom]: +1 bleed (limited)", _apply)]


@card.on(Hook.STEALTH_MODIFIER)
def _provide_bonding_superior(state: GameState, ctx: StealthModifierContext) -> list[HookOption]:
    """Only offered while stealth is needed [TOM 19951109]: the engine asks for
    stealth only then."""
    if ctx["action"] != ACTION_BLEED:
        return []
    player, vampire = ctx["player"], acting_vampire(state, ctx)
    if vampire is None or discipline_level(state, vampire, "dom") < 2:
        return []
    if not card.in_hand(state, player):
        return []
    pending = ctx["pending"]
    book = bleed_bookkeeping(pending)
    if book.get(LIMITED_USED_KEY):
        return []

    def _apply(s: GameState) -> int:
        card.play_from_hand(s, player)
        book[LIMITED_USED_KEY] = True
        pending[PENDING_BLEED_AMOUNT_KEY] = pending.get(PENDING_BLEED_AMOUNT_KEY, 0) + 1
        return 1  # the +1 stealth

    return [
        card.option("bonding:superior", "Bonding [DOM]: +1 stealth and +1 bleed (limited)", _apply)
    ]
