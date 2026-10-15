"""Private helpers shared by real card modules (not itself a card). Not
imported by `cards/__init__.py`'s module list -- exists so a few cards
don't reimplement the same bookkeeping."""

from typing import TYPE_CHECKING, Any

from vtesbot.engine.cards import LibraryCard
from vtesbot.engine.hand import reconcile_hand_size

if TYPE_CHECKING:
    from vtesbot.engine.state import GameState


def play_from_hand_pending(state: GameState, player: str, krcg_id: int) -> LibraryCard:
    """Remove the first `krcg_id` card from hand, draw its replacement,
    without deciding where it ends up (OQ-12): a blockable action's fate
    depends on the later block outcome. Reconciles hand size (§2)."""
    p = state.players[player]
    for i, card in enumerate(p.hand):
        if card.krcg_id == krcg_id:
            played = p.hand.pop(i)
            if p.library:
                p.hand.append(p.library.pop(0))
            reconcile_hand_size(state, player)
            return played
    raise LookupError(f"{player} has no krcg_id={krcg_id} card in hand to play")


def play_from_hand(state: GameState, player: str, krcg_id: int) -> LibraryCard:
    """Play the first `krcg_id` card in hand, straight to the ash heap
    (Rulebook §2). Only for a play with no block window; a blockable
    action must use `play_from_hand_pending` instead (OQ-12)."""
    played = play_from_hand_pending(state, player, krcg_id)
    state.players[player].ash_heap.append(played)
    return played


def bleed_bookkeeping(pending: dict[str, Any]) -> dict[str, Any]:
    """Per-bleed-action scratch dict for "(limited)" bleed-increase
    enforcement (Rulebook §2/§8). Keyed off `pending` (OQ-11), spanning
    the whole action. An exempt clause (OQ-19) skips `LIMITED_USED_KEY`."""
    return pending.setdefault("_bleed_bookkeeping", {})
