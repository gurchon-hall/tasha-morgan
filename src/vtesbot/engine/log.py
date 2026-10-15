"""Full replay log: every decision/random draw, in order (CLAUDE.md §5),
not shown to agents. `"event"` narrates consequences, never read back.
`"forced"` records a choice taken without asking an agent."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .decision import Choice, Decision


@dataclass(frozen=True)
class LogEntry:
    kind: str  # "decision" | "random" | "event" | "forced"
    data: dict[str, Any]


@dataclass
class ReplayLog:
    entries: list[LogEntry] = field(default_factory=list)

    def record_decision(self, decision: Decision, choice: Choice) -> None:
        self.entries.append(
            LogEntry(
                kind="decision",
                data={
                    "player": decision.player,
                    "decision_kind": decision.kind,
                    "offered": [c.value for c in decision.choices],
                    "context": dict(decision.context),
                    "choice": choice.value,
                },
            )
        )

    def record_forced(self, decision: Decision, choice: Choice) -> None:
        """A lone legal choice taken without an agent call (see module docstring)."""
        self.entries.append(
            LogEntry(
                kind="forced",
                data={
                    "player": decision.player,
                    "decision_kind": decision.kind,
                    "offered": [c.value for c in decision.choices],
                    "context": dict(decision.context),
                    "choice": choice.value,
                },
            )
        )

    def record_random(self, description: str, result: Any) -> None:
        self.entries.append(
            LogEntry(kind="random", data={"description": description, "result": result})
        )

    def record_event(self, description: str) -> None:
        """A human-readable note about a notable state change (see module
        docstring) -- observability only, never read back by any rule."""
        self.entries.append(LogEntry(kind="event", data={"description": description}))
