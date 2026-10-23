"""Loup (Action Modifier). krcg 102273. Snapshot: data/cards/102273.json
Table-wide: any Toreador gets each Loup's +1 stealth, once per copy per action,
and a Toreador success burns every Loup (RUL-012). Proactive window: RUL-011."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import acting_vampire
from vtesbot.engine.action import PENDING_STEALTH_INCREASE_KEY, ActiveStealthIncrease
from vtesbot.engine.hook_contexts import ActionSucceededContext, StealthIncreaseContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState
from vtesbot.engine.turn_cards import active_turn_cards, bring_turn_card_into_play, burn_turn_card

KRCG_ID = 102273
NAME = "Loup"
CLAN_REQUIREMENT = "Toreador"
LOUP_STEALTH_GRANTED_KEY = "loup_stealth_granted"

card = Card(KRCG_ID, NAME, "Action Modifier")


@card.on(Hook.STEALTH_INCREASE)
def _provide_loup(state: GameState, ctx: StealthIncreaseContext) -> list[HookOption]:
    """One option per in-play copy not yet granted, plus playing one from hand;
    "only one Loup each turn" is per player (`card_played_turn`)."""
    player, vampire = ctx["player"], acting_vampire(state, ctx)
    if vampire is None or vampire.card.clan != CLAN_REQUIREMENT:
        return []
    pending = ctx["pending"]
    granted: set[str] = pending.setdefault(LOUP_STEALTH_GRANTED_KEY, set())

    def _grant(instance_id: str) -> None:
        pending.setdefault(PENDING_STEALTH_INCREASE_KEY, []).append(ActiveStealthIncrease(delta=1))
        granted.add(instance_id)

    options: list[HookOption] = []
    for owner in state.players:
        for copy in active_turn_cards(state, owner, KRCG_ID):
            if copy.instance_id in granted:
                continue

            def _apply_bonus(_s: GameState, instance_id: str = copy.instance_id) -> None:
                _grant(instance_id)

            options.append(
                card.option(
                    f"loup:stealth_bonus:{copy.instance_id}",
                    f"Loup ({copy.controller}'s copy): Toreador get +1 stealth",
                    _apply_bonus,
                    played_card_type=None,  # a card already in play
                )
            )

    if card.in_hand(state, player) and (
        state.players[player].card_played_turn.get(KRCG_ID) != state.turn_number
    ):

        def _apply_play(s: GameState) -> None:
            card.play_from_hand_pending(s, player)
            turn_card = bring_turn_card_into_play(s, player, krcg_id=KRCG_ID, name=NAME)
            s.players[player].card_played_turn[KRCG_ID] = s.turn_number
            _grant(turn_card.instance_id)

        options.append(
            card.option(
                "loup:play", "Play Loup: put it in play, Toreador get +1 stealth", _apply_play
            )
        )
    return options


@card.on(Hook.ACTION_SUCCEEDED)
def _provide_loup_burn(state: GameState, ctx: ActionSucceededContext) -> None:
    if ctx["vampire"].card.clan != CLAN_REQUIREMENT:
        return
    for owner in state.players:
        for copy in active_turn_cards(state, owner, KRCG_ID):
            burn_turn_card(copy)
