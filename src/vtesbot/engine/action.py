"""Minion action: announce, block, resolve/combat (Rulebook §4; 2P collapses
prey/predator, CLAUDE.md §3). See OQ-9,11,17,25,26,30,31,34,36,39,46,48."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import hooks
from .combat import run_combat, seed_pre_combat_maneuver_grant
from .decision import Choice, Decision

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

STEALTH_MODIFIER_HOOK = "stealth_modifier"
INTERCEPT_MODIFIER_HOOK = "intercept_modifier"
BLOCK_CANDIDATE_INJECTION_HOOK = "block_candidate_injection"
"""OQ-26: mirrors `Hook.BLOCK_CANDIDATE_INJECTION`. `apply()` must unlock
the vampire and return it as an unconditional successful block."""

INTERCEPT_DECREASE_HOOK = "intercept_decrease"
"""OQ-30/31: mirrors `Hook.INTERCEPT_DECREASE`. Offered to `actor`
proactively and reactively; `apply()` appends an `ActiveInterceptDecrease`
to `pending`, not a delta."""

PENDING_INTERCEPT_DECREASE_KEY = "intercept_decrease_modifiers"
"""`pending[...]` key (OQ-30): holds a `list[ActiveInterceptDecrease]`,
appended to (never replaced) by each activated `INTERCEPT_DECREASE_HOOK`
option's own `apply` closure."""

STEALTH_INCREASE_HOOK = "stealth_increase"
"""OQ-39: `INTERCEPT_DECREASE_HOOK`'s sibling for actor's stealth.
`apply()` appends an `ActiveStealthIncrease` to `pending`; no `qualifies`
predicate needed."""

PENDING_STEALTH_INCREASE_KEY = "stealth_increase_modifiers"
"""`pending[...]` key (OQ-39): holds a `list[ActiveStealthIncrease]`,
appended to (never replaced) by each activated `STEALTH_INCREASE_HOOK`
option's own `apply` closure."""

WAKE_LOCKED_MINION_HOOK = "wake_locked_minion"
"""OQ-48: defender-side sibling of `INTERCEPT_DECREASE_HOOK`/
`STEALTH_INCREASE_HOOK`. `apply()` sets `woken = True` on a locked
vampire; block stays fully contestable."""


@dataclass(frozen=True)
class ActiveInterceptDecrease:
    """One Action Modifier's persistent intercept decrease (OQ-30). `delta`
    applies while `qualifies(blocker)` matches; never floored at 0
    (Rulebook §4)."""

    delta: int
    qualifies: Callable[[VampireInPlay], bool]


@dataclass(frozen=True)
class ActiveStealthIncrease:
    """One Action Modifier's persistent stealth increase (OQ-39). `delta`
    adds to `base_stealth` unconditionally; never floored at 0 (Rulebook
    §4)."""

    delta: int


def _active_stealth_increase(pending: dict[str, Any] | None) -> int:
    """Sum every `ActiveStealthIncrease` (OQ-39) in `pending`; mirrors
    `_active_intercept_decrease` minus the per-candidate `qualifies` filter."""
    if not pending:
        return 0
    modifiers: list[ActiveStealthIncrease] = pending.get(PENDING_STEALTH_INCREASE_KEY, [])
    return sum(modifier.delta for modifier in modifiers)


ACTION_BLEED = "bleed"
ACTION_HUNT = "hunt"
ACTION_RECRUIT_ALLY = "recruit_ally"
ACTION_POLITICAL = "political_action"
ACTION_ACTION_CARD = "action_card"
ACTION_DIABLERIE = "diablerise"
"""Action discriminator constants (OQ-9) for `action=` passed to
`attempt_block`/`perform_minion_action`."""

ACTION_SUCCEEDED_HOOK = "action_succeeded"
"""OQ-34: mirrors `Hook.ACTION_SUCCEEDED`. Rulebook §4: success means not
blocked. Dispatched via `run_effects` after `resolve(pending)`; never on
the blocked branch."""

PENDING_REFERENDUM_RESULT_KEY = "referendum_result"
"""Mirrors `politics.py::REFERENDUM_RESULT_KEY` (duplicated, not imported,
to avoid a circular import). See `REFERENDUM_RESOLVED_HOOK` below."""

REFERENDUM_RESOLVED_HOOK = "referendum_resolved"
"""OQ-36: mirrors `Hook.REFERENDUM_RESOLVED`, strictly after a political
action's `resolve()` returns, only if it passed; dispatched via
`resolve_impulse_window`."""


def clear_woken_vampires(state: GameState) -> None:
    """Clear `VampireInPlay.woken` for both players (OQ-46), On the Qui
    Vive's end-of-action scope. Called from every `perform_minion_action`
    exit."""
    for player_state in state.players.values():
        for vampire in player_state.vampires.values():
            vampire.woken = False


def _active_intercept_decrease(pending: dict[str, Any] | None, blocker: VampireInPlay) -> int:
    """Sum every `ActiveInterceptDecrease` (OQ-30) in `pending` whose
    `qualifies` matches `blocker`, right now -- never cached, so a retried
    attempt (OQ-11) against a different `blocker` is re-checked fresh."""
    if not pending:
        return 0
    modifiers: list[ActiveInterceptDecrease] = pending.get(PENDING_INTERCEPT_DECREASE_KEY, [])
    return sum(modifier.delta for modifier in modifiers if modifier.qualifies(blocker))


def _duel_stealth_intercept(
    state: GameState,
    actor: str,
    defender: str,
    base_stealth: int,
    acting_vampire: VampireInPlay | None,
    blocker: VampireInPlay,
    action: str | None = None,
    directed: bool | None = None,
    pending: dict[str, Any] | None = None,
) -> tuple[int, int]:
    """Resolve the stealth/intercept ping-pong for one block attempt.
    Baselines fold active `ActiveInterceptDecrease`/`ActiveStealthIncrease`
    (OQ-30/39)."""
    stealth = base_stealth + _active_stealth_increase(pending)
    intercept = _active_intercept_decrease(pending, blocker)
    context = {
        "actor": actor,
        "defender": defender,
        "acting_vampire": acting_vampire.instance_id if acting_vampire is not None else None,
        "blocking_vampire": blocker.instance_id,
        "action": action,
        "directed": directed,
        "pending": pending,
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
            if delta is None or state.game_over:
                return stealth, intercept
            intercept += delta
        else:
            # Block currently succeeds: stealth may be added, only now
            # needed (OQ-31/39: actor may also decrease intercept or
            # increase stealth here, reactively; see _ask_stealth_or_modifier).
            stealth_options = hooks.offer(
                STEALTH_MODIFIER_HOOK,
                state,
                player=actor,
                stealth=stealth,
                intercept=intercept,
                **context,
            )
            decrease_options = hooks.offer(
                INTERCEPT_DECREASE_HOOK,
                state,
                player=actor,
                stealth=stealth,
                intercept=intercept,
                **context,
            )
            increase_options = hooks.offer(
                STEALTH_INCREASE_HOOK,
                state,
                player=actor,
                stealth=stealth,
                intercept=intercept,
                **context,
            )
            if not stealth_options and not decrease_options and not increase_options:
                return stealth, intercept
            chosen = _ask_stealth_or_modifier(
                state, actor, stealth_options, decrease_options, increase_options, context
            )
            if chosen is None:
                return stealth, intercept
            option, kind = chosen
            if kind == "intercept_decrease":
                option.apply(state)
                if state.game_over:
                    return stealth, intercept
                # Re-evaluated fresh, same as the baseline at the top of
                # this function: never cached (OQ-11).
                intercept = _active_intercept_decrease(pending, blocker)
            elif kind == "stealth_increase":
                option.apply(state)
                stealth = base_stealth + _active_stealth_increase(pending)
            else:
                stealth += option.apply(state)
                if state.game_over:
                    return stealth, intercept


def _ask_modifier(
    state: GameState,
    player: str,
    hook_name: str,
    options: list[hooks.HookOption],
    context: dict,
) -> int | None:
    """Offer `options` plus decline; return the applied delta or None.
    Sanitizes context (OQ-30) since `pending` must never reach an agent."""
    by_value = {o.choice.value: o for o in options}
    choices = tuple(o.choice for o in options) + (Choice("decline", "Decline"),)
    decision = Decision(
        player=player,
        kind=hook_name,
        choices=choices,
        context=hooks.sanitize_decision_context(context),
    )
    answer = state.ask(decision)
    if answer.value == "decline":
        return None
    return by_value[answer.value].apply(state)


def _ask_stealth_or_modifier(
    state: GameState,
    actor: str,
    stealth_options: list[hooks.HookOption],
    decrease_options: list[hooks.HookOption],
    increase_options: list[hooks.HookOption],
    context: dict,
) -> tuple[hooks.HookOption, str] | None:
    """Merge `STEALTH_MODIFIER_HOOK`/`INTERCEPT_DECREASE_HOOK`/
    `STEALTH_INCREASE_HOOK` into one `Decision` (OQ-31/39). Returns
    `(option, kind)` or `None`."""
    decrease_values = {o.choice.value for o in decrease_options}
    increase_values = {o.choice.value for o in increase_options}
    by_value = {o.choice.value: o for o in stealth_options}
    by_value.update({o.choice.value: o for o in decrease_options})
    by_value.update({o.choice.value: o for o in increase_options})
    choices = (
        tuple(o.choice for o in stealth_options)
        + tuple(o.choice for o in decrease_options)
        + tuple(o.choice for o in increase_options)
        + (Choice("decline", "Decline"),)
    )
    hooks.ensure_unique_choice_values(choices, decision_kind=STEALTH_MODIFIER_HOOK)
    decision = Decision(
        player=actor,
        kind=STEALTH_MODIFIER_HOOK,
        choices=choices,
        context=hooks.sanitize_decision_context(context),
    )
    answer = state.ask(decision)
    if answer.value == "decline":
        return None
    option = by_value[answer.value]
    if answer.value in decrease_values:
        return option, "intercept_decrease"
    if answer.value in increase_values:
        return option, "stealth_increase"
    return option, "stealth_delta"


def attempt_block(
    state: GameState,
    actor: str,
    defender: str,
    base_stealth: int,
    acting_vampire: VampireInPlay | None = None,
    action: str | None = None,
    directed: bool | None = None,
    pending: dict[str, Any] | None = None,
) -> VampireInPlay | None:
    """Offer `defender` a block with a ready unlocked vampire. Returns the
    blocker on success, None on decline; loops on failed attempts
    (Rulebook §4)."""
    if pending is None:
        pending = {}
    while not state.game_over:
        proactive_context = {
            "actor": actor,
            "defender": defender,
            "acting_vampire": acting_vampire.instance_id if acting_vampire is not None else None,
            "action": action,
            "directed": directed,
            "base_stealth": base_stealth,
            "pending": pending,
        }
        hooks.offer_until_pass(state, INTERCEPT_DECREASE_HOOK, actor, proactive_context)
        if state.game_over:
            return None
        hooks.offer_until_pass(state, STEALTH_INCREASE_HOOK, actor, proactive_context)
        if state.game_over:
            return None
        hooks.offer_until_pass(state, WAKE_LOCKED_MINION_HOOK, defender, proactive_context)
        if state.game_over:
            return None
        candidates = state.ready_unlocked_vampires(defender)
        candidate_choices = tuple(
            Choice(f"block_with:{v.instance_id}", f"Block with {v.card.name}") for v in candidates
        )

        injected_options = hooks.offer(
            BLOCK_CANDIDATE_INJECTION_HOOK,
            state,
            player=defender,
            actor=actor,
            defender=defender,
            acting_vampire=acting_vampire.instance_id if acting_vampire is not None else None,
            action=action,
            directed=directed,
            base_stealth=base_stealth,
            pending=pending,
        )
        by_injected_value = {o.choice.value: o for o in injected_options}

        offered_choices = candidate_choices + tuple(o.choice for o in injected_options)
        if not offered_choices:
            return None  # nothing legal to block with: no vacuous decision raised.

        choices = offered_choices + (Choice("decline", "Decline to block"),)
        hooks.ensure_unique_choice_values(choices, decision_kind="block_attempt")
        decision = Decision(
            player=defender,
            kind="block_attempt",
            choices=choices,
            context={
                "actor": actor,
                "base_stealth": base_stealth,
                "action": action,
                "directed": directed,
            },
        )
        choice = state.ask(decision)
        if choice.value == "decline":
            return None

        if choice.value in by_injected_value:
            # OQ-26: an immediate, unconditional successful block -- never
            # runs the stealth/intercept ping-pong for this candidate.
            injected_blocker = by_injected_value[choice.value].apply(state)
            return None if state.game_over else injected_blocker

        instance_id = choice.value.split(":", 1)[1]
        blocker = state.players[defender].vampires[instance_id]

        stealth, intercept = _duel_stealth_intercept(
            state,
            actor,
            defender,
            base_stealth,
            acting_vampire,
            blocker,
            action=action,
            directed=directed,
            pending=pending,
        )
        if state.game_over:
            return None
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
    resolve: Callable[[dict[str, Any]], None],
    action: str | None = None,
    directed: bool | None = None,
    on_blocked: Callable[[dict[str, Any]], None] | None = None,
    maneuver_grant: str | None = None,
) -> None:
    """Announce, block attempt, resolve or combat (Rulebook §4). Dispatches
    `ACTION_SUCCEEDED_HOOK` (OQ-34) then `REFERENDUM_RESOLVED_HOOK`
    (OQ-36)."""
    vampire.locked = True
    pending: dict[str, Any] = {}
    blocker = attempt_block(
        state,
        actor_player,
        defender_player,
        base_stealth,
        vampire,
        action=action,
        directed=directed,
        pending=pending,
    )
    if state.game_over:
        clear_woken_vampires(state)
        return
    if blocker is not None:
        blocker.locked = True
        initial_combat_state = (
            seed_pre_combat_maneuver_grant(maneuver_grant) if maneuver_grant is not None else None
        )
        run_combat(state, actor_player, vampire, defender_player, blocker, initial_combat_state)
        if state.game_over:
            clear_woken_vampires(state)
            return
        if on_blocked is not None:
            on_blocked(pending)
        clear_woken_vampires(state)
        return
    resolve(pending)
    hooks.run_effects(
        ACTION_SUCCEEDED_HOOK,
        state,
        actor_player=actor_player,
        vampire=vampire,
        action=action,
    )
    if action == ACTION_POLITICAL:
        result = pending.get(PENDING_REFERENDUM_RESULT_KEY)
        if result is not None and result["passed"]:
            hooks.resolve_impulse_window(
                state,
                REFERENDUM_RESOLVED_HOOK,
                actor_player,
                defender_player,
                context={
                    "caller": actor_player,
                    "other": defender_player,
                    "caller_vampire_id": vampire.instance_id,
                    "margin": result["votes_for"] - result["votes_against"],
                    "pending": pending,
                },
            )
    clear_woken_vampires(state)
