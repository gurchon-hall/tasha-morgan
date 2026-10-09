"""Private helpers shared by real card effect modules (not itself a card).

Leading underscore: this module registers nothing and is not imported by
`src/vtesbot/cards/__init__.py`'s module list; it exists only so
`life_in_the_city.py` / `telepathic_counter.py` / `threats.py` do not each
reimplement the same two small pieces of bookkeeping.
"""

from typing import TYPE_CHECKING, Any

from vtesbot.engine.cards import LibraryCard

if TYPE_CHECKING:
    from vtesbot.engine.state import GameState


def play_from_hand(state: GameState, player: str, krcg_id: int) -> LibraryCard:
    """Play the first `krcg_id` card found in `player`'s hand.

    Rulebook SS2 Cards in general: "Play = announce, show, resolve; replace
    from library after play" -- mirrors the already-established pattern in
    `engine/phases/discard.py::discard_phase` (pop from hand, move to the ash
    heap, draw one replacement if the library is non-empty). Raises
    `LookupError` if the card is not in hand; callers must only call this
    after confirming the card is actually there (the hook provider's own
    `offer()` check), so this should never fire in practice.
    """
    p = state.players[player]
    for i, card in enumerate(p.hand):
        if card.krcg_id == krcg_id:
            played = p.hand.pop(i)
            p.ash_heap.append(played)
            if p.library:
                p.hand.append(p.library.pop(0))
            return played
    raise LookupError(f"{player} has no krcg_id={krcg_id} card in hand to play")


def bleed_bookkeeping(amount_box: list[Any]) -> dict[str, Any]:
    """Per-bleed-action scratch space for "(limited)"/"same card once per
    action" enforcement (Rulebook SS2 "A minion cannot play the same action
    modifier [or reaction] card more than once during a single action"; SS8
    glossary "Limited": "an action modifier card cannot be played to
    increase the bleed if the bleed amount is already being increased by
    another action modifier card").

    `amount_box` (`engine/phases/minion.py::_perform_bleed`'s `[base_amount]`
    list, threaded through the `"bleed_amount_modifier"` hook's context) is
    freshly created once per single bleed action and goes out of scope right
    after that action's impulse window closes, so it is exactly the
    per-action-scoped object this bookkeeping needs -- no new engine state,
    no change to any engine file, and the engine's own contract (it reads
    only `amount_box[0]` at the end) is left intact; this just appends one
    extra element lazily the first time any card asks for it.
    """
    if len(amount_box) < 2:
        amount_box.append({})
    return amount_box[1]
