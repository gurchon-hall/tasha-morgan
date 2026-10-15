"""Card-hook dispatcher: the engine's one extension point for card text. Cards
register providers via `register`; engine calls `offer`/helpers at each
decision point. Static catalogue, not game state."""

from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .decision import Choice, Decision

if TYPE_CHECKING:
    from .state import GameState

PASS_VALUE = "pass"


@dataclass(frozen=True)
class HookOption:
    """One legal, card-sourced option at a hook point. `apply` runs if chosen.
    `cost` (OQ-32) pays unconditionally, even if later canceled.
    `played_card_type` (OQ-33) names what is played, for cancel checks."""

    choice: Choice
    apply: Callable[[GameState], Any]
    cost: Callable[[GameState], Any] | None = None
    played_card_type: str | None = None


Provider = Callable[["GameState", Mapping[str, Any]], list[HookOption]]

_PROVIDERS: dict[str, list[Provider]] = defaultdict(list)


def register(hook: str, provider: Provider) -> None:
    """Register `provider` to answer `hook`. Called at card-module import time."""
    _PROVIDERS[hook].append(provider)


def unregister(hook: str, provider: Provider) -> None:
    """Remove a previously registered provider (test isolation helper)."""
    _PROVIDERS[hook].remove(provider)


def clear(hook: str | None = None) -> None:
    """Remove providers for `hook`, or all if `hook` is None (test isolation
    only). `clear(None)` wipes every real card's providers too -- prefer
    `snapshot()`/`restore()` for test isolation instead."""
    if hook is None:
        _PROVIDERS.clear()
    else:
        _PROVIDERS.pop(hook, None)


def snapshot() -> dict[str, list[Provider]]:
    """Capture the catalogue so `restore()` can undo a test's own
    registrations without disturbing other hooks (test isolation helper;
    see `clear()`)."""
    return {hook: list(providers) for hook, providers in _PROVIDERS.items()}


def restore(snapshot: dict[str, list[Provider]]) -> None:
    """Replace the catalogue with a previous `snapshot()`, undoing
    `register()`/`clear()` calls since (standard snapshot-before/
    restore-after test fixture pattern)."""
    _PROVIDERS.clear()
    _PROVIDERS.update(snapshot)


def offer(hook: str, state: GameState, **context: Any) -> list[HookOption]:
    """Collect every legal `HookOption` any registered provider offers right now."""
    options: list[HookOption] = []
    for provider in _PROVIDERS.get(hook, ()):
        options.extend(provider(state, context))
    return options


def ensure_unique_choice_values(choices: Iterable[Choice], *, decision_kind: str) -> None:
    """Raise if two `Choice`s share a `.value`. Prevents a hook-provided value
    from silently shadowing a hardcoded one (OQ-24) -- call once on the full
    choice set before building a `Decision`."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for choice in choices:
        if choice.value in seen:
            duplicates.add(choice.value)
        seen.add(choice.value)
    if duplicates:
        raise ValueError(
            f"{decision_kind!r} decision: duplicate choice value(s) "
            f"{sorted(duplicates)} offered from more than one source"
        )


PENDING_CONTEXT_KEY = "pending"
"""Convention key (OQ-11) a hook `context` carries its shared, action-scoped
scratch dict under -- excluded from `Decision.context` by
`sanitize_decision_context` below."""


def sanitize_decision_context(context: Mapping[str, Any]) -> dict[str, Any]:
    """Strip `PENDING_CONTEXT_KEY` from a hook `context` before it reaches
    `Decision.context` -- `pending` is live engine-internal scratch (may
    hold a `Callable`, OQ-30), not for agent reasoning (CLAUDE.md)."""
    return {key: value for key, value in context.items() if key != PENDING_CONTEXT_KEY}


CANCEL_AS_PLAYED_HOOK = "cancel_as_played"
"""Mirrors `cards/registry.py::Hook.CANCEL_AS_PLAYED`'s own string value --
see `apply_chosen_option` below for the dispatch this now drives (OQ-32)."""


def apply_chosen_option(
    state: GameState,
    option: HookOption,
    played_by: str,
    may_cancel: str,
    context: Mapping[str, Any],
) -> Any:
    """Interception point for cancel-as-played (OQ-32). Runs `option.cost`
    unconditionally, then offers `may_cancel` `CANCEL_AS_PLAYED_HOOK`; if
    used, `option.apply` is suppressed, else it runs normally."""
    if option.cost is not None:
        option.cost(state)
        if state.game_over:
            return None
    cancel_context = {
        **context,
        "canceled_by": played_by,
        "canceled_choice": option.choice.value,
        "canceled_card_type": option.played_card_type,
    }
    cancel_options = offer(CANCEL_AS_PLAYED_HOOK, state, player=may_cancel, **cancel_context)
    if cancel_options:
        by_value = {o.choice.value: o for o in cancel_options}
        choices = tuple(o.choice for o in cancel_options) + (Choice(PASS_VALUE, "Pass"),)
        decision = Decision(
            player=may_cancel,
            kind=CANCEL_AS_PLAYED_HOOK,
            choices=choices,
            context=sanitize_decision_context(cancel_context),
        )
        answer = state.ask(decision)
        if answer.value != PASS_VALUE:
            by_value[answer.value].apply(state)
            return None
    return option.apply(state)


def offer_until_pass(
    state: GameState,
    hook: str,
    player: str,
    context: Mapping[str, Any],
    decision_kind: str | None = None,
) -> None:
    """Single-sided loop: offer `player` every `HookOption` for `hook`, plus
    pass, until they pass or none remain. Each choice resolves via
    `apply_chosen_option` so the other side can cancel it."""
    while not state.game_over:
        options = offer(hook, state, player=player, **context)
        if not options:
            return
        by_value = {o.choice.value: o for o in options}
        choices = tuple(o.choice for o in options) + (Choice(PASS_VALUE, "Pass"),)
        decision = Decision(
            player=player,
            kind=decision_kind or hook,
            choices=choices,
            context=sanitize_decision_context(context),
        )
        answer = state.ask(decision)
        if answer.value == PASS_VALUE:
            return
        apply_chosen_option(
            state, by_value[answer.value], player, state.other_player(player), context
        )


def resolve_impulse_window(
    state: GameState,
    hook: str,
    acting_player: str,
    other_player: str,
    context: Mapping[str, Any],
    decision_kind: str | None = None,
) -> None:
    """Two-sided impulse window (Rulebook §2 Sequencing): offers `hook` to
    `acting_player` then `other_player`, alternating; using an option resets
    to `acting_player`; ends once both pass in succession."""
    turn = acting_player
    consecutive_passes = 0
    while consecutive_passes < 2 and not state.game_over:
        options = offer(hook, state, player=turn, **context)
        if not options:
            consecutive_passes += 1
            turn = other_player if turn == acting_player else acting_player
            continue
        by_value = {o.choice.value: o for o in options}
        choices = tuple(o.choice for o in options) + (Choice(PASS_VALUE, "Pass"),)
        decision = Decision(
            player=turn,
            kind=decision_kind or hook,
            choices=choices,
            context=sanitize_decision_context(context),
        )
        answer = state.ask(decision)
        if answer.value == PASS_VALUE:
            consecutive_passes += 1
        else:
            consecutive_passes = 0
            may_cancel = other_player if turn == acting_player else acting_player
            apply_chosen_option(state, by_value[answer.value], turn, may_cancel, context)
            turn = acting_player
            continue
        turn = other_player if turn == acting_player else acting_player


def sum_modifiers(hook: str, state: GameState, **context: Any) -> int:
    """Passive numeric-modifier hook: sums every provider's contribution for
    a mandatory, non-chosen effect (CLAUDE.md rule 3). Providers are plain
    callables returning 0 when they don't apply."""
    total = 0
    for provider in _PROVIDERS.get(hook, ()):
        total += provider(state, context)  # type: ignore[arg-type]
    return total


def run_effects(hook: str, state: GameState, **context: Any) -> None:
    """Mandatory, non-chosen per-provider side-effect dispatch: calls every
    provider once, in order; each may mutate `state` directly. Stops once
    `state.game_over` (Rulebook §5)."""
    for provider in _PROVIDERS.get(hook, ()):
        if state.game_over:
            return
        provider(state, context)  # type: ignore[arg-type]


def union_modifiers(hook: str, state: GameState, **context: Any) -> tuple[Any, ...]:
    """Set-valued counterpart to `sum_modifiers`: unions every provider's
    contribution (e.g. discipline-level codes). Returns a sorted tuple, not
    a frozenset, for determinism (CLAUDE.md §5)."""
    result: set[Any] = set()
    for provider in _PROVIDERS.get(hook, ()):
        result.update(provider(state, context))  # type: ignore[arg-type]
    return tuple(sorted(result))
