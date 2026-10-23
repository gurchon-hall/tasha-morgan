"""Slam (Combat). krcg 101798. Snapshot: data/cards/101798.json
The 1 blood is paid as the card is played. The [POT] maneuver commits the "as
above" strike for the round (ENG-019, RUL-008); damage per ENG-048."""

from dataclasses import replace

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire, discipline_level, has_discipline
from vtesbot.engine.combat import (
    LONG_RANGE,
    StrikeDamage,
    commit_strike_for_round,
    hand_strike_damage,
    strike_committed_this_round,
)
from vtesbot.engine.hook_contexts import CombatStrikeOptionContext, ManeuverContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 101798
BLOOD_COST = 1
STRIKE_BONUS = 2

card = Card(KRCG_ID, "Slam", "Combat")


def _bonus_strike(
    state: GameState, ctx: CombatStrikeOptionContext | ManeuverContext
) -> StrikeDamage:
    base = hand_strike_damage(
        state, ctx["player"], ctx["vampire"], ctx["opponent"], ctx.get("combat_state")
    )
    return replace(base, amount=base.amount + STRIKE_BONUS)


@card.on(Hook.COMBAT_STRIKE_OPTION)
def _provide_basic(state: GameState, ctx: CombatStrikeOptionContext) -> list[HookOption]:
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or not has_discipline(state, vampire, "pot"):
        return []
    if not card.in_hand(state, player) or vampire.blood < BLOOD_COST:
        return []
    damage = _bonus_strike(state, ctx)

    def _apply(s: GameState) -> StrikeDamage:
        card.play_from_hand(s, player)
        vampire.blood -= BLOOD_COST
        return damage

    return [card.option("slam:basic", "Slam [pot]: hand strike +2 damage", _apply)]


@card.on(Hook.MANEUVER)
def _provide_superior_maneuver(state: GameState, ctx: ManeuverContext) -> list[HookOption]:
    """Offered at long range only, so it always maneuvers to close range; no
    second strike-bundled maneuver in a round (Rulebook §4 Determine Range)."""
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or discipline_level(state, vampire, "pot") < 2:
        return []
    if not card.in_hand(state, player) or vampire.blood < BLOOD_COST:
        return []
    if strike_committed_this_round(ctx) or state.combat_range != LONG_RANGE:
        return []

    def _apply(s: GameState) -> None:
        card.play_from_hand(s, player)
        vampire.blood -= BLOOD_COST
        strike = card.option(
            "slam:superior_strike",
            "Slam [POT]: hand strike +2 damage (committed)",
            lambda s2: _bonus_strike(s2, ctx),
            played_card_type=None,  # already played, at the maneuver
        )
        commit_strike_for_round(ctx, strike)

    return [
        card.option(
            "slam:superior_maneuver",
            "Slam [POT]: maneuver to close range, with hand strike +2 damage",
            _apply,
        )
    ]
