import pytest

from vtesbot.engine.log import LogEntry, ReplayLog
from vtesbot.sim import InvariantViolation, check_no_activity_after_oust
from vtesbot.sim.invariants import is_self_oust


def _dec(player: str, kind: str, choice: str) -> LogEntry:
    return LogEntry("decision", {"player": player, "decision_kind": kind, "choice": choice})


def _ev(text: str) -> LogEntry:
    return LogEntry("event", {"description": text})


def _bad_log() -> ReplayLog:
    """Shape of the real bad log (seed 0 excerpt): decisions after the oust."""
    return ReplayLog(
        [
            _dec("P2", "minion_phase_choice", "end_minion_phase"),
            _dec("P2", "influence_action", "add_blood:P2-V2"),
            _ev("P2 loses 1 pool (now 0)"),
            _ev("P2 is OUSTED -- P1 wins (VP=2, pool=20)"),
            _dec("P2", "influence_action", "remove_blood:P2-V8"),
            _ev("P2 gains 1 pool (now 1)"),
        ]
    )


def test_oust_followed_by_events_only_passes():
    log = _bad_log()
    del log.entries[4]
    check_no_activity_after_oust(log)


def test_log_without_oust_passes():
    check_no_activity_after_oust(ReplayLog([_dec("P1", "x", "y")]))


def test_decision_after_oust_fails():
    with pytest.raises(InvariantViolation):
        check_no_activity_after_oust(_bad_log())


def test_random_after_oust_fails():
    log = ReplayLog([_ev("P2 is OUSTED -- P1 wins"), LogEntry("random", {"description": "d"})])
    with pytest.raises(InvariantViolation):
        check_no_activity_after_oust(log)


def test_self_oust_detected_from_own_influence_action():
    assert is_self_oust(_bad_log())


def test_oust_by_opponent_bleed_is_not_self_oust():
    log = ReplayLog(
        [
            _dec("P1", "action_choice", "bleed"),
            _ev("P2 loses 1 pool (now 0)"),
            _ev("P2 is OUSTED -- P1 wins"),
        ]
    )
    assert not is_self_oust(log)


def test_activity_after_a_simultaneous_oust_tie_is_a_violation():
    log = ReplayLog(
        [
            _ev("P1 is OUSTED -- simultaneous ousts, TIE, no winner (VP=1)"),
            _ev("P2 is OUSTED -- simultaneous ousts, TIE, no winner (VP=1)"),
            LogEntry("random", {"description": "d"}),
        ]
    )
    with pytest.raises(InvariantViolation):
        check_no_activity_after_oust(log)


def test_forced_fame_burn_after_a_yield_is_not_a_self_oust():
    """OQ-43: a forced own-pool oust stays legal and must not be flagged; the
    nearest decision (a contest `yield`) spent nothing."""
    log = ReplayLog(
        [
            _dec("P1", "contest_resolution", "yield"),
            _ev("P1 loses 1 pool (now 0)"),
            _ev("P1 is OUSTED -- P2 wins"),
        ]
    )
    assert not is_self_oust(log)


def test_forced_burn_after_unrelated_intervening_decision_is_not_a_self_oust():
    log = ReplayLog(
        [
            _dec("P1", "contest_resolution", "pay"),
            _ev("P1 loses 1 pool (now 3)"),
            _dec("P1", "mend_damage", "0"),
            _ev("P1 loses 3 pool (now 0)"),
            _ev("P1 is OUSTED -- P2 wins"),
        ]
    )
    assert not is_self_oust(log)


def test_paying_the_last_pool_for_a_contest_is_a_self_oust():
    log = ReplayLog(
        [
            _dec("P1", "contest_resolution", "pay"),
            _ev("P1 loses 1 pool (now 0)"),
            _ev("P1 is OUSTED -- P2 wins"),
        ]
    )
    assert is_self_oust(log)


def test_forced_yield_after_a_voluntary_pay_is_not_a_self_oust():
    """The forced (auto-resolved) yield is the nearest decision, so the
    earlier voluntary `pay` is not blamed for the later forced Fame oust."""
    log = ReplayLog(
        [
            _dec("P1", "contest_resolution", "pay"),
            LogEntry(
                "forced", {"player": "P1", "decision_kind": "contest_resolution", "choice": "yield"}
            ),
            _ev("P1 loses 1 pool (now 0)"),
            _ev("P1 is OUSTED -- P2 wins"),
        ]
    )
    assert not is_self_oust(log)


def test_ending_a_phase_spends_nothing():
    log = ReplayLog(
        [
            _dec("P1", "influence_action", "end_phase"),
            _ev("P1 loses 1 pool (now 0)"),
            _ev("P1 is OUSTED -- P2 wins"),
        ]
    )
    assert not is_self_oust(log)


def test_forced_entry_after_oust_is_a_violation():
    log = ReplayLog(
        [_ev("P2 is OUSTED -- P1 wins"), LogEntry("forced", {"player": "P1", "choice": "x"})]
    )
    with pytest.raises(InvariantViolation):
        check_no_activity_after_oust(log)
