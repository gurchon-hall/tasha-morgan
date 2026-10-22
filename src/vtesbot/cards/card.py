"""Card authoring API: one `Card` per card module registers the card and its
hook providers, so its registry entry can never drift from what it wires.
`cards/celerity.py` is the reference module."""

import inspect
import sys
from annotationlib import Format
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Final

from vtesbot.cards import _shared
from vtesbot.cards.registry import Status, register
from vtesbot.engine import hooks
from vtesbot.engine.cards import LibraryCard
from vtesbot.engine.decision import Choice
from vtesbot.engine.hook_contexts import HOOK_CONTEXTS
from vtesbot.engine.hooks import UNWIRED_HOOKS, Hook, HookOption

if TYPE_CHECKING:
    from vtesbot.engine.state import GameState

_CARD_TYPE: Final = object()


def _check_ctx_annotation(name: str, hook: Hook, provider: Callable[..., Any]) -> None:
    params = list(inspect.signature(provider, annotation_format=Format.FORWARDREF).parameters)
    if len(params) != 2:
        raise TypeError(f"{name}: {provider.__name__} must take (state, ctx)")
    annotation = inspect.get_annotations(provider, format=Format.FORWARDREF).get(params[1])
    if annotation != HOOK_CONTEXTS[hook]:
        raise TypeError(
            f"{name}: {provider.__name__}'s ctx must be annotated "
            f"{HOOK_CONTEXTS[hook]!r} for {hook}, got {annotation!r}"
        )


class Card:
    """A card's registry entry plus its hook providers.

    `card_type` is the krcg type (`"Master"`, `"Combat"`, ...) stamped on
    every `option()` as `HookOption.played_card_type` (ENG-023); required for
    library cards (krcg ids 100000-199999). `also_uses` names unwired hooks the
    card is classified under but cannot register on. `source` defaults to the
    module creating the card.
    """

    def __init__(
        self,
        krcg_id: int,
        name: str,
        card_type: str | None = None,
        *,
        also_uses: tuple[Hook, ...] = (),
        source: str | None = None,
    ) -> None:
        if 100_000 <= krcg_id < 200_000 and not card_type:
            raise ValueError(f"{name}: a library card needs its card_type")
        if wired := [h for h in also_uses if h not in UNWIRED_HOOKS]:
            raise ValueError(f"{name}: also_uses is for unwired hooks only, got {wired}")
        self.krcg_id = krcg_id
        self.name = name
        self.card_type = card_type
        self.status = Status.IMPLEMENTED
        self.blocked_reason: str | None = None
        self.source = source if source is not None else sys._getframe(1).f_globals["__name__"]
        self._hooks: list[Hook] = list(also_uses)
        self._wired = False
        register(self)

    @property
    def hooks(self) -> tuple[Hook, ...]:
        return tuple(self._hooks)

    def on[P: Callable[[GameState, Any], Any]](self, hook: Hook) -> Callable[[P], P]:
        """Decorator: register the function as this card's provider for `hook`.
        Its `ctx` parameter must be annotated with `HOOK_CONTEXTS[hook]`."""
        if hook in UNWIRED_HOOKS:
            raise ValueError(f"{self.name}: {hook} has no engine dispatch site yet")
        if self.status is Status.BLOCKED:
            raise ValueError(f"{self.name}: a blocked card must not wire providers")

        def decorate(provider: P) -> P:
            _check_ctx_annotation(self.name, hook, provider)
            hooks.register(hook, provider)
            self._wired = True
            if hook not in self._hooks:
                self._hooks.append(hook)
            return provider

        return decorate

    def block(self, reason: str, *, planned_hooks: tuple[Hook, ...] = ()) -> None:
        """Mark the card blocked, with no providers wired so it is never offered.
        `reason` is a `RUL-`/`ENG-` id or a short note; `planned_hooks` records
        the hooks it will use once unblocked."""
        if not reason:
            raise ValueError(f"card {self.krcg_id} ({self.name!r}) is blocked but has no reason")
        if self._wired:
            raise ValueError(f"{self.name}: blocked after wiring providers; it would stay playable")
        self.status = Status.BLOCKED
        self.blocked_reason = reason
        self._hooks += [h for h in planned_hooks if h not in self._hooks]

    def in_hand(self, state: GameState, player: str) -> bool:
        return any(c.krcg_id == self.krcg_id for c in state.players[player].hand)

    def play_from_hand(self, state: GameState, player: str) -> LibraryCard:
        return _shared.play_from_hand(state, player, self.krcg_id)

    def play_from_hand_pending(self, state: GameState, player: str) -> LibraryCard:
        return _shared.play_from_hand_pending(state, player, self.krcg_id)

    def remove_from_hand(self, state: GameState, player: str) -> LibraryCard:
        return _shared.remove_from_hand(state, player, self.krcg_id)

    def option(
        self,
        value: str,
        label: str,
        apply: Callable[[GameState], Any],
        *,
        cost: Callable[[GameState], Any] | None = None,
        played_card_type: Any = _CARD_TYPE,
        block_candidate_instance_id: str | None = None,
    ) -> HookOption:
        """A `HookOption` for this card. `played_card_type` defaults to
        `card_type`; pass `None` for an option that plays no card."""
        return HookOption(
            choice=Choice(value, label),
            apply=apply,
            cost=cost,
            played_card_type=(
                self.card_type if played_card_type is _CARD_TYPE else played_card_type
            ),
            block_candidate_instance_id=block_candidate_instance_id,
        )
