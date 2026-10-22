"""Bot-vs-bot matches via `sim.run_match`/`run_many` (CLAUDE.md milestone 4).

A full manual 1,000-seed run of the Brujah-mirror matchup (both players on
the real `data/decks/vekn-2p/brujah.json` suggested decklist, chosen because
a mirror match is what actually exercises the 2P variant's "contested
crypt cards" override) came back with zero crashes and zero stuck games
(turns played ranged 22-121); this test commits a much smaller batch (fast
enough for routine `pytest` runs) as an ongoing regression guard, not as a
restatement of that full run.
"""

import json
from pathlib import Path

import krcg
import pytest

from vtesbot.decks import check_and_build, load_resolved_fixture
from vtesbot.engine import CryptCard, LibraryCard
from vtesbot.engine.setup import DeckSpec
from vtesbot.formats import load_allowed_list
from vtesbot.sim import run_many, run_match
from vtesbot.sim.invariants import ECONOMIC_FIELDS

KNOWN_RANDOM_AGENT_STALLS = {12}
"""Brujah-mirror seeds where two `RandomLegalAgent`s are still undecided at
the turn cap (ENG-047): the game stays winnable (P2 can gather blood on one
vampire via remove/add transfers) but uniform random choices never commit."""


def _tiny_deck(prefix: str) -> DeckSpec:
    crypt = [
        CryptCard(krcg_id=i, name=f"{prefix}-crypt-{i}", capacity=3, group=5) for i in range(12)
    ]
    library = [
        LibraryCard(krcg_id=1000 + i, name=f"{prefix}-lib-{i}", card_type="master")
        for i in range(40)
    ]
    return DeckSpec(crypt=crypt, library=library)


def test_single_match_runs_to_completion():
    decks = {"P1": _tiny_deck("P1"), "P2": _tiny_deck("P2")}
    result = run_match(decks, turn_order=["P1", "P2"], seed=1, max_turns=500)

    assert result.game_over
    assert not result.stuck
    assert result.winner in ("P1", "P2")
    assert result.turns_played > 0
    assert len(result.log.entries) > 0
    assert set(result.economic_counts) == {"P1", "P2"}
    assert all(field in result.economic_counts["P1"] for field in ECONOMIC_FIELDS)
    assert any(
        result.economic_counts[p][field]
        for p in ("P1", "P2")
        for field in ("pool_spent_add_blood", "bleed_pool_dealt")
    )


def test_run_match_is_deterministic_for_a_given_seed():
    decks = {"P1": _tiny_deck("P1"), "P2": _tiny_deck("P2")}
    result_a = run_match(decks, turn_order=["P1", "P2"], seed=99, max_turns=500)
    result_b = run_match(decks, turn_order=["P1", "P2"], seed=99, max_turns=500)

    assert result_a.winner == result_b.winner
    assert result_a.turns_played == result_b.turns_played
    assert [e.data for e in result_a.log.entries] == [e.data for e in result_b.log.entries]


@pytest.fixture(scope="module")
def brujah_deck() -> DeckSpec:
    repo_root = Path(__file__).resolve().parents[2]
    allowed = load_allowed_list(repo_root / "data" / "formats" / "2p" / "2026-10-03.json")
    cards: krcg.CardDict = krcg.load()
    fixture = json.loads(
        (repo_root / "data" / "decks" / "vekn-2p" / "brujah.json").read_text(encoding="utf-8")
    )
    resolved = load_resolved_fixture(fixture)
    result = check_and_build(resolved, allowed, cards, name=fixture["name"])
    assert result.legal, result.violations
    assert result.deck_spec is not None
    return result.deck_spec


def test_brujah_mirror_batch_has_no_crashes_or_stuck_games(brujah_deck):
    decks = {"P1": brujah_deck, "P2": brujah_deck}
    batch = run_many(decks, turn_order=["P1", "P2"], seeds=range(20), max_turns=500)

    assert batch.crashes == []
    assert set(batch.stuck_seeds) <= KNOWN_RANDOM_AGENT_STALLS
    assert len(batch.results) == 20


def test_report_dir_defaults_to_no_file_io(tmp_path: Path):
    """`report_dir` is opt-in (CLAUDE.md milestone-4 verification helper, not
    a mature-run default): omitting it must not touch disk at all."""
    decks = {"P1": _tiny_deck("P1"), "P2": _tiny_deck("P2")}
    run_match(decks, turn_order=["P1", "P2"], seed=1, max_turns=500)
    run_many(decks, turn_order=["P1", "P2"], seeds=range(3), max_turns=500)

    assert list(tmp_path.iterdir()) == []


def test_run_match_report_dir_writes_a_match_report(tmp_path: Path):
    decks = {"P1": _tiny_deck("P1"), "P2": _tiny_deck("P2")}
    run_match(decks, turn_order=["P1", "P2"], seed=1, max_turns=500, report_dir=tmp_path)

    assert (tmp_path / "1.summary.txt").exists()
    assert (tmp_path / "1.decisions.log").exists()


def test_run_many_report_dir_writes_a_batch_report(brujah_deck, tmp_path: Path):
    decks = {"P1": brujah_deck, "P2": brujah_deck}
    batch = run_many(
        decks,
        turn_order=["P1", "P2"],
        seeds=range(5),
        max_turns=500,
        report_dir=tmp_path,
        report_sample_count=2,
    )

    assert (tmp_path / "batch_results.csv").exists()
    assert (tmp_path / "crashes.log").exists()
    assert (tmp_path / "crashes.log").read_text(encoding="utf-8") == ""
    sample_files = sorted((tmp_path / "samples").iterdir())
    assert len(sample_files) == 4  # 2 samples x (summary + decisions)
    csv_rows = (tmp_path / "batch_results.csv").read_text(encoding="utf-8").splitlines()
    assert len(csv_rows) == len(batch.results) + 1  # header + one row per game


def test_alternating_seat_batch_is_clean(brujah_deck):
    """Seat-alternated Brujah mirror: no crash (incl. oust-activity invariant
    violations, which `run_match` raises), no stuck game."""
    from vtesbot.sim.benchmark import run_alternating

    batch = run_alternating({"P1": brujah_deck, "P2": brujah_deck}, range(20))

    assert batch.crashes == []
    assert set(batch.stuck_seeds) <= KNOWN_RANDOM_AGENT_STALLS
    assert len(batch.results) == 20
    assert all(set(r.final_pools) == {"P1", "P2"} for r in batch.results)


@pytest.mark.xfail(strict=True, reason="random-agent stall, see KNOWN_RANDOM_AGENT_STALLS")
@pytest.mark.parametrize("seed", sorted(KNOWN_RANDOM_AGENT_STALLS))
def test_known_random_agent_stall_still_stalls(brujah_deck, seed):
    """Strict xfail: fails loudly once this seed finishes, so the known-stall
    list cannot silently go stale."""
    decks = {"P1": brujah_deck, "P2": brujah_deck}
    result = run_match(decks, turn_order=["P1", "P2"], seed=seed, max_turns=500)
    assert not result.stuck


@pytest.mark.parametrize("seed", [270, 942])
def test_fame_oust_mid_combat_seeds_do_not_crash(brujah_deck, seed):
    """Regression: GameOverError 'mend_damage' requested after game over."""
    from vtesbot.sim.benchmark import run_alternating

    batch = run_alternating({"P1": brujah_deck, "P2": brujah_deck}, [seed])

    assert batch.crashes == []
    assert batch.results[0].game_over
