"""Human-readable rendering of a match's outcome and full decision trail.

`engine/log.py::ReplayLog` already records every decision, every random
draw, and a few narrated `"event"` entries (pool changes, damage, torpor/
burn, ousting). This module only adds presentation: a short summary and a
full line-by-line transcript, each as an independently-testable formatting
function. The `write_*` functions are the only I/O here (`sim/`, unlike
`engine/`/`cards/`, is allowed to do I/O) and are opt-in via `report_dir`
(`run_match`/`run_many`, `runner.py`), so a mature evaluation run isn't
forced to pay for file I/O it no longer needs.

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
    return f"seed={result.seed} turns_played={result.turns_played} {outcome}\nvictory_points: {vp}"


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
    per completed game), `crashes.log` (a full traceback per crashed seed),
    and a `samples/` subfolder with `write_match_report`'s full output for
    the first `sample_count` games -- enough to spot-check decision-level
    detail without writing a file pair per game in a large batch. Returns
    `directory`.
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
