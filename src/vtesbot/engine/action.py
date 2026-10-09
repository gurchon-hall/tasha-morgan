"""Generic course of a minion-phase action: announce -> block attempt -> resolve.

Source: Rulebook SS4 Minion Phase (per the `vtes-rules-reference` skill
condensed mapping):
  1. "Announce (all terms fixed now ...), lock the acting minion."
  2. "Block attempts: directed action -> only the targeted Methuselah may
     block; undirected -> prey first, then predator. In 2P the opponent is
     both. Block succeeds if intercept >= stealth. Stealth may be added only
     when needed ...; intercept only when needed .... Declining to block is
     final unless the target changes."
  3. "If unblocked -> pay cost, resolve. If blocked -> action card burned,
     cost not paid, blocker locks, combat."

2P structural consequence (CLAUDE.md SS3, settled core structural rule, not
OQ-1 which is scoped to card-text wording): with exactly two Methuselahs,
the sole opponent is simultaneously prey and predator. The rulebook's
"prey first, then predator" sequencing exists to give each of several
*different* Methuselahs a chance to block in turn; when both roles are held
by the same single Methuselah there is only one decision-maker and no new
information arrives between a hypothetical "as prey" and "as predator" ask,
so this implementation collapses both directed and undirected actions to a
single block-attempt decision offered to that one opponent.

Stealth/intercept hook wiring (`engine/hooks.py`): "Stealth may be added
only when needed (an ongoing block would succeed); intercept only when
needed (acting stealth exceeds it)" (Rulebook SS4 Minion Phase, per the
`vtes-rules-reference` skill condensed mapping) is a strict ping-pong, not
the general "both sides get a turn" impulse window: the *blocking*
Methuselah may add intercept only while the attempt is currently failing
(stealth > intercept); the *acting* Methuselah may add stealth only while
the attempt is currently succeeding (intercept >= stealth). `_duel_stealth_
intercept` below implements exactly that alternation via the
`"stealth_modifier"` / `"intercept_modifier"` hooks; with no providers
registered for either hook (no stealth/intercept library cards implemented
yet), each offer is empty and the loop terminates immediately at
(stealth=base_stealth, intercept=0) -- byte-for-byte the milestone-2 result,
so this wiring is pure scaffolding until a card registers against one of
these hooks.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

from . import hooks
from .combat import run_combat
from .decision import Choice, Decision

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

STEALTH_MODIFIER_HOOK = "stealth_modifier"
INTERCEPT_MODIFIER_HOOK = "intercept_modifier"


def _duel_stealth_intercept(
    state: GameState,
    actor: str,
    defender: str,
    base_stealth: int,
    acting_vampire: VampireInPlay | None,
    blocker: VampireInPlay,
) -> tuple[int, int]:
    """Resolve the "only when needed" stealth/intercept ping-pong for one
    block attempt against `blocker` (see module docstring)."""
    stealth = base_stealth
    intercept = 0
    context = {
        "actor": actor,
        "defender": defender,
        "acting_vampire": acting_vampire.instance_id if acting_vampire is not None else None,
        "blocking_vampire": blocker.instance_id,
    }
    while True:
        if stealth > intercept:
            # Block currently fails: intercept may be added, only now needed.
            options = hooks.offer(
                INTERCEPT_MODIFIER_HOOK,
                state,
                player=defender,
                stealth=stealth,
                intercept=intercept,
                **context,
            )
            if not options:
                return stealth, intercept
            delta = _ask_modifier(state, defender, INTERCEPT_MODIFIER_HOOK, options, context)
            if delta is None:
                return stealth, intercept
            intercept += delta
        else:
            # Block currently succeeds: stealth may be added, only now needed.
            options = hooks.offer(
                STEALTH_MODIFIER_HOOK,
                state,
                player=actor,
                stealth=stealth,
                intercept=intercept,
                **context,
            )
            if not options:
                return stealth, intercept
            delta = _ask_modifier(state, actor, STEALTH_MODIFIER_HOOK, options, context)
            if delta is None:
                return stealth, intercept
            stealth += delta


def _ask_modifier(
    state: GameState,
    player: str,
    hook_name: str,
    options: list[hooks.HookOption],
    context: dict,
) -> int | None:
    """Offer `options` plus a decline choice; return the applied delta, or
    None if the player declines (the hook's `apply` must return an `int`)."""
    by_value = {o.choice.value: o for o in options}
    choices = tuple(o.choice for o in options) + (Choice("decline", "Decline"),)
    decision = Decision(player=player, kind=hook_name, choices=choices, context=dict(context))
    answer = state.ask(decision)
    if answer.value == "decline":
        return None
    return by_value[answer.value].apply(state)


def attempt_block(
    state: GameState,
    actor: str,
    defender: str,
    base_stealth: int,
    acting_vampire: VampireInPlay | None = None,
) -> VampireInPlay | None:
    """Offer `defender` the chance to block with a ready, unlocked vampire.

    Returns the blocking vampire if a block *succeeds* (intercept >=
    stealth); returns None once the defender declines. Rulebook SS4: "If one
    attempt to block fails, another can be made as often as the blocking
    Methuselah wishes" -- a *failed* attempt (stealth exceeds intercept) does
    not end the block-attempt window and does not lock the failed vampire
    (see OQ-5 on that specific lock-timing reading); the defender is
    re-offered the choice of another candidate vampire or declining, looping
    until they decline or a block succeeds. This is the "three states: no
    current block attempt / ongoing block attempt / blocks declined by all"
    model named by the `vtes-rules-reference` skill.
    """
    while True:
        candidates = state.ready_unlocked_vampires(defender)
        if not candidates:
            return None  # nothing legal to block with: no vacuous decision raised.

        choices = tuple(
            Choice(f"block_with:{v.instance_id}", f"Block with {v.card.name}") for v in candidates
        ) + (Choice("decline", "Decline to block"),)
        decision = Decision(
            player=defender,
            kind="block_attempt",
            choices=choices,
            context={"actor": actor, "base_stealth": base_stealth},
        )
        choice = state.ask(decision)
        if choice.value == "decline":
            return None

        instance_id = choice.value.split(":", 1)[1]
        blocker = state.players[defender].vampires[instance_id]

        stealth, intercept = _duel_stealth_intercept(
            state, actor, defender, base_stealth, acting_vampire, blocker
        )
        if intercept >= stealth:
            return blocker
        # Failed attempt: does not lock the blocker, does not end the
        # window -- loop back and re-offer another attempt or decline.


def perform_minion_action(
    state: GameState,
    actor_player: str,
    defender_player: str,
    vampire: VampireInPlay,
    base_stealth: int,
    resolve: Callable[[], None],
) -> None:
    """Announce (lock) -> block attempt -> resolve-or-combat (Rulebook SS4).

    `resolve` is called only if the action goes unblocked (declined or
    evaded); it must perform the action's own effect (e.g. bleed/hunt).
    """
    vampire.locked = True
    blocker = attempt_block(state, actor_player, defender_player, base_stealth, vampire)
    if blocker is not None:
        blocker.locked = True
        run_combat(state, actor_player, vampire, defender_player, blocker)
        return
    resolve()
