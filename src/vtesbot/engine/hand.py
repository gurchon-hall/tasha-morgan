"""Hand-size enforcement: the generic "match your hand size" mechanic.

Source: Rulebook §2 Card Types > Drawing Cards (local cache `data/sources/
rulebook/2026-10-09/2-card-types.md`, lines 128-137), verbatim: "The number
of cards in your hand should always match your hand size (cards that are
replaced later reduce your hand size for the duration of the effect). The
starting default hand size is seven cards in hand. Whenever an effect
changes your hand size or adds or removes cards from your hand, immediately
discard down to or draw up to match your hand size." The same section's
earlier sentence ("If your library is empty, then you do not draw to
replenish your hand, but you do continue to play") is why draw-up silently
stops, rather than erroring, once the library runs dry.

`FormatConfig.hand_size` (`engine/format.py`) is the base value ("seven
cards in hand"); `HAND_SIZE_MODIFIER_HOOK` is the passive, mandatory numeric
hook (`hooks.sum_modifiers` contract, CLAUDE.md rule 3's "mandatory effects"
exception) a printed ability uses to change it for as long as some condition
holds -- the motivating case is Carmelita Neillson (krcg id 201625,
"Camarilla: While Carmelita is ready, you get +1 hand size"), whose own
effect module (a later `card-implementer` pass, not built here) registers a
provider against this hook. Mirrors `engine/attachments.py::
CAPACITY_MODIFIER_HOOK`/`effective_capacity`'s own shape exactly: a provider
is a plain `Callable[[GameState, Mapping], int]` returning 0 when it does
not apply, and -- because the hook models a *continuously re-evaluated*
condition ("while Carmelita is ready") rather than a one-shot effect -- must
itself re-check its own trigger (e.g. the granting vampire's current
`zone`/`locked`) every call, rather than caching a prior answer.

`reconcile_hand_size` is the one function every hand-mutating call site
calls immediately after changing a player's hand (CLAUDE.md rule 3: a
forced discard still lets the player choose *which* card, since the rule
does not say; drawing up has no choice to offer at all, so it never raises a
`Decision` -- mirrors `engine/phases/discard.py::discard_phase`'s own
replacement-draw, logged the same way via `state.log.record_random`). Wired
call sites: `vtesbot.cards._shared.play_from_hand_pending` (the
one chokepoint every card play's own replacement draw already goes through,
per that module's docstring) and `engine/phases/discard.py::discard_phase`'s
own discard+replacement branch. `engine/setup.py`'s initial 7-card deal is
deliberately *not* wired: it deals before any `GameState` exists and before
any vampire can be `"ready"` (crypt cards are dealt face-down, `zone=
"uncontrolled"`, in the same setup pass), so no `HAND_SIZE_MODIFIER_HOOK`
provider can possibly apply yet. A future hand-size-changing card whose
trigger is not "a replacement draw" at all (e.g. a torpor/diablerie effect
that touches hand size, or a card that changes hand size outright rather
than via a printed modifier) must call `reconcile_hand_size` itself right
after the mutation -- this module does not attempt to anticipate every such
site, per the Rulebook's own "whenever an effect changes your hand size ...
immediately" wording (the obligation is on the mutating code, not a single
end-of-phase sweep).
"""

from typing import TYPE_CHECKING

from . import hooks
from .decision import Choice, Decision

if TYPE_CHECKING:
    from .state import GameState

HAND_SIZE_MODIFIER_HOOK = "hand_size_modifier"
"""Passive, mandatory numeric hook (`hooks.sum_modifiers` contract) -- see
module docstring. Matches `src/vtesbot/cards/registry.py::Hook.
HAND_SIZE_MODIFIER`'s own string value."""


def effective_hand_size(state: GameState, player: str) -> int:
    """`FormatConfig.hand_size` (Rulebook §2: "the starting default hand size
    is seven cards in hand") plus every registered `HAND_SIZE_MODIFIER_HOOK`
    provider's current contribution for `player`.

    Re-evaluated from scratch on every call (no caching): a provider for a
    continuously-conditional ability (e.g. "while Carmelita is ready") must
    reflect the *current* game state, not whatever was true the last time
    this was read (see module docstring).
    """
    return state.format.hand_size + hooks.sum_modifiers(
        HAND_SIZE_MODIFIER_HOOK, state, player=player
    )


def reconcile_hand_size(state: GameState, player: str) -> None:
    """Immediately discard down to, or draw up to, `player`'s effective hand
    size (Rulebook §2, quoted in the module docstring).

    Discarding down is a real choice (the rule does not say which card, so
    the player picks, one card at a time, mirroring `engine/phases/
    discard.py::discard_phase`'s own per-card `Decision` shape) -- offered
    with no "pass"/decline option, since the discard itself is mandatory,
    only *which* card is not. Drawing up is automatic (nothing to choose)
    and logged via `state.log.record_random`, exactly like `discard_phase`'s
    own replacement draw; it silently stops once the library is empty
    ("you do not draw to replenish your hand, but you do continue to play"),
    never raising or crashing.

    Re-derives the target hand size on every loop iteration (`effective_
    hand_size` is cheap and side-effect-free) rather than computing it once,
    so a hypothetical provider that itself reacts to a discard/draw stays
    correctly reflected -- no such provider exists yet, this is just not
    assuming the target is frozen for the duration of the call.
    """
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
