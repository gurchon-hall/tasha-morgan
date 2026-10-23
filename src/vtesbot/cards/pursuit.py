"""Pursuit (Combat). krcg 101523. Snapshot: data/cards/101523.json
[cel] is a plain maneuver, not one "from a strike", so it locks no strike
(RUL-008). [CEL] uses the cross-card "(limited)" cap (ENG-013)."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire, discipline_level, has_discipline
from vtesbot.engine.combat import additional_strike_limit_used, mark_additional_strike_limit_used
from vtesbot.engine.hook_contexts import CombatAdditionalStrikeContext, ManeuverContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 101523

card = Card(KRCG_ID, "Pursuit", "Combat")


@card.on(Hook.MANEUVER)
def _maneuver(state: GameState, ctx: ManeuverContext) -> list[HookOption]:
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or not has_discipline(state, vampire, "cel"):
        return []
    if not card.in_hand(state, player):
        return []

    def _apply(s: GameState) -> None:
        card.play_from_hand(s, player)

    return [card.option("pursuit:maneuver", "Pursuit [cel]: Maneuver", _apply)]


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
            "pursuit:additional_strike", "Pursuit [CEL]: Additional strike (limited)", _apply
        )
    ]
