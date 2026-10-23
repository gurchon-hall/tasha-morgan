"""Weighted Walking Stick (Combat). krcg 102169. Snapshot: data/cards/102169.json
Counters burn as the strike is chosen, before any prevention; full damage while
any counter is left [ANK 20201229-2]. Attach window: ENG-029."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire, window_sides
from vtesbot.engine.attachments import attach_card
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.combat import hand_strike_strength
from vtesbot.engine.hook_contexts import BeforeRangeContext, CombatStrikeOptionContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 102169
NAME = "Weighted Walking Stick"
INITIAL_COUNTERS = 5
STRIKE_BONUS = 1

card = Card(KRCG_ID, NAME, "Combat")


def _find_attachment(vampire: VampireInPlay) -> CardAttachment | None:
    return next((a for a in vampire.attachments if a.krcg_id == KRCG_ID), None)


@card.on(Hook.BEFORE_RANGE)
def _attach(state: GameState, ctx: BeforeRangeContext) -> list[HookOption]:
    """ "This minion" is the player's own combatant."""
    player = ctx["player"]
    if not card.in_hand(state, player):
        return []
    vampire = state.players[player].vampires[window_sides(ctx)[0]]
    if _find_attachment(vampire) is not None:
        return []  # "A minion can have only one Weighted Walking Stick."

    def _apply(s: GameState) -> None:
        card.play_from_hand(s, player)
        attach_card(
            s,
            vampire,
            controller=player,
            krcg_id=KRCG_ID,
            name=NAME,
            counters=INITIAL_COUNTERS,
            is_equipment=True,
        )

    return [
        card.option(
            f"weighted_walking_stick:attach:{vampire.instance_id}",
            f"Weighted Walking Stick: attach to {vampire.card.name}",
            _apply,
        )
    ]


@card.on(Hook.COMBAT_STRIKE_OPTION)
def _strike(state: GameState, ctx: CombatStrikeOptionContext) -> list[HookOption]:
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None:
        return []
    wws = _find_attachment(vampire)
    if wws is None or (wws.counters or 0) <= 0:
        return []
    strength = hand_strike_strength(
        state, player, ctx["vampire"], ctx["opponent"], ctx["combat_state"]
    )
    amount = strength + STRIKE_BONUS

    def _apply(s: GameState) -> int:
        counters = wws.counters or 0
        wws.counters = counters - min(amount, counters)
        if wws.counters == 0:
            vampire.attachments.remove(wws)
        return amount

    return [
        card.option(
            f"weighted_walking_stick:strike:{vampire.instance_id}",
            "Weighted Walking Stick: strike",
            _apply,
            played_card_type=None,  # the attached card strikes; nothing is played
        )
    ]
