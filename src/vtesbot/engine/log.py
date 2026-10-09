"""Full replay log: every decision and every random draw, in order.

CLAUDE.md SS5 engine invariant: "every decision and every random draw is
logged so a game can be replayed and a bug reproduced." The log is an
engine-internal record (unlike `Observation`, it is not shown to agents and
does not need to hide hidden information -- it exists for debugging/replay).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .decision import Choice, Decision


@dataclass(frozen=True)
class LogEntry:
    kind: str  # "decision" | "random"
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

    def record_random(self, description: str, result: Any) -> None:
        self.entries.append(
            LogEntry(kind="random", data={"description": description, "result": result})
        )
