"""Kasim Bayar (Vampire). krcg 201598. Snapshot: data/cards/201598.json
Blocked until its once-per-combat +2 strength is written; the engine supports
it (ENG-046), and "+1 bleed" waits for it."""

from vtesbot.cards.card import Card
from vtesbot.engine.hooks import Hook

KRCG_ID = 201598

card = Card(KRCG_ID, "Kasim Bayar")
card.block(
    "not implemented yet: once-per-combat +2 strength; engine support exists (ENG-046)",
    planned_hooks=(
        Hook.BEFORE_RANGE,
        Hook.COMBAT_STRENGTH_MODIFIER,
        Hook.BLEED_AMOUNT_FIXED_MODIFIER,
    ),
)
