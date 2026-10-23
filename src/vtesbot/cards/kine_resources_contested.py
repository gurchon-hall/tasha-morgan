"""Kine Resources Contested (Political Action). krcg 101056. Snapshot: data/cards/101056.json
Terms are chosen before polling, each side at least 1 point [LSJ 20000622]; your own
share may not oust you and stays reserved through the vote (RUL-013, DES-009)."""

from typing import Any

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire
from vtesbot.engine.action import ACTION_POLITICAL
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.errors import UnresolvedRulingError
from vtesbot.engine.hook_contexts import ActionCardPlayContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.phases.minion import ActionCardSpec, action_card_already_played_this_turn
from vtesbot.engine.politics import POLITICAL_ACTION_STEALTH, resolve_referendum
from vtesbot.engine.pool import lose_pool_simultaneously, max_voluntary_spend
from vtesbot.engine.state import GameState

KRCG_ID = 101056
NAME = "Kine Resources Contested"
TOTAL_POINTS = 4

card = Card(KRCG_ID, NAME, "Political Action")


def _legal_self_points(state: GameState, player: str) -> range:
    """Your share, 1 to 3, capped so it cannot zero your pool (DES-009)."""
    return range(1, min(TOTAL_POINTS, max_voluntary_spend(state, player) + 1))


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_kine_resources_contested(
    state: GameState, ctx: ActionCardPlayContext
) -> list[HookOption]:
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or not card.in_hand(state, player):
        return []
    if not _legal_self_points(state, player):
        return []
    if action_card_already_played_this_turn(state, vampire, NAME):
        return []
    other = state.other_player(player)

    def _apply(s: GameState) -> ActionCardSpec:
        card.remove_from_hand(s, player)

        def resolve(pending: dict[str, Any]) -> None:
            choices = tuple(
                Choice(
                    f"allocate:{self_points}",
                    f"Allocate {self_points} point(s) to yourself, "
                    f"{TOTAL_POINTS - self_points} to your opponent "
                    "(each point burns 1 pool)",
                )
                for self_points in _legal_self_points(s, player)
            )
            if not choices:
                raise UnresolvedRulingError(
                    "Kine Resources Contested: no affordable self share when the terms "
                    "are chosen (pool dropped between announce and success)"
                )
            decision = Decision(
                player=player,
                kind="kine_resources_contested_allocation",
                choices=choices,
                context={"caller": player, "other": other},
            )
            self_points = int(s.ask_unless_forced(decision).value.split(":", 1)[1])
            votes_for, votes_against, _casts = resolve_referendum(
                s,
                player,
                other,
                vampire,
                action_pending=pending,
                pool_reserve={player: self_points},
            )
            if s.game_over or votes_for <= votes_against:
                return  # ousted at tally, or failed (ties fail)
            lose_pool_simultaneously(s, {player: self_points, other: TOTAL_POINTS - self_points})

        return ActionCardSpec(
            base_stealth=POLITICAL_ACTION_STEALTH,
            directed=False,
            action=ACTION_POLITICAL,
            resolve=resolve,
            name=NAME,
        )

    return [card.option("kine_resources_contested:play", "Play Kine Resources Contested", _apply)]
