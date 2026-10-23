"""Threats (Action Modifier). krcg 101978. Snapshot: data/cards/101978.json
Offered to the bleeder only. "(limited)" is one flag per action, shared with
Bonding (ENG-005)."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import (
    bleed_bookkeeping,
    context_vampire,
    discipline_level,
    has_discipline,
)
from vtesbot.engine.hook_contexts import BleedAmountModifierContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 101978
LIMITED_USED_KEY = "bleed_increase_limited_used"

card = Card(KRCG_ID, "Threats", "Action Modifier")


@card.on(Hook.BLEED_AMOUNT_MODIFIER)
def _play(state: GameState, ctx: BleedAmountModifierContext) -> list[HookOption]:
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or not has_discipline(state, vampire, "dom"):
        return []  # no vampire: `player` is the defender in this window
    if not card.in_hand(state, player):
        return []
    amount_box, book = ctx["amount"], bleed_bookkeeping(ctx["pending"])
    if book.get(LIMITED_USED_KEY):
        return []

    def _option(value: str, label: str, delta: int) -> HookOption:
        def _apply(s: GameState) -> None:
            card.play_from_hand(s, player)
            amount_box[0] += delta
            book[LIMITED_USED_KEY] = True

        return card.option(value, label, _apply)

    options = [_option("threats:basic", "Threats [dom]: +1 bleed (limited)", 1)]
    if discipline_level(state, vampire, "dom") == 2:
        options.append(_option("threats:superior", "Threats [DOM]: +2 bleed (limited)", 2))
    return options
