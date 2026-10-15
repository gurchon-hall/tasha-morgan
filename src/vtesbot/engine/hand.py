"""Hand-size enforcement (Rulebook §2). `HAND_SIZE_MODIFIER_HOOK` is the
passive numeric hook. `reconcile_hand_size` must be called after every
hand mutation."""

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
