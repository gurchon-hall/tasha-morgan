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
    `cost` (ENG-022) pays unconditionally, even if later canceled.
    `played_card_type` (ENG-023) names what is played, for cancel checks.
    `block_candidate_instance_id`: required on every option offered under
    `engine/action.py::BLOCK_CANDIDATE_INJECTION_HOOK` -- the instance id of
    the specific vampire that option would unlock and return as a block
    candidate. `attempt_block` filters injected options against its own
    exclusion set (`BLOCK_CANDIDATE_EXCLUSION_HOOK`) by this id before
    offering them, so a named-and-excluded vampire (e.g.
    `cards/sleeping_mind.py`) cannot be forced back in as an injected
    candidate (rules-auditor finding: this filter previously only covered
    the hardcoded `ready_unlocked_vampires` candidate list, not injected
    ones)."""

    choice: Choice
    apply: Callable[[GameState], Any]
    cost: Callable[[GameState], Any] | None = None
    played_card_type: str | None = None
    block_candidate_instance_id: str | None = None


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
    from silently shadowing a hardcoded one (ENG-016) -- call once on the full
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
"""Convention key (ENG-005) a hook `context` carries its shared, action-scoped
scratch dict under -- excluded from `Decision.context` by
`sanitize_decision_context` below."""


def sanitize_decision_context(context: Mapping[str, Any]) -> dict[str, Any]:
    """Strip `PENDING_CONTEXT_KEY` from a hook `context` before it reaches
    `Decision.context` -- `pending` is live engine-internal scratch (may
    hold a `Callable`, ENG-021), not for agent reasoning (CLAUDE.md)."""
    return {key: value for key, value in context.items() if key != PENDING_CONTEXT_KEY}


CANCEL_AS_PLAYED_HOOK = "cancel_as_played"
"""Mirrors `cards/registry.py::Hook.CANCEL_AS_PLAYED`'s own string value --
see `apply_chosen_option` below for the dispatch this now drives (ENG-022)."""

PENDING_REACTION_PLAYED_KEY = "reaction_played"
"""`pending[...]` key: set `True` the moment a Reaction-type `HookOption`
is chosen, even if it is later canceled as played ([LSJ 20070330] --
cancellation still counts as having been played). Needed by
`cards/perfectionist.py` (krcg 101388)'s "no reaction cards were played"
gate, read via `engine/action.py::perform_minion_action`'s own
`ACTION_SUCCEEDED_HOOK` dispatch forwarding `pending`."""


def mark_reaction_played(pending: dict[str, Any] | None, option: HookOption) -> None:
    """Records a chosen Reaction-type `option` into `pending`
    (`PENDING_REACTION_PLAYED_KEY`), if an action-scoped `pending` dict is
    being tracked at all. A no-op for any other `played_card_type`. Every
    `option.apply` call site that resolves a choice made during an
    action's own action-scoped `pending` tracking must call this (directly,
    or via `apply_chosen_option` below) before applying -- as of this
    writing that is: `apply_chosen_option` itself (the choke point for
    `offer_until_pass`/`resolve_impulse_window`), `engine/action.py::
    _ask_modifier`, `engine/action.py::_ask_stealth_or_modifier`,
    `engine/action.py::attempt_block`'s `BLOCK_CANDIDATE_INJECTION_HOOK`
    branch, and `engine/politics.py::_cast_votes`'s mid-cast cancel-choice
    branch -- five call sites, not a single one; `.apply(` call sites
    outside this action-scoped `pending` tracking mechanism (master phase,
    influence phase, unlock phase, combat's own strike/dodge/maneuver
    choices) are a different mechanism and out of scope here (rules-auditor
    review)."""
    if pending is not None and option.played_card_type == "Reaction":
        pending[PENDING_REACTION_PLAYED_KEY] = True


def offer_cancel_as_played(
    state: GameState,
    option: HookOption,
    played_by: str,
    may_cancel: str,
    context: Mapping[str, Any] | None = None,
) -> bool:
    """Offer `may_cancel` a chance to cancel `option` -- already chosen by
    `played_by` -- "as it is played" (Rulebook Advanced Rules "Reflex
    cards", `data/sources/rulebook/2026-10-09/2-card-types.md:323-326`:
    "A minion can play a reflex card to cancel a specified kind of card
    played against them as it is played."). Returns True once a canceling
    option is chosen (its own `apply` has already run); False if
    `may_cancel` passes or no `CANCEL_AS_PLAYED_HOOK` provider offers
    anything. Caller decides what "canceled" means for `option` itself --
    this only runs the canceling side's own effect.

    Shared by `apply_chosen_option` below (ENG-022: a `HookOption` whose own
    `cost` is paid unconditionally first, matching "If a non-action card is
    cancelled, its cost should be paid as normal", `3-playing-the-game.md:
    103-108`) and `engine/phases/minion.py::_perform_action_card` (ENG-037: an
    Action card has no such `cost` field to pay at all -- its own printed
    cost lives inside `ActionCardSpec.resolve`, paid only on the unblocked
    branch, so skipping `option.apply`'s caller entirely already matches
    "they do not pay for the action card")."""
    cancel_context = {
        **(context or {}),
        "canceled_by": played_by,
        "canceled_choice": option.choice.value,
        "canceled_card_type": option.played_card_type,
    }
    cancel_options = offer(CANCEL_AS_PLAYED_HOOK, state, player=may_cancel, **cancel_context)
    if not cancel_options:
        return False
    by_value = {o.choice.value: o for o in cancel_options}
    choices = tuple(o.choice for o in cancel_options) + (Choice(PASS_VALUE, "Pass"),)
    decision = Decision(
        player=may_cancel,
        kind=CANCEL_AS_PLAYED_HOOK,
        choices=choices,
        context=sanitize_decision_context(cancel_context),
    )
    answer = state.ask(decision)
    if answer.value == PASS_VALUE:
        return False
    by_value[answer.value].apply(state)
    return True


def apply_chosen_option(
    state: GameState,
    option: HookOption,
    played_by: str,
    may_cancel: str,
    context: Mapping[str, Any],
) -> Any:
    """Interception point for cancel-as-played (ENG-022). Runs `option.cost`
    unconditionally, then offers `may_cancel` `CANCEL_AS_PLAYED_HOOK` via
    `offer_cancel_as_played`; if used, `option.apply` is suppressed, else it
    runs normally. Records a Reaction-type `option` as played
    (`mark_reaction_played`) before any of that, since the card has been
    played the moment it is chosen, regardless of cost/cancel outcome."""
    mark_reaction_played(context.get(PENDING_CONTEXT_KEY), option)
    if option.cost is not None:
        option.cost(state)
        if state.game_over:
            return None
    if offer_cancel_as_played(state, option, played_by, may_cancel, context):
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


def any_true(hook: str, state: GameState, **context: Any) -> bool:
    """Passive boolean hook (mirrors `sum_modifiers`/`union_modifiers`): True the moment any
    provider's contribution for a mandatory, non-chosen fact is truthy (CLAUDE.md rule 3
    exception, same as `attachments.py::CAPACITY_MODIFIER_HOOK`). Providers are plain
    callables returning a falsy value when they don't apply; short-circuits like `any()`."""
    for provider in _PROVIDERS.get(hook, ()):
        if provider(state, context):  # type: ignore[arg-type]
            return True
    return False


def collect(hook: str, state: GameState, **context: Any) -> list[Any]:
    """Passive hook whose providers return an arbitrary per-provider value
    (not a `HookOption`): each provider returns `None` to mean "does not
    apply right now" (dropped), or any other value to contribute -- unlike
    `sum_modifiers`/`union_modifiers`, which fix the combining operation
    (add / union) and so require every provider to return a homogeneous
    numeric/iterable contribution. Needed where a provider's contribution is
    itself a small record a caller must act on individually (e.g.
    `engine/action.py::BLOCK_ATTEMPT_COST_HOOK`'s `BlockAttemptCost`, one
    per candidate, carrying its own `can_pay`/`pay` rather than folding into
    one combined total)."""
    results: list[Any] = []
    for provider in _PROVIDERS.get(hook, ()):
        value = provider(state, context)  # type: ignore[arg-type]
        if value is not None:
            results.append(value)
    return results


def union_modifiers(hook: str, state: GameState, **context: Any) -> tuple[Any, ...]:
    """Set-valued counterpart to `sum_modifiers`: unions every provider's
    contribution (e.g. discipline-level codes). Returns a sorted tuple, not
    a frozenset, for determinism (CLAUDE.md §5)."""
    result: set[Any] = set()
    for provider in _PROVIDERS.get(hook, ()):
        result.update(provider(state, context))  # type: ignore[arg-type]
    return tuple(sorted(result))
