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
from collections.abc import Callable, Mapping
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
    """

    choice: Choice
    apply: Callable[[GameState], Any]


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
    """
    while True:
        options = offer(hook, state, player=player, **context)
        if not options:
            return
        by_value = {o.choice.value: o for o in options}
        choices = tuple(o.choice for o in options) + (Choice(PASS_VALUE, "Pass"),)
        decision = Decision(
            player=player, kind=decision_kind or hook, choices=choices, context=dict(context)
        )
        answer = state.ask(decision)
        if answer.value == PASS_VALUE:
            return
        by_value[answer.value].apply(state)


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
            player=turn, kind=decision_kind or hook, choices=choices, context=dict(context)
        )
        answer = state.ask(decision)
        if answer.value == PASS_VALUE:
            consecutive_passes += 1
        else:
            consecutive_passes = 0
            by_value[answer.value].apply(state)
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
