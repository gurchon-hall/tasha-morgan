"""Generic card-hook dispatcher: the engine's one extension point for card text.

CLAUDE.md SS5/SS6: "Card hooks. The engine exposes hooks/events; card-specific
behaviour lives in `src/vtesbot/cards/`. Do not special-case card names in the
engine." Every rules-sourced moment where a *card* (library card or printed
vampire ability) might add a legal option -- "only when needed" stealth/
intercept (Rulebook SS4 Minion Phase > Block Attempts), a bleed-amount
modifier, a master-phase play, a damage-prevention effect, a combat strike
option, a passive numeric modifier (e.g. strike strength) -- is named here as
a `hook`. `src/vtesbot/cards/<card>.py` modules call `register(hook, provider)`
at import time; `engine/` code calls `offer(...)` (or one of the two generic
decision-loop helpers below) at the exact moment the rule says the option may
be used. No providers registered for a hook => `offer` returns an empty list
=> the call site raises no decision at all (the project's "only when needed"
/ "never a vacuous Decision" invariant, already used throughout `engine/`),
so wiring these hooks into `engine/` changes no behaviour until a card
actually registers against one.

This is a *static catalogue* of card behaviour (which hooks exist and which
providers answer to them), populated once at import time by `cards/__init__.py`
-- analogous to `src/vtesbot/cards/registry.py`'s catalogue of implemented
cards, or Python's own stdlib plugin-registration patterns. It is not
*game* state (CLAUDE.md SS5 "no global state" targets the mutable, in-game,
seeded `GameState`/RNG, not a static program-wide list of known rules
extensions) -- see `docs/DECISIONS.md` D-5. Tests that register temporary
fake providers must remove them afterwards (`unregister`/`clear`) so the
catalogue does not leak between tests.
"""

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
    """One legal, card-sourced option offered at a hook point.

    `choice` is folded into the `Decision` the call site raises; `apply` is
    invoked (with the live `GameState`) only if the player picks this option,
    and returns whatever the hook's call site documents (e.g. an `int` delta
    for a numeric modifier hook, `None` for an effect hook).

    `cost` (`docs/OPEN_QUESTIONS.md` OQ-32, resolved) is an optional split-out
    "pay for/mark as played" step, run by `apply_chosen_option` unconditionally
    -- before the option is even offered a chance to be canceled -- so a
    provider whose own card can be "canceled as it is played" can still
    satisfy the generic ruling "cost is still paid" (quoted verbatim in
    OQ-32) without the *effect* (`apply`) itself running. `None` (the default)
    means `apply` alone does everything, exactly as every pre-existing
    provider in this codebase already assumes -- adding this field changes no
    existing provider's behaviour. A provider that does not need to be
    cancelable (the overwhelming majority) simply never sets it.

    `played_card_type` (`docs/OPEN_QUESTIONS.md` OQ-33, resolved) identifies
    *what is being played* when this specific option is chosen: the printed
    `LibraryCard.card_type` value (e.g. `"Reaction"`, `"Action Modifier"`,
    `"Master"`, `"Ally"`, `"Combat"`, `"Action"`, `"Political Action"`) of the
    physical library card this choice actually plays/recruits from hand --
    the same string `decks/loader.py::_build_library_card` already derives
    from krcg at deck-import time, matching exactly the "Card type: X" fact
    every card module's own docstring already states (CLAUDE.md §2 "card
    text first"; this is a restatement of an already-sourced fact, not a new
    one, so no provider needs to re-derive it live). `None` (the default)
    means this option is *not* playing a card at all: a printed vampire/
    crypt-card ability being activated (e.g. Modius's "discard a master card
    to get +1 vote", Saku Pihlajamäki's innate maneuver), a card already in
    play using its own standing ability (e.g. Oxford University, England's
    polling-step burn, Wider View's own transfer-costed clauses), or an
    option that only resolves/claims an effect some card already played and
    paid for earlier this action (e.g. Slam's deferred, already-committed
    strike; Dust Up's/Fleetness's claiming of an already-recorded grant) --
    none of these is "a card ... as it is played" in the sense Diana
    Iadanza's own printed text requires (`apply_chosen_option` below).
    Leaving this at its default `None` for a genuine card-play option would
    be a landmine identical in kind to the `rules-auditor` finding OQ-32's
    own review already caught for `cost` (a provider silently defaulting to
    a wrong value the moment the first real `CANCEL_AS_PLAYED_HOOK` provider
    exists) -- every provider that *does* play a card sets this explicitly.
    """

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
    """Remove all providers for `hook`, or every hook if `hook` is None.

    Test isolation helper only; production code never needs to call this
    (the catalogue is populated once, at import time, and left alone).
    """
    if hook is None:
        _PROVIDERS.clear()
    else:
        _PROVIDERS.pop(hook, None)


def offer(hook: str, state: GameState, **context: Any) -> list[HookOption]:
    """Collect every legal `HookOption` any registered provider offers right now."""
    options: list[HookOption] = []
    for provider in _PROVIDERS.get(hook, ()):
        options.extend(provider(state, context))
    return options


def ensure_unique_choice_values(choices: Iterable[Choice], *, decision_kind: str) -> None:
    """Raise if two or more `Choice`s share the same `.value`.

    CLAUDE.md "never mis-resolves a card": a call site that unions choices
    from more than one source before building a `Decision` (e.g. engine-
    hardcoded defaults plus hook-provided options -- `engine/phases/
    influence.py::influence_phase`, the first caller, resolving `docs/
    OPEN_QUESTIONS.md` OQ-24's own audit-driven addendum) must not let a
    collision pass silently: `GameState.ask`'s own `legal = {c.value: c for
    c in decision.choices}` keeps only the *last* value on a collision, so
    without this check a hook-provided `Choice.value` that happened to
    collide with a hardcoded one would silently make the hardcoded action
    unreachable for that value, with no error raised -- exactly the silent
    mis-resolution CLAUDE.md's "always plays legally and never mis-resolves
    a card" milestone forbids. Call this once, on the full set of choices
    about to be offered (including any fixed `"pass"`/`"end_phase"`-style
    choice), right before constructing the `Decision`.
    """
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
"""The project-wide convention key (OQ-11, `docs/OPEN_QUESTIONS.md`) a hook
`context` carries its shared, action-scoped scratch dict under -- see
`sanitize_decision_context` below for why it is excluded from every
`Decision.context`."""


def sanitize_decision_context(context: Mapping[str, Any]) -> dict[str, Any]:
    """Build the `dict` a `Decision.context` may safely copy from a hook
    `context` -- every call site that builds a `Decision` from a `Mapping`
    sourced from `offer(...)`'s own `context` must use this, never a bare
    `dict(context)`.

    CLAUDE.md "Information hiding": `Decision.context` reaches an agent
    directly (`GameState.ask` -> `Agent.decide`, `engine/decision.py`'s own
    "for logging/agent reasoning" purpose) with no filtering of its own.
    `context[PENDING_CONTEXT_KEY]` (OQ-11) is a live, engine-internal,
    per-action scratch dict threaded to every hook *provider* so a card play
    spanning two phases of the same action can carry state between them --
    it is not itself meant for an agent's own reasoning about the choice at
    hand, and sharing the identical live object across every hook offer for
    the whole action means mutating it later (e.g. a different provider's
    later `apply`) would retroactively change what an *earlier*, already-
    logged `Decision.context` appears to show, and a
    `ReplayLog.record_decision` snapshot of it is only a shallow copy, not a
    true snapshot, for the same reason. Since OQ-30 (`docs/OPEN_QUESTIONS.md`,
    resolved) it may also hold a `Callable` (`engine/action.py::
    ActiveInterceptDecrease.qualifies`) -- not serializable for a persisted
    replay log, and a sharper information-hiding violation than the plain
    data `pending` held before (a closure can capture a live `VampireInPlay`
    or other engine-internal state). This function strips
    `PENDING_CONTEXT_KEY` from what reaches `Decision.context`; the full,
    unfiltered `context` (including `pending`) is still exactly what every
    hook `offer(...)` call passes to the trusted, engine-registered provider
    functions themselves -- only the agent-visible copy is affected."""
    return {key: value for key, value in context.items() if key != PENDING_CONTEXT_KEY}


CANCEL_AS_PLAYED_HOOK = "cancel_as_played"
"""Mirrors `cards/registry.py::Hook.CANCEL_AS_PLAYED`'s own string value --
see `apply_chosen_option` below for the dispatch this now drives (`docs/
OPEN_QUESTIONS.md` OQ-32, resolved)."""


def apply_chosen_option(
    state: GameState,
    option: HookOption,
    played_by: str,
    may_cancel: str,
    context: Mapping[str, Any],
) -> Any:
    """The interception point between a `HookOption` being chosen and its
    effect actually running (`docs/OPEN_QUESTIONS.md` OQ-32, resolved).

    Every generic decision-loop helper in this module (`offer_until_pass`,
    `resolve_impulse_window`) resolves a chosen option through this function
    rather than calling `option.apply(state)` directly, so a reflexive
    "cancel a [reaction] card as it is played" effect (e.g. Diana Iadanza,
    krcg id 201694 -- not itself implemented by this function, see
    `src/vtesbot/cards/diana_iadanza.py`) has one generic place to interject,
    for *any* hook dispatched through either helper, with no further engine
    work needed.

    Order of operations, per the generic rulings on file for this mechanic
    (quoted verbatim in OQ-32's own entry):
    1. `option.cost`, if set, runs unconditionally -- this is what lets
       "cost is still paid" hold even when the effect below ends up
       suppressed; a provider that folds its own SS8 "once per action"
       bookkeeping into `cost` (rather than `apply`) thereby also keeps that
       bookkeeping correct regardless of cancellation, per the ruling "[t]he
       canceled card has still been played. The same reaction ... cannot be
       played again by the same minion."
    2. `may_cancel` -- the side *not* making the choice `option` represents,
       never `played_by` themselves (one cannot cancel one's own card as it
       is played) -- is offered `CANCEL_AS_PLAYED_HOOK`. Per the ruling "the
       cancelation must be played immediately: no other effects can be
       used," this is a single ask, not a further `offer_until_pass`-style
       loop: any card-specific restriction on what else may happen
       meanwhile belongs in a provider's own eligibility check, not here.
    3. If `may_cancel` chooses a cancellation: that option's own `apply`
       runs (paying its own cost, e.g. Diana's "burn 1 blood") and
       `option.apply` is suppressed entirely -- this function returns
       `None`. If a limited effect (e.g. a once-per-action bleed bonus) was
       canceled, per "[i]f a limited effect is canceled ..., then the limit
       is not triggered," which falls out for free here: nothing in
       `option.apply` (where such limited-effect bookkeeping would live) runs
       at all.
    4. Otherwise (`may_cancel` passes, or nothing is legal to offer them --
       the common, "only when needed" case when no provider is registered
       for `CANCEL_AS_PLAYED_HOOK`, true of every card in the pool today):
       `option.apply(state)` runs normally and its return value is passed
       through unchanged -- byte-for-byte the pre-OQ-32 behaviour, so wiring
       this into `offer_until_pass`/`resolve_impulse_window` changes nothing
       about any already-implemented card.

    `context` is threaded into `CANCEL_AS_PLAYED_HOOK`'s own offer (plus
    `canceled_by`/`canceled_choice`/`canceled_card_type`, identifying what is
    being canceled -- `canceled_card_type` is `option.played_card_type`,
    `docs/OPEN_QUESTIONS.md` OQ-33, resolved) the same way every other hook
    threads it -- including `context["pending"]`, if present; the nested
    `Decision` this may raise is still built via `sanitize_decision_context`,
    so `pending` never reaches the agent (CLAUDE.md "Information hiding",
    the same convention this module's other helpers already follow).

    One known gap, dormant today (no `CANCEL_AS_PLAYED_HOOK` provider exists
    yet to hit it), left for whoever builds the first one (`docs/
    OPEN_QUESTIONS.md` OQ-32, `rules-auditor` review): nothing here enforces
    "the cancelation must be played immediately: no other effects can be
    used" [LSJ 20061207] if a future `option.cost`, or a cancel option's own
    `apply`, itself calls back into `hooks.offer`/`offer_until_pass`/
    `resolve_impulse_window` (re-entrant hook dispatch mid-cancellation). No
    current provider does this -- it is unenforced, not forbidden, by this
    function today.

    (A second gap used to be documented here -- `cancel_context` carrying no
    structured marker of the canceled option's own card type, so a provider
    wanting to cancel only Reaction cards, as Diana Iadanza's own printed
    text requires, had nothing but fragile `canceled_choice` string-matching
    to go on. OQ-33 (resolved) closed it: `canceled_card_type` above.)
    """
    if option.cost is not None:
        option.cost(state)
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
    """Single-sided "keep using options or stop" loop for one player.

    Used for hook points the rules give to exactly one side (e.g. a
    master-phase play, a damage-prevention effect): `player` is offered every
    legal `HookOption`, plus "pass", repeatedly, until they pass or no
    options remain (CLAUDE.md "only when needed": no options => no decision
    raised at all, matching the pattern already used by
    `engine/phases/unlock.py`'s own-effect-ordering loop).

    Each chosen option is resolved via `apply_chosen_option` (`docs/
    OPEN_QUESTIONS.md` OQ-32, resolved), not a bare `.apply(state)` call, so
    `GameState.other_player(player)` -- the 2P structural fact that the sole
    opponent is always both prey and predator (CLAUDE.md §3) -- always gets
    the generic "cancel as played" interception point, for any hook, with no
    further engine work needed.
    """
    while True:
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
    """Two-sided impulse window (CLAUDE.md rule 4 / Rulebook SS2 Sequencing):
    "Acting Methuselah gets the impulse first; after any effect is used the
    impulse returns to the acting Methuselah; then the other player; the
    window closes when both pass."

    Offers `hook` to `acting_player`, then `other_player`, alternating; using
    an option resets the alternation back to `acting_player` next (the
    "impulse returns to the acting Methuselah" rule); the window ends once
    both players pass (or have nothing to offer) in immediate succession.

    Each chosen option is resolved via `apply_chosen_option` (`docs/
    OPEN_QUESTIONS.md` OQ-32, resolved), not a bare `.apply(state)` call, so
    whichever side did *not* just choose `turn`'s option always gets the
    generic "cancel as played" interception point, for any hook, with no
    further engine work needed.
    """
    turn = acting_player
    consecutive_passes = 0
    while consecutive_passes < 2:
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
    """Passive numeric-modifier hook (no decision): sum every registered
    provider's contribution for a mandatory, non-chosen effect (e.g. a
    printed vampire ability that always adds +1 strength in a given
    matchup -- CLAUDE.md rule 3's "mandatory effects defined by the rules"
    exception; nothing to offer a player, so no `Decision` is raised).

    Providers for a `sum_modifiers` hook are plain
    `Callable[[GameState, Mapping], int]` functions (not `HookOption`-based),
    registered the same way via `register`, and must return 0 when they do
    not apply.
    """
    total = 0
    for provider in _PROVIDERS.get(hook, ()):
        total += provider(state, context)  # type: ignore[arg-type]
    return total


def run_effects(hook: str, state: GameState, **context: Any) -> None:
    """Mandatory, non-chosen, per-provider side-effect dispatch (no decision,
    no aggregated return value): every registered provider for `hook` is
    called once, in registration order, and may mutate `state` directly
    (CLAUDE.md rule 3's "mandatory effects defined by the rules" exception --
    nothing for a player to choose, so no `Decision` is raised). Sibling of
    `sum_modifiers`/`union_modifiers`, which both aggregate a *value* the
    caller then applies itself; `run_effects` is for a provider whose own
    effect *is* the mutation (e.g. a printed ability that makes a Methuselah
    automatically lose pool once some condition is met, with nothing to pick
    among -- see `docs/OPEN_QUESTIONS.md` OQ-6, Marcos Belegrad, the motivating
    case this helper was added for).

    Providers for a `run_effects` hook are plain
    `Callable[[GameState, Mapping], None]` functions (return value ignored),
    registered the same way via `register`, and must simply do nothing when
    they do not apply.
    """
    for provider in _PROVIDERS.get(hook, ()):
        provider(state, context)  # type: ignore[arg-type]


def union_modifiers(hook: str, state: GameState, **context: Any) -> tuple[Any, ...]:
    """Passive, set-valued counterpart to `sum_modifiers` (no decision):
    unions every registered provider's contribution for a mandatory,
    non-chosen effect whose value is a *collection* rather than a number
    (e.g. `engine/attachments.py::effective_disciplines` -- an attached
    discipline/archetype master card's printed "+1 level of <X>" grants a
    discipline-level code, not a scalar quantity, so `sum_modifiers`'s `int`
    contract does not fit -- CLAUDE.md rule 3's "mandatory effects defined
    by the rules" exception still applies: nothing to offer a player, so no
    `Decision` is raised).

    Providers for a `union_modifiers` hook are plain
    `Callable[[GameState, Mapping], Iterable[Any]]` functions (not
    `HookOption`-based), registered the same way via `register`, and must
    return an empty iterable when they do not apply.

    Returns a *sorted tuple*, not a `frozenset` (rules-auditor finding,
    CLAUDE.md SS5 determinism: "same seed + same decisions => same game").
    Python's string hashing is randomized per process by default, so a
    `frozenset[str]` iterated to build `Decision.choices` -- not a need
    today, since nothing iterates this return value yet, but a latent trap
    for a future card module that does -- would yield a non-reproducible
    choice ordering across process runs from the same replay log, even
    though the legal *values* would still be correct. Sorting here, once,
    removes the footgun at its source rather than relying on every future
    caller to remember to sort. Values must be sortable (every current and
    anticipated use is discipline-level string codes).
    """
    result: set[Any] = set()
    for provider in _PROVIDERS.get(hook, ()):
        result.update(provider(state, context))  # type: ignore[arg-type]
    return tuple(sorted(result))
