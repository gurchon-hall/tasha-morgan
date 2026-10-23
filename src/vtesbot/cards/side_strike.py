"""Side Strike (Combat). krcg 101778. Snapshot: data/cards/101778.json
Two independent clauses, each played from its own copy; "(limited)" is the cap
shared across cards (ENG-013)."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire, discipline_level, has_discipline
from vtesbot.engine.combat import additional_strike_limit_used, mark_additional_strike_limit_used
from vtesbot.engine.hook_contexts import CombatAdditionalStrikeContext, CombatDodgeOptionContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 101778

card = Card(KRCG_ID, "Side Strike", "Combat")


@card.on(Hook.COMBAT_DODGE_OPTION)
def _dodge(state: GameState, ctx: CombatDodgeOptionContext) -> list[HookOption]:
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or not has_discipline(state, vampire, "cel"):
        return []
    if not card.in_hand(state, player):
        return []

    def _apply(s: GameState) -> None:
        card.play_from_hand(s, player)

    return [card.option("side_strike:dodge", "Side Strike [cel]: dodge", _apply)]


@card.on(Hook.COMBAT_ADDITIONAL_STRIKE)
def _additional_strike(state: GameState, ctx: CombatAdditionalStrikeContext) -> list[HookOption]:
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or discipline_level(state, vampire, "cel") < 2:
        return []
    if not card.in_hand(state, player) or additional_strike_limit_used(ctx):
        return []

    def _apply(s: GameState) -> None:
        card.play_from_hand(s, player)
        mark_additional_strike_limit_used(ctx)

    return [
        card.option(
            "side_strike:additional_strike",
            "Side Strike [CEL]: additional strike (limited)",
            _apply,
        )
    ]
