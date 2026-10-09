"""Master phase.

Source: Rulebook SS4 Master Phase (per the `vtes-rules-reference` skill
condensed mapping): "1 master phase action by default; trifles grant one
extra (max one per phase); an out-of-turn master played earlier removes
one; unused actions are lost."

CLAUDE.md milestone-2 scope: no master cards are implemented yet (the card
pool is out of scope for this pass, CLAUDE.md SS9 milestone 3). There is
therefore nothing legal to do in this phase this milestone, so it is a
structural no-op: the turn sequence still names and runs the phase (so the
five-phase turn structure is correct and extensible), but it never raises a
decision, since a decision with no legal options would violate "only when
needed" / "never a vacuous Decision". This function is the hook point for
master-phase card plays in a later milestone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..state import GameState


def master_phase(state: GameState, player: str) -> None:
    return
