"""Parity Shift (Political Action). krcg 101353. Snapshot: data/cards/101353.json
In a duel the target is the opponent, offered only while they have more pool
[LSJ 20100129]; you are the only other Methuselah, so all 3 go to you. RUL-005."""

from typing import Any

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire
from vtesbot.engine.action import ACTION_POLITICAL
from vtesbot.engine.hook_contexts import ActionCardPlayContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.phases.minion import ActionCardSpec, action_card_already_played_this_turn
from vtesbot.engine.politics import POLITICAL_ACTION_STEALTH, resolve_referendum
from vtesbot.engine.pool import gain_pool, lose_pool
from vtesbot.engine.state import GameState

KRCG_ID = 101353
NAME = "Parity Shift"
REQUIRED_TITLES = frozenset({"Prince", "Justicar"})
MAX_ALLOCATION = 3

card = Card(KRCG_ID, NAME, "Political Action")


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_parity_shift(state: GameState, ctx: ActionCardPlayContext) -> list[HookOption]:
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or vampire.card.title not in REQUIRED_TITLES:
        return []
    if not card.in_hand(state, player):
        return []
    other = state.other_player(player)
    if state.players[other].pool <= state.players[player].pool:
        return []
    if action_card_already_played_this_turn(state, vampire, NAME):
        return []

    def _apply(s: GameState) -> ActionCardSpec:
        card.remove_from_hand(s, player)

        def resolve(pending: dict[str, Any]) -> None:
            votes_for, votes_against, _casts = resolve_referendum(
                s, player, other, vampire, action_pending=pending
            )
            if s.game_over or votes_for <= votes_against:
                return  # ousted at tally, or failed (ties fail)
            amount = min(MAX_ALLOCATION, s.players[other].pool)
            lose_pool(s, other, amount)
            gain_pool(s, player, amount)

        return ActionCardSpec(
            base_stealth=POLITICAL_ACTION_STEALTH,
            directed=True,
            action=ACTION_POLITICAL,
            resolve=resolve,
            name=NAME,
        )

    return [card.option("parity_shift:play", "Play Parity Shift", _apply)]
