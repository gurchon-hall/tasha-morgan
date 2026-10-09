"""Basic combat: hand strikes only, fixed close range.

Source: Rulebook SS4 Combat (per the `vtes-rules-reference` skill condensed
mapping): "Rounds of 7 steps: before range -> determine range (maneuvers
alternate, no two in a row) -> before strikes -> strike (acting minion
chooses first; simultaneous resolution) -> damage resolution (prevent, then
mend) -> press (alternating) -> end of round. Combat ends at once if a
combatant is no longer ready." "Hand strike = strength (default 1), close
range only."

CLAUDE.md milestone-2 scope restriction: only hand strikes are implemented
(no ranged strikes, no maneuvers/range changes, no equipment/retainers/
allies in combat). Range therefore has nothing to determine this milestone:
combat is fixed at close range by construction (the only range hand strikes
need), and the "before range"/"determine range" steps are no-ops pending a
later milestone that adds ranged weapons and the maneuver mechanic.

Press step order (resolves docs/OPEN_QUESTIONS.md OQ-3): the rulebook states
"The acting minion always gets first opportunity to use cards or effects
before the opposing minion" at every stage of combat, including press (per
`rules-auditor`'s verbatim quote from the primary rulebook text, matching
the project's own impulse invariant, CLAUDE.md SS5 / Rulebook SS2
Sequencing). The acting minion's controller is therefore always asked to
press first, every round, never alternating by round parity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .damage import apply_damage
from .decision import Choice, Decision

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

HAND_STRIKE_STRENGTH = 1


def _is_ready(vampire: VampireInPlay) -> bool:
    return vampire.zone == "ready"


def _ask_strike(state: GameState, player: str, vampire: VampireInPlay) -> str:
    choices = (
        Choice("hand_strike", "Hand strike"),
        Choice("no_strike", "Do not strike this round"),
    )
    decision = Decision(
        player=player,
        kind="strike_choice",
        choices=choices,
        context={"vampire": vampire.instance_id},
    )
    return state.ask(decision).value


def _ask_press(state: GameState, player: str, vampire: VampireInPlay) -> str:
    choices = (
        Choice("press", "Press: continue combat to another round"),
        Choice("end_combat", "Do not press"),
    )
    decision = Decision(
        player=player, kind="press", choices=choices, context={"vampire": vampire.instance_id}
    )
    return state.ask(decision).value


def run_combat(
    state: GameState,
    acting_player: str,
    acting_vampire: VampireInPlay,
    blocking_player: str,
    blocking_vampire: VampireInPlay,
) -> None:
    """Resolve combat between the acting and the (successfully) blocking minion."""
    while True:
        if not (_is_ready(acting_vampire) and _is_ready(blocking_vampire)):
            break  # Rulebook SS4: combat ends at once if a combatant is no longer ready.

        # --- Strike step: acting minion's controller chooses first; simultaneous resolution. ---
        acting_choice = _ask_strike(state, acting_player, acting_vampire)
        blocking_choice = _ask_strike(state, blocking_player, blocking_vampire)

        damage_to_blocking = HAND_STRIKE_STRENGTH if acting_choice == "hand_strike" else 0
        damage_to_acting = HAND_STRIKE_STRENGTH if blocking_choice == "hand_strike" else 0

        # Simultaneous: both strikes' damage is resolved in the same step,
        # neither combatant's mend decision can react to the other's.
        if damage_to_blocking:
            apply_damage(state, blocking_player, blocking_vampire, normal=damage_to_blocking)
        if damage_to_acting:
            apply_damage(state, acting_player, acting_vampire, normal=damage_to_acting)

        if not (_is_ready(acting_vampire) and _is_ready(blocking_vampire)):
            break

        # --- Press step: the acting minion's controller always goes first
        # (Rulebook SS2 Sequencing; see module docstring / OQ-3). ---
        order = [(acting_player, acting_vampire), (blocking_player, blocking_vampire)]

        pressed = False
        for player, vampire in order:
            if _ask_press(state, player, vampire) == "press":
                pressed = True
                break
        if not pressed:
            break
