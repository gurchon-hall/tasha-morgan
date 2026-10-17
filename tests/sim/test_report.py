"""Readable match-report rendering (`vtesbot.sim.report`)."""

from pathlib import Path

from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.log import ReplayLog
from vtesbot.sim import MatchResult, format_decision_log, format_summary, write_match_report


def _sample_result() -> MatchResult:
    log = ReplayLog()
    log.record_random("P1 shuffles library", ["Alpha", "Beta"])
    decision = Decision(
        player="P1", kind="minion_phase_choice", choices=(Choice("end_minion_phase", "End"),)
    )
    log.record_decision(decision, decision.choices[0])
    return MatchResult(
        seed=123,
        turns_played=7,
        game_over=True,
        winner="P1",
        victory_points={"P1": 2, "P2": 0},
        log=log,
    )


def test_format_summary_mentions_seed_outcome_and_victory_points():
    text = format_summary(_sample_result())
    assert "seed=123" in text
    assert "winner=P1" in text
    assert "P1=2" in text
    assert "P2=0" in text


def test_format_summary_reports_stuck_when_not_game_over():
    stuck = MatchResult(
        seed=1, turns_played=500, game_over=False, winner=None, victory_points={}, log=ReplayLog()
    )
    text = format_summary(stuck)
    assert "STUCK" in text


def test_format_decision_log_includes_every_entry():
    text = format_decision_log(_sample_result().log)
    lines = text.splitlines()
    assert len(lines) == 2
    assert "P1 shuffles library" in lines[0]
    assert "['Alpha', 'Beta']" in lines[0]
    assert "P1 minion_phase_choice" in lines[1]
    assert "end_minion_phase" in lines[1]


def test_format_decision_log_renders_event_entries():
    log = ReplayLog()
    log.record_event("P2 is OUSTED -- P1 wins (VP=2, pool=16)")

    text = format_decision_log(log)

    assert text == "[event] P2 is OUSTED -- P1 wins (VP=2, pool=16)"


def test_write_match_report_writes_both_files(tmp_path: Path):
    result = _sample_result()
    summary_path, decisions_path = write_match_report(result, tmp_path)

    assert summary_path == tmp_path / "123.summary.txt"
    assert decisions_path == tmp_path / "123.decisions.log"
    assert summary_path.read_text(encoding="utf-8").strip() == format_summary(result)
    assert decisions_path.read_text(encoding="utf-8").strip() == format_decision_log(result.log)


def test_format_summary_reports_a_tie_distinctly_from_stuck():
    tie = MatchResult(
        seed=2,
        turns_played=9,
        game_over=True,
        winner=None,
        victory_points={"P1": 1, "P2": 1},
        log=ReplayLog(),
    )
    assert tie.tie and not tie.stuck
    text = format_summary(tie)
    assert "TIE" in text and "STUCK" not in text


def test_benchmark_summaries_count_ties_separately():
    from vtesbot.sim.benchmark import summarize, summarize_versus
    from vtesbot.sim.runner import BatchResult

    tie = MatchResult(
        seed=2, turns_played=9, game_over=True, winner=None, victory_points={}, log=ReplayLog()
    )
    batch = BatchResult(results=[_sample_result(), tie])
    assert batch.tie_seeds == [2]
    assert batch.stuck_seeds == []
    assert "ties=1" in summarize(batch)
    assert "ties=1" in summarize_versus(batch, 500)


def test_write_batch_report_adds_economic_columns_after_action_columns(tmp_path: Path):
    """Phase A (`tmp/heuristic-agent-audit-plan.md`): the new `{player}_
    {field}` columns are purely additive, placed after the existing
    action-count columns."""
    from vtesbot.sim import write_batch_report
    from vtesbot.sim.invariants import ACTION_NAMES, ECONOMIC_FIELDS
    from vtesbot.sim.runner import BatchResult

    r1 = MatchResult(
        seed=1,
        turns_played=5,
        game_over=True,
        winner="P1",
        victory_points={"P1": 2},
        log=ReplayLog(),
        final_pools={"P1": 20, "P2": 0},
        economic_counts={"P1": {"bleed_pool_dealt": 3}, "P2": {}},
    )
    r2 = MatchResult(
        seed=2,
        turns_played=7,
        game_over=True,
        winner="P2",
        victory_points={"P2": 2},
        log=ReplayLog(),
        final_pools={"P1": 0, "P2": 20},
    )
    batch = BatchResult(results=[r1, r2])

    write_batch_report(batch, tmp_path)

    rows = (tmp_path / "batch_results.csv").read_text(encoding="utf-8").splitlines()
    header = rows[0].split(",")
    players = ["P1", "P2"]
    expected_len = (
        8 + len(players) + len(players) * len(ACTION_NAMES) + len(players) * len(ECONOMIC_FIELDS)
    )
    assert len(header) == expected_len
    for p in players:
        for f in ECONOMIC_FIELDS:
            assert f"{p}_{f}" in header

    last_action_col = max(header.index(f"{p}_{a}") for p in players for a in ACTION_NAMES)
    first_economic_col = min(header.index(f"{p}_{f}") for p in players for f in ECONOMIC_FIELDS)
    assert first_economic_col > last_action_col

    data_row = rows[1].split(",")
    assert data_row[header.index("P1_bleed_pool_dealt")] == "3"
    assert data_row[header.index("P2_bleed_pool_dealt")] == "0"


def test_sample_losses_and_ties_reaches_a_loss_buried_past_sample_count(tmp_path: Path):
    """A P1 loss past the first `sample_count` wins only gets a `samples/`
    decision log when `sample_losses_and_ties=True` (opt-in default-off,
    so existing callers are unaffected)."""
    from vtesbot.sim import write_batch_report
    from vtesbot.sim.runner import BatchResult

    wins = [
        MatchResult(
            seed=s, turns_played=1, game_over=True, winner="P1", victory_points={}, log=ReplayLog()
        )
        for s in range(5)
    ]
    buried_loss = MatchResult(
        seed=99, turns_played=1, game_over=True, winner="P2", victory_points={}, log=ReplayLog()
    )
    batch = BatchResult(results=[*wins, buried_loss])

    write_batch_report(batch, tmp_path / "off", sample_count=3)
    assert not (tmp_path / "off" / "samples" / "99.summary.txt").exists()

    write_batch_report(batch, tmp_path / "on", sample_count=3, sample_losses_and_ties=True)
    assert (tmp_path / "on" / "samples" / "99.summary.txt").exists()
