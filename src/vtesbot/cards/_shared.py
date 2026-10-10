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


def play_from_hand_pending(state: GameState, player: str, krcg_id: int) -> LibraryCard:
    """Remove the first `krcg_id` card from `player`'s hand and draw its
    replacement, *without* yet deciding where the card itself ends up.

    Rulebook SS4 "Announce the Action" (OQ-12, `docs/OPEN_QUESTIONS.md`):
    "Any card required for the action is played (face up) at this time, but
    is temporarily set aside (out of play) until the action resolves." Unlike
    `play_from_hand` (used by master-phase plays and other never-blockable
    plays, which always finish in the ash heap once played), a *minion
    action* built from a played library card has two possible destinations
    depending on the later block-attempt outcome (Rulebook SS4 "Resolve the
    Action": unblocked -> the card's own printed effect takes place; blocked
    -> "any card played to perform the action is burned"), decided only
    after the block-attempt window closes. Callers (e.g. a
    `"recruit_ally_play"` hook option's `apply`, see
    `engine/allies.py::RecruitAllySpec`) keep the returned card and hand it
    to whichever outcome-specific placement the calling minion-phase action
    performs (`engine/phases/minion.py::_perform_recruit_ally`). Still
    "replace from library after play" (Rulebook SS2) immediately, same as
    `play_from_hand` -- that part of the rule does not depend on the
    action's eventual success. Raises `LookupError` if the card is not in
    hand, mirroring `play_from_hand`.
    """
    p = state.players[player]
    for i, card in enumerate(p.hand):
        if card.krcg_id == krcg_id:
            played = p.hand.pop(i)
            if p.library:
                p.hand.append(p.library.pop(0))
            return played
    raise LookupError(f"{player} has no krcg_id={krcg_id} card in hand to play")


def play_from_hand(state: GameState, player: str, krcg_id: int) -> LibraryCard:
    """Play the first `krcg_id` card found in `player`'s hand, straight to
    the ash heap.

    Rulebook SS2 Cards in general: "Play = announce, show, resolve; replace
    from library after play" -- mirrors the already-established pattern in
    `engine/phases/discard.py::discard_phase` (pop from hand, move to the ash
    heap, draw one replacement if the library is non-empty). Raises
    `LookupError` if the card is not in hand; callers must only call this
    after confirming the card is actually there (the hook provider's own
    `offer()` check), so this should never fire in practice.

    Only correct for a play with no block-attempt window of its own (e.g. a
    master-phase play): the card's fate is certain the instant it is played,
    so it can go to the ash heap right away. A blockable minion action built
    from a played card (e.g. "recruit ally") must use
    `play_from_hand_pending` instead, since the card's destination depends on
    an outcome not yet known (OQ-12, `docs/OPEN_QUESTIONS.md`).
    """
    played = play_from_hand_pending(state, player, krcg_id)
    state.players[player].ash_heap.append(played)
    return played


def bleed_bookkeeping(pending: dict[str, Any]) -> dict[str, Any]:
    """Per-bleed-action scratch space for "(limited)"/"same card once per
    action" enforcement (Rulebook SS2 "A minion cannot play the same action
    modifier [or reaction] card more than once during a single action"; SS8
    glossary "Limited": "an action modifier card cannot be played to
    increase the bleed if the bleed amount is already being increased by
    another action modifier card").

    `pending` (`engine/action.py::perform_minion_action`'s per-minion-action
    `dict[str, Any]` scratch container, OQ-11 `docs/OPEN_QUESTIONS.md`) is
    freshly created once per single minion action, *before* the block-attempt
    phase runs, and is threaded unchanged into both the earlier phase's
    `"stealth_modifier"`/`"intercept_modifier"` hook context and the later
    `"bleed_amount_modifier"` window's own context -- so it is the per-action
    (not merely per-window) scratch object this bookkeeping actually needs.
    This function originally keyed off `_perform_bleed`'s `resolve()`-local
    `amount_box` (a `[base_amount]` list that only exists during the later
    window); that was sufficient for Threats/Telepathic Counter, which only
    ever act in that one window, but could not see a "(limited)" bleed
    increase played earlier in the *same* action from the block-attempt
    phase (e.g. Bonding's superior clause, "[DOM] +1 stealth and +1 bleed
    (limited)", whose stealth half is offered during the earlier phase).
    Switching the storage to `pending` closes that gap for every caller with
    no change to call-site lifetime semantics (both objects are freshly
    created once per single bleed action) and no engine change -- `pending`
    was already threaded exactly where needed by OQ-11's resolution.
    """
    return pending.setdefault("_bleed_bookkeeping", {})
