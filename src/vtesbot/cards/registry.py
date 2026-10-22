"""Card implementation registry (CLAUDE.md §6): a card module registers
itself at import, via `cards/card.py::Card` (or, until every module is
migrated, `register(CardRegistration(...))`). `krcg_id` is the key (DES-005:
static catalogue, not GameState).
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from vtesbot.engine.hooks import Hook as Hook


class Status(StrEnum):
    IMPLEMENTED = "implemented"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class CardRegistration:
    krcg_id: int
    name: str
    status: Status
    hooks: tuple[Hook, ...]
    source: str
    """Short provenance note: the module path, or (for a card not yet
    implemented) a one-line description of what blocks it."""
    blocked_reason: str | None = None
    """A `RUL-<nnn>`/`ENG-<nnn>` id when `status is Status.BLOCKED` and a
    `docs/` entry is the blocker; otherwise a short
    descriptive string citing the missing engine data field or subsystem
    (not a ruling ambiguity -- see e.g. Queen Anne/Alexa Draper)."""


class RegisteredCard(Protocol):
    """What the registry reads: a `CardRegistration` or a `card.Card`."""

    @property
    def krcg_id(self) -> int: ...
    @property
    def name(self) -> str: ...
    @property
    def status(self) -> Status: ...
    @property
    def hooks(self) -> tuple[Hook, ...]: ...
    @property
    def source(self) -> str: ...
    @property
    def blocked_reason(self) -> str | None: ...


_REGISTRY: dict[int, RegisteredCard] = {}


def register[R: RegisteredCard](reg: R) -> R:
    if reg.krcg_id in _REGISTRY:
        raise ValueError(f"card {reg.krcg_id} ({reg.name!r}) is already registered")
    if reg.status is Status.BLOCKED and not reg.blocked_reason:
        raise ValueError(f"card {reg.krcg_id} ({reg.name!r}) is blocked but has no blocked_reason")
    _REGISTRY[reg.krcg_id] = reg
    return reg


def get(krcg_id: int) -> RegisteredCard | None:
    return _REGISTRY.get(krcg_id)


def all_registrations() -> tuple[RegisteredCard, ...]:
    return tuple(_REGISTRY.values())


def implemented_ids() -> frozenset[int]:
    return frozenset(r.krcg_id for r in _REGISTRY.values() if r.status is Status.IMPLEMENTED)


def blocked_ids() -> frozenset[int]:
    return frozenset(r.krcg_id for r in _REGISTRY.values() if r.status is Status.BLOCKED)


def remove(krcg_id: int) -> None:
    """Test isolation helper only; production code never calls this."""
    _REGISTRY.pop(krcg_id, None)


def clear() -> None:
    """Test isolation helper only; production code never calls this."""
    _REGISTRY.clear()
