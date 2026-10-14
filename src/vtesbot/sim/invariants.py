"""Post-match invariant checks over a `ReplayLog` (CLAUDE.md test-engineer
invariants). Log-only: they need no engine state."""

import re

from vtesbot.engine.log import ReplayLog


class InvariantViolation(AssertionError):
    """A simulated match broke an engine invariant."""


def check_no_activity_after_oust(log: ReplayLog) -> None:
    """Rulebook §5 Ending the Game: once a Methuselah is ousted in a duel the
    game is over, so no `"decision"`, `"forced"` or `"random"` entry may follow the
    `"... is OUSTED"` event."""
    oust_at: int | None = None
    for i, entry in enumerate(log.entries):
        if oust_at is None:
            if entry.kind == "event" and "is OUSTED" in entry.data["description"]:
                oust_at = i
        elif entry.kind in ("decision", "forced", "random"):
            raise InvariantViolation(
                f"{entry.kind} entry #{i} after oust event #{oust_at}: "
                f"{log.entries[oust_at].data['description']!r}"
            )


_LOSS = re.compile(r"^(\S+) loses \d+ pool")
_OUST = re.compile(r"^(\S+) is OUSTED")
ACTION_NAMES = (
    "reveal",
    "bleed",
    "hunt",
    "act_with",
    "end_minion_phase",
    "bring_crypt",
    "add_blood",
    "remove_blood",
)


def action_counts(log: ReplayLog, players: list[str]) -> dict[str, dict[str, int]]:
    """Per-player count of decisions whose choice value (before any `:`) is
    one of the tracked action names."""
    counts = {p: dict.fromkeys(ACTION_NAMES, 0) for p in players}
    for e in log.entries:
        if e.kind != "decision":
            continue
        name = str(e.data["choice"]).split(":", 1)[0]
        if name in ACTION_NAMES and e.data["player"] in counts:
            counts[e.data["player"]][name] += 1
    return counts


VOLUNTARY_POOL_DECISION_KINDS = frozenset(
    {
        "influence_action",
        "contest_resolution",
        "ally_contest_resolution",
        "attachment_contest_resolution",
        "master_card_contest_resolution",
        "master_phase_action",
        "polling_step",
        "kine_resources_contested_allocation",
    }
)


NON_SPENDING_CHOICES = frozenset(
    {"yield", "pass", "decline", "end_phase", "end_minion_phase", "done"}
)
"""Choices of a voluntary-pool decision kind that spend no pool, so a later
forced loss (Fame, OQ-43) is not attributable to them."""


def is_self_oust(log: ReplayLog) -> bool:
    """True if the ousted player's last pool loss was caused by their own
    voluntary-pool decision (the nearest preceding decision or `"forced"`
    lone-choice entry, one that spends pool; OQ-41/OQ-42). Forced own-pool
    ousts are legal (OQ-43), not flagged."""
    entries = log.entries
    for i, e in enumerate(entries):
        if e.kind != "event" or not (m := _OUST.match(e.data["description"])):
            continue
        ousted = m.group(1)
        for j in range(i - 1, -1, -1):
            ej = entries[j]
            if ej.kind == "event" and (lm := _LOSS.match(ej.data["description"])):
                if lm.group(1) != ousted:
                    continue
                for k in range(j - 1, -1, -1):
                    if entries[k].kind in ("decision", "forced"):
                        d = entries[k].data
                        return (
                            d["player"] == ousted
                            and d["decision_kind"] in VOLUNTARY_POOL_DECISION_KINDS
                            and str(d["choice"]).split(":", 1)[0] not in NON_SPENDING_CHOICES
                        )
                return False
        return False
    return False
