"""Turn-scoped library cards (ENG-024): stays in play for the rest of the
turn played, auto-burned at end of turn unless burned sooner (e.g. Loup).
Generic primitives; specifics live in the card's module."""

from typing import TYPE_CHECKING

from .state import TurnCardInPlay

if TYPE_CHECKING:
    from .state import GameState


def bring_turn_card_into_play(
    state: GameState,
    player: str,
    *,
    krcg_id: int,
    name: str,
) -> TurnCardInPlay:
    """Put a new turn-scoped card into play under `player`'s control."""
    p = state.players[player]
    instance_id = p.new_turn_card_instance_id()
    card = TurnCardInPlay(instance_id=instance_id, krcg_id=krcg_id, name=name, controller=player)
    p.turn_cards[instance_id] = card
    return card


def burn_turn_card(card: TurnCardInPlay) -> None:
    """Burn condition 1 or 2 (module docstring): plain mandatory zone flip,
    no cost, no decision -- either burn trigger named on the card is a
    forced effect with no legal alternative (CLAUDE.md rule 3)."""
    card.zone = "burned"


def active_turn_cards(state: GameState, player: str, krcg_id: int) -> list[TurnCardInPlay]:
    """Every `is_in_play` turn card of `krcg_id` controlled by `player` --
    the "is it in play for this player" check a card provider needs."""
    return [
        card
        for card in state.players[player].turn_cards.values()
        if card.krcg_id == krcg_id and card.is_in_play
    ]


def clear_turn_cards_at_end_of_turn(state: GameState, player: str) -> None:
    """Burn condition 1: every `is_in_play` turn card `player` controls is
    burned once their turn ends, unconditionally (CLAUDE.md rule 3).
    Called from `play_turn` right before the turn flips (ENG-024)."""
    for card in state.players[player].turn_cards.values():
        if card.is_in_play:
            burn_turn_card(card)
