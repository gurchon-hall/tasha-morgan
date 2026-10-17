"""Human-readable rendering of a match's outcome/decision trail from
`ReplayLog`. `write_*` are the only I/O here (`sim/` is allowed to do I/O)
and are opt-in via `report_dir`."""

import csv
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

from vtesbot.engine.log import ReplayLog

from .invariants import ACTION_NAMES, ECONOMIC_FIELDS

if TYPE_CHECKING:
    from .runner import BatchResult, MatchResult


def format_crash(seed: int, exc: BaseException) -> str:
    """A short, reproducible description of one `BatchResult.crashes` entry."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return f"seed={seed}:\n{tb}"


def format_summary(result: MatchResult) -> str:
    if not result.game_over:
        outcome = "STUCK (max_turns reached)"
    elif result.winner is None:
        outcome = "TIE (simultaneous oust, no winner)"
    else:
        outcome = f"winner={result.winner}"
    vp = ", ".join(f"{player}={points}" for player, points in result.victory_points.items())
    return f"seed={result.seed} turns_played={result.turns_played} {outcome}\nvictory_points: {vp}"


def format_decision_log(log: ReplayLog) -> str:
    lines: list[str] = []
    for entry in log.entries:
        if entry.kind in ("decision", "forced"):
            data = entry.data
            offered = ", ".join(data["offered"])
            lines.append(
                f"[{entry.kind}] {data['player']} {data['decision_kind']}: "
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


def write_batch_report(
    batch: BatchResult,
    directory: Path,
    *,
    sample_count: int = 3,
    sample_losses_and_ties: bool = False,
) -> Path:
    """Writes `batch_results.csv`, `crashes.log`, and a `samples/` subfolder
    with `write_match_report`'s output for the first `sample_count` games.

    `sample_losses_and_ties` (opt-in, default `False` so existing callers
    are unaffected): a batch dominated by P1 wins still samples every P1
    loss/tie beyond the first `sample_count`, capped at `sample_count * 4`
    extra games (bounds disk use). "Loss/tie" is from P1's own perspective
    (`winner != "P1"`), the same P1-as-subject convention `summarize_versus`
    already uses -- the CSV/report shape has no other notion of which seat
    is "the" agent under test."""
    directory.mkdir(parents=True, exist_ok=True)

    csv_path = directory / "batch_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        players = sorted({p for r in batch.results for p in r.final_pools})
        writer.writerow(
            ["seed", "turns_played", "game_over", "stuck", "winner", "victory_points"]
            + ["self_oust", "tie"]
            + [f"{p}_final_pool" for p in players]
            + [f"{p}_{a}" for p in players for a in ACTION_NAMES]
            + [f"{p}_{f}" for p in players for f in ECONOMIC_FIELDS]
        )
        for r in batch.results:
            vp = ";".join(f"{player}={points}" for player, points in r.victory_points.items())
            writer.writerow(
                [r.seed, r.turns_played, r.game_over, r.stuck, r.winner, vp, r.self_oust, r.tie]
                + [r.final_pools.get(p, "") for p in players]
                + [r.action_counts.get(p, {}).get(a, 0) for p in players for a in ACTION_NAMES]
                + [r.economic_counts.get(p, {}).get(f, 0) for p in players for f in ECONOMIC_FIELDS]
            )

    crashes_path = directory / "crashes.log"
    with open(crashes_path, "w", encoding="utf-8") as f:
        for seed, exc in batch.crashes:
            f.write(format_crash(seed, exc) + "\n\n")

    samples = list(batch.results[:sample_count])
    if sample_losses_and_ties:
        extra_cap = sample_count * 4
        sampled_seeds = {r.seed for r in samples}
        for r in batch.results:
            if len(samples) >= sample_count + extra_cap:
                break
            if r.seed in sampled_seeds or r.winner == "P1":
                continue
            samples.append(r)
            sampled_seeds.add(r.seed)

    for sample in samples:
        write_match_report(sample, directory / "samples")

    return directory
