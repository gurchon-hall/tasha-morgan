"""Discard phase.

Source: Rulebook SS4 Discard Phase (per the `vtes-rules-reference` skill
condensed mapping): "1 discard phase action (discard + replace, or play one
event)." CLAUDE.md milestone-2 scope: event cards are not implemented, so
only "discard a hand card and draw its replacement" (Rulebook SS2: "replace
from library after play") or passing are offered.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..decision import Choice, Decision

if TYPE_CHECKING:
    from ..state import GameState


def discard_phase(state: GameState, player: str) -> None:
    p = state.players[player]
    if not p.hand:
        return  # nothing legal to discard: no vacuous decision raised.

    choices = tuple(
        Choice(f"discard:{i}", f"Discard {card.name}") for i, card in enumerate(p.hand)
    ) + (Choice("pass", "Pass (no discard phase action)"),)
    decision = Decision(player=player, kind="discard_phase_action", choices=choices)
    choice = state.ask(decision).value
    if choice == "pass":
        return

    index = int(choice.split(":", 1)[1])
    card = p.hand.pop(index)
    p.ash_heap.append(card)
    if p.library:
        drawn = p.library.pop(0)
        state.log.record_random(f"{player} draws a discard-phase replacement", drawn.name)
        p.hand.append(drawn)
