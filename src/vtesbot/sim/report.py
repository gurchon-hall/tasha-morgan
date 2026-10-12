"""Human-readable rendering of a match's outcome and full decision trail.

`engine/log.py::ReplayLog` already records every decision (player, kind,
offered choices, context, chosen value), every random draw (CLAUDE.md's
"every decision and every random draw is logged" invariant), and -- a later,
purely additive, human-readability-only addition, see `ReplayLog`'s own
docstring -- a handful of narrated `"event"` entries (pool changes, damage
taken, torpor/burn, ousting). The gap this module fills is purely
presentation: a short summary, and a full line-by-line transcript suitable
for debugging/reproducing one seed or just reading "what happened," each as
a separate, independently-testable string-formatting function; the `write_*`
functions
are the only parts of this module that touch disk (`sim/` -- unlike
`engine/`/`cards/` -- is allowed to do I/O, CLAUDE.md SS5's own "replay
logs" package), and are themselves opt-in (`run_match`/`run_many`'s
`report_dir` parameter, `runner.py`) rather than always-on, so a mature run
(e.g. evaluating an agent over many games) isn't forced to pay for file I/O
it no longer needs for day-to-day use.

Only type-hint imports from `.runner` (under `TYPE_CHECKING`) so `runner.py`
can import this module at the top level without a circular import.
"""

import csv
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from vtesbot.engine.log import ReplayLog

if TYPE_CHECKING:
    from .runner import BatchResult, MatchResult


def format_crash(seed: int, exc: BaseException) -> str:
    """A short, reproducible description of one `BatchResult.crashes` entry."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return f"seed={seed}:\n{tb}"


def format_summary(result: MatchResult) -> str:
    outcome = f"winner={result.winner}" if result.game_over else "STUCK (max_turns reached)"
    vp = ", ".join(f"{player}={points}" for player, points in result.victory_points.items())
    return (
        f"seed={result.seed} turns_played={result.turns_played} {outcome}\n"
        f"victory_points: {vp}"
    )


def format_decision_log(log: ReplayLog) -> str:
    lines: list[str] = []
    for entry in log.entries:
        if entry.kind == "decision":
            data = entry.data
            offered = ", ".join(data["offered"])
            lines.append(
                f"[decision] {data['player']} {data['decision_kind']}: "
                f"chose {data['choice']!r} (offered: [{offered}])"
            )
        elif entry.kind == "random":
            lines.append(f"[random] {entry.data['description']} -> {entry.data['result']!r}")
        elif entry.kind == "event":
            lines.append(f"[event] {entry.data['description']}")
        else:
            lines.append(f"[{entry.kind}] {entry.data}")
    return "\n".join(lines)


def write_match_report(result: MatchResult, directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    summary_path = directory / f"{result.seed}.summary.txt"
    decisions_path = directory / f"{result.seed}.decisions.log"
    summary_path.write_text(format_summary(result) + "\n", encoding="utf-8")
    decisions_path.write_text(format_decision_log(result.log) + "\n", encoding="utf-8")
    return summary_path, decisions_path


def write_batch_report(batch: BatchResult, directory: Path, *, sample_count: int = 3) -> Path:
    """Writes `batch`'s outcome to `directory`: `batch_results.csv` (one row
    per completed game -- seed, turns played, outcome, victory points),
    `crashes.log` (a full reproducible traceback per crashed seed, if any),
    and a `samples/` subfolder holding `write_match_report`'s full
    summary+decision-log output for the first `sample_count` completed
    games -- enough to spot-check real decision-level detail without
    writing one file pair per game in a large batch. Returns `directory`.
    """
    directory.mkdir(parents=True, exist_ok=True)

    csv_path = directory / "batch_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["seed", "turns_played", "game_over", "stuck", "winner", "victory_points"])
        for r in batch.results:
            vp = ";".join(f"{player}={points}" for player, points in r.victory_points.items())
            writer.writerow([r.seed, r.turns_played, r.game_over, r.stuck, r.winner, vp])

    crashes_path = directory / "crashes.log"
    with open(crashes_path, "w", encoding="utf-8") as f:
        for seed, exc in batch.crashes:
            f.write(format_crash(seed, exc) + "\n\n")

    for sample in batch.results[:sample_count]:
        write_match_report(sample, directory / "samples")

    return directory
