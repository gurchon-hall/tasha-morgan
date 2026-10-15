"""Decision points: the engine never chooses on behalf of a player (CLAUDE.md §5).
Data shapes only; `GameState.ask` calls the agent and enforces a legal answer."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Choice:
    """One legal, selectable option within a `Decision`. `value` is the machine-readable
    id an agent returns; `label` is a human-readable description for logs/CLI."""

    value: str
    label: str

    def __hash__(self) -> int:  # noqa: D105 - identity by value only
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Choice):
            return self.value == other.value
        return NotImplemented


@dataclass(frozen=True)
class Decision:
    """A point where one player must choose among legal options. `kind` names the rule
    mechanism; `context` carries extra info. `choices` is non-empty: a no-op step
    resolves automatically instead."""

    player: str
    kind: str
    choices: tuple[Choice, ...]
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.choices:
            raise ValueError(f"Decision(kind={self.kind!r}) offered with no legal choices")
