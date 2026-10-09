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

Combat-card hook wiring (`engine/hooks.py`, CLAUDE.md milestone-3 scaffolding
pass): the strike step offers each combatant's controller every registered
`"combat_strike_option"` alongside the two built-in choices (a card-granted
strike option's `apply(state)` must return the damage it inflicts, so it can
fully stand in for a hand strike -- e.g. a card that adds flat damage to a
hand strike); `"combat_strength_modifier"` is a passive, mandatory numeric
hook (CLAUDE.md rule 3 exception) summed into the base hand-strike strength,
for printed vampire abilities that are not a choice (e.g. a flat "+1
strength" line or a clan-conditional combat bonus). With no providers
registered for either hook, every strike is exactly a plain hand strike at
strength 1 -- byte-for-byte the milestone-2 result. Maneuvers, ranged
strikes, and additional strikes remain out of scope this pass (no combat
card in the current pool's classification needs them *without* also needing
the maneuver/range mechanic itself, which is a separate, larger future
engine change -- see the rules-engineer milestone-3 scaffolding report).
"""

from typing import TYPE_CHECKING

from . import hooks
from .damage import apply_damage
from .decision import Choice, Decision

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

HAND_STRIKE_STRENGTH = 1
COMBAT_STRIKE_OPTION_HOOK = "combat_strike_option"
COMBAT_STRENGTH_MODIFIER_HOOK = "combat_strength_modifier"


def _is_ready(vampire: VampireInPlay) -> bool:
    return vampire.zone == "ready"


def _strike_strength(
    state: GameState, player: str, vampire: VampireInPlay, opponent: VampireInPlay
) -> int:
    """Hand strike = base strength (default 1, Rulebook SS4 Combat) plus any
    passive `combat_strength_modifier` contribution (see module docstring)."""
    return HAND_STRIKE_STRENGTH + hooks.sum_modifiers(
        COMBAT_STRENGTH_MODIFIER_HOOK,
        state,
        player=player,
        vampire=vampire.instance_id,
        opponent=opponent.instance_id,
    )


def _ask_strike(
    state: GameState, player: str, vampire: VampireInPlay, opponent: VampireInPlay
) -> tuple[str, dict[str, hooks.HookOption]]:
    options = hooks.offer(
        COMBAT_STRIKE_OPTION_HOOK,
        state,
        player=player,
        vampire=vampire.instance_id,
        opponent=opponent.instance_id,
    )
    by_value = {o.choice.value: o for o in options}
    choices = (
        Choice("hand_strike", "Hand strike"),
        Choice("no_strike", "Do not strike this round"),
    ) + tuple(o.choice for o in options)
    decision = Decision(
        player=player,
        kind="strike_choice",
        choices=choices,
        context={"vampire": vampire.instance_id},
    )
    return state.ask(decision).value, by_value


def _strike_damage(
    state: GameState,
    choice: str,
    by_value: dict[str, hooks.HookOption],
    player: str,
    vampire: VampireInPlay,
    opponent: VampireInPlay,
) -> int:
    if choice == "hand_strike":
        return _strike_strength(state, player, vampire, opponent)
    if choice == "no_strike":
        return 0
    return by_value[choice].apply(state)  # card-granted strike option: returns its own damage


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
        acting_choice, acting_by_value = _ask_strike(
            state, acting_player, acting_vampire, blocking_vampire
        )
        blocking_choice, blocking_by_value = _ask_strike(
            state, blocking_player, blocking_vampire, acting_vampire
        )

        damage_to_blocking = _strike_damage(
            state, acting_choice, acting_by_value, acting_player, acting_vampire, blocking_vampire
        )
        damage_to_acting = _strike_damage(
            state,
            blocking_choice,
            blocking_by_value,
            blocking_player,
            blocking_vampire,
            acting_vampire,
        )

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
