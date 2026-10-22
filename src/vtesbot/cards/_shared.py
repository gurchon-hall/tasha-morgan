"""Private helpers shared by real card modules (not itself a card). Not
imported by `cards/__init__.py`'s module list -- exists so a few cards
don't reimplement the same bookkeeping. `remove_from_hand`/
`draw_replacement_card` are re-exported, not redefined, from `engine/
hand.py` (ENG-037): the actual mechanism lives in
the engine layer so `engine/phases/minion.py` can call it directly without
importing from `cards/` (CLAUDE.md §6)."""

from typing import TYPE_CHECKING, Any

from vtesbot.engine.cards import LibraryCard
from vtesbot.engine.hand import draw_replacement_card, reconcile_hand_size
from vtesbot.engine.hand import remove_from_hand as remove_from_hand

if TYPE_CHECKING:
    from vtesbot.engine.state import GameState

__all__ = [
    "bleed_bookkeeping",
    "draw_replacement_card",
    "play_from_hand",
    "play_from_hand_pending",
    "remove_from_hand",
]


def play_from_hand_pending(state: GameState, player: str, krcg_id: int) -> LibraryCard:
    """Remove the first `krcg_id` card from hand, draw its replacement,
    without deciding where it ends up (ENG-006): a blockable action's fate
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
    """Play the first `krcg_id` card in hand, straight to the ash heap,
    drawing its replacement immediately (Rulebook §2) -- a thin wrapper of
    `remove_from_hand` + `draw_replacement_card` (`engine/hand.py`) for a
    play with no block window and no "as played" cancel window of its own
    to interleave between the two (every caller except the Action-card
    `ACTION_CARD_PLAY_HOOK` providers fixed by ENG-037 Finding 1, which call
    `remove_from_hand` directly from their own `apply()` instead). A
    blockable action with a later, undetermined destination must use
    `play_from_hand_pending` instead (ENG-006)."""
    played = remove_from_hand(state, player, krcg_id)
    draw_replacement_card(state, player)
    return played


def bleed_bookkeeping(pending: dict[str, Any]) -> dict[str, Any]:
    """Per-bleed-action scratch dict for "(limited)" bleed-increase
    enforcement (Rulebook §2/§8). Keyed off `pending` (ENG-005), spanning
    the whole action. An exempt clause (ENG-013) skips `LIMITED_USED_KEY`."""
    return pending.setdefault("_bleed_bookkeeping", {})
