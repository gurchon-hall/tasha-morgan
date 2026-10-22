"""Hand-size enforcement (Rulebook §2). `HAND_SIZE_MODIFIER_HOOK` is the
passive numeric hook. `reconcile_hand_size` must be called after every hand
mutation. `remove_from_hand`/`draw_replacement_card` (ENG-037) are the generic
engine-layer primitives behind `cards/_shared.py::play_from_hand` -- kept here,
not in `cards/`, so engine code (`engine/phases/minion.py`) can call
`draw_replacement_card` directly without importing from the cards layer
(CLAUDE.md §6: cards register into the engine, never the reverse)."""

from typing import TYPE_CHECKING

from . import hooks
from .decision import Choice, Decision
from .hooks import Hook

if TYPE_CHECKING:
    from .cards import LibraryCard
    from .state import GameState

HAND_SIZE_MODIFIER_HOOK = Hook.HAND_SIZE_MODIFIER
"""Passive, mandatory numeric hook (`hooks.sum_modifiers` contract) -- see
module docstring. Matches `src/vtesbot/cards/registry.py::Hook.
HAND_SIZE_MODIFIER`'s own string value."""


def effective_hand_size(state: GameState, player: str) -> int:
    """`FormatConfig.hand_size` plus every `HAND_SIZE_MODIFIER_HOOK` provider's current
    contribution for `player`. Re-evaluated fresh every call, never cached."""
    return state.format.hand_size + hooks.sum_modifiers(
        HAND_SIZE_MODIFIER_HOOK, state, player=player
    )


def reconcile_hand_size(state: GameState, player: str) -> None:
    """Discard down to, or draw up to, `player`'s effective hand size (§2).
    Discarding is mandatory but which card is a real choice; drawing up is
    automatic, silently stopping once the library is empty."""
    p = state.players[player]
    while len(p.hand) > effective_hand_size(state, player):
        choices = tuple(
            Choice(f"discard:{i}", f"Discard {card.name}") for i, card in enumerate(p.hand)
        )
        decision = Decision(player=player, kind="hand_size_discard", choices=choices)
        choice = state.ask(decision).value
        index = int(choice.split(":", 1)[1])
        card = p.hand.pop(index)
        p.ash_heap.append(card)
    while p.library and len(p.hand) < effective_hand_size(state, player):
        drawn = p.library.pop(0)
        state.log.record_random(f"{player} draws up to hand size", drawn.name)
        p.hand.append(drawn)


def remove_from_hand(state: GameState, player: str, krcg_id: int) -> LibraryCard:
    """Remove the first `krcg_id` card from hand straight to the ash heap,
    without drawing its replacement (ENG-037 Finding 1). Rulebook §2 Card
    Types, "Library Cards" Advanced Rules
    (`data/sources/rulebook/2026-10-09/2-card-types.md:124-126`): "Some effects
    can cancel a card 'as it is played.' ... Even drawing to replace cards,
    comes after this time period." -- so a caller with an "as played" cancel
    window to offer first (`engine/phases/minion.py::_perform_action_card`, for
    an Action-type card specifically) calls this instead of
    `cards/_shared.py::play_from_hand`, then calls `draw_replacement_card` only
    once that window closes."""
    p = state.players[player]
    for i, card in enumerate(p.hand):
        if card.krcg_id == krcg_id:
            played = p.hand.pop(i)
            p.ash_heap.append(played)
            return played
    raise LookupError(f"{player} has no krcg_id={krcg_id} card in hand to play")


def draw_replacement_card(state: GameState, player: str) -> None:
    """Draw one card from library to replace a card just removed from hand
    (`remove_from_hand`), reconciling hand size (§2). Rulebook §3 "Cancel a
    Card" (`3-playing-the-game.md:103`): "A cancelled card has no effect,
    but it is still considered played" -- being played, not succeeding, is
    what triggers the replacement draw, so a caller runs this exactly once,
    unconditionally, after any "as played" cancel window for that card
    closes, whether or not it was canceled."""
    p = state.players[player]
    if p.library:
        p.hand.append(p.library.pop(0))
    reconcile_hand_size(state, player)
