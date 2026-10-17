"""Post-match invariant checks over a `ReplayLog` (CLAUDE.md test-engineer
invariants). Log-only: they need no engine state."""

import re

from vtesbot.engine.action import ACTION_BLEED
from vtesbot.engine.log import LogEntry, ReplayLog


class InvariantViolation(AssertionError):
    """A simulated match broke an engine invariant."""


def check_no_activity_after_oust(log: ReplayLog) -> None:
    """Rulebook §5: once ousted in a duel the game is over, so no
    `"decision"`/`"forced"`/`"random"` entry may follow `"... is OUSTED"`."""
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


ECONOMIC_FIELDS = (
    "pool_spent_recruit",
    "recruit_count",
    "pool_spent_add_blood",
    "pool_gained_remove_blood",
    "bleed_pool_dealt",
    "lethal_bleed_count",
)
"""Phase A (`tmp/heuristic-agent-audit-plan.md`): economic detail missing
from `action_counts`'s raw tallies, needed to tell *why* a benchmark number
moved, not just that it did."""

_RECRUIT_CHOICE_PREFIX = "recruit_"
"""`action_choice` picks a per-card `HookOption.choice.value` for a recruit
(e.g. `cards/forty_seventh_street_royals.py`'s `"recruit_47th_street_royals"`
-- the only Ally card implemented as of this writing), not `engine/action.py
::ACTION_RECRUIT_ALLY` itself: that constant only labels the internal
`action=` discriminator passed to `perform_minion_action`/`attempt_block`,
which `ReplayLog.record_decision` never stores for an `action_choice` entry.
Detecting a recruit from the log alone therefore matches this literal
prefix convention rather than a single hook-enforced constant (judgment
call -- flagged in the test-engineer's Phase A report): a future Ally card
module whose own `Choice.value` does not start with `"recruit_"` would
silently fall out of `recruit_count`/`pool_spent_recruit` until this is
revisited."""

_LOSS_AMOUNT = re.compile(r"^(\S+) loses (\d+) pool")


def _resolution_window_end(entries: list[LogEntry], start: int) -> int:
    """Index (exclusive) where the minion-action window opened by the
    `action_choice` decision/forced entry just before `start` ends: the
    next `action_choice` entry (a new minion action announced) or end of
    log -- same bounded-forward-scan style as `is_self_oust` below."""
    j = start
    while j < len(entries):
        e = entries[j]
        if e.kind in ("decision", "forced") and e.data.get("decision_kind") == "action_choice":
            return j
        j += 1
    return j


def _pool_lost_by(entries: list[LogEntry], start: int, end: int, player: str) -> int:
    total = 0
    for e in entries[start:end]:
        if e.kind == "event" and (m := _LOSS_AMOUNT.match(e.data["description"])):
            if m.group(1) == player:
                total += int(m.group(2))
    return total


def _ousted_within(entries: list[LogEntry], start: int, end: int, player: str) -> bool:
    return any(
        e.kind == "event" and (m := _OUST.match(e.data["description"])) and m.group(1) == player
        for e in entries[start:end]
    )


def economic_counts(log: ReplayLog, players: list[str]) -> dict[str, dict[str, int]]:
    """Per-player economic detail, derived purely from `ReplayLog` decision
    and event entries (no engine changes): `add_blood`/`remove_blood` cost
    and gain 1 pool each, fixed, read straight off the `influence_action`
    choice (`engine/phases/influence.py::_apply`); a `bleed`/recruit
    action's actual pool effect goes through a block/modifier window, so
    it is read back from the pool-loss/oust events inside that action's
    own resolution window (`_resolution_window_end`), the same
    bounded-forward-scan idea `is_self_oust` already uses below."""
    counts = {p: dict.fromkeys(ECONOMIC_FIELDS, 0) for p in players}
    entries = log.entries

    def other_of(player: str) -> str | None:
        others = [p for p in players if p != player]
        return others[0] if others else None

    for i, e in enumerate(entries):
        if e.kind not in ("decision", "forced"):
            continue
        d = e.data
        player = d["player"]
        if player not in counts:
            continue
        choice = str(d["choice"])

        if d["decision_kind"] == "influence_action":
            if choice.startswith("add_blood:"):
                counts[player]["pool_spent_add_blood"] += 1
            elif choice.startswith("remove_blood:"):
                counts[player]["pool_gained_remove_blood"] += 1
            continue

        if d["decision_kind"] != "action_choice":
            continue

        if choice.startswith(_RECRUIT_CHOICE_PREFIX):
            end = _resolution_window_end(entries, i + 1)
            counts[player]["recruit_count"] += 1
            counts[player]["pool_spent_recruit"] += _pool_lost_by(entries, i + 1, end, player)
        elif choice == ACTION_BLEED:
            other = other_of(player)
            if other is None:
                continue
            end = _resolution_window_end(entries, i + 1)
            counts[player]["bleed_pool_dealt"] += _pool_lost_by(entries, i + 1, end, other)
            if _ousted_within(entries, i + 1, end, other):
                counts[player]["lethal_bleed_count"] += 1

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
    """True if the ousted player's last pool loss traces to their own
    voluntary, pool-spending decision (OQ-41/42). Forced own-pool ousts
    are legal (OQ-43), not flagged."""
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
