"""Bot-vs-bot runner and replay logs (CLAUDE.md SS5)."""

from .invariants import InvariantViolation, check_no_activity_after_oust
from .report import (
    format_crash,
    format_decision_log,
    format_summary,
    write_batch_report,
    write_match_report,
)
from .runner import BatchResult, MatchResult, run_many, run_match

__all__ = [
    "InvariantViolation",
    "check_no_activity_after_oust",
    "MatchResult",
    "BatchResult",
    "run_match",
    "run_many",
    "format_crash",
    "format_summary",
    "format_decision_log",
    "write_match_report",
    "write_batch_report",
]
