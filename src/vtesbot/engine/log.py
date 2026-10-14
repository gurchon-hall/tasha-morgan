"""Full replay log: every decision and every random draw, in order.

CLAUDE.md SS5 engine invariant: "every decision and every random draw is
logged so a game can be replayed and a bug reproduced." The log is an
engine-internal record (unlike `Observation`, it is not shown to agents and
does not need to hide hidden information -- it exists for debugging/replay).

`"event"` entries (`record_event`) are a later, purely additive addition on
top of that invariant: a human-readable narration of a handful of
notable, deterministic *consequences* of decisions/random draws already in
the log (pool gained/lost, damage taken, a vampire entering torpor or being
burned, an oust) -- added because a `sim/report.py`-rendered decision log,
while complete enough to replay, was hard for a person to read ("how did
this game actually end?") without mentally re-deriving these consequences.
They change nothing about replay/reproducibility (no rule reads them back;
only `pool.py`/`damage.py`/`ousting.py` write them, right where the state
change already happens) and are never required reading -- the log is still
fully reconstructable from just its `"decision"`/`"random"` entries.

`"forced"` entries (`record_forced`) record a lone-legal-choice decision the
engine took without asking an agent (`GameState.ask_unless_forced`; "only
when needed"). Same data shape as `"decision"` but a distinct kind: no agent
answered, so replay and agent RNG consumption are unchanged, while sim
invariants can still see which choice was taken.
"""

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
