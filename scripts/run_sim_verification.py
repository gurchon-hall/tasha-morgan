"""Implementation-phase verification run for milestone 4 (CLAUDE.md §9):
plays several bot-vs-bot matchups and persists every batch's outcome under
`logs/games/<matchup>/` via `sim.run_many`'s opt-in `report_dir` parameter,
so the "no crash or stuck state" claim can be checked from disk, not just a
printed summary. `logs/` is gitignored -- these are run artifacts, not
source.

Usage: python scripts/run_sim_verification.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import krcg  # noqa: E402

import vtesbot.cards  # noqa: E402,F401 (import for registration side effect)
from vtesbot.decks import check_and_build, load_resolved_fixture  # noqa: E402
from vtesbot.formats import load_allowed_list  # noqa: E402
from vtesbot.sim import run_many  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = REPO_ROOT / "logs" / "games"


def load_deck(name: str, allowed, cards):
    fixture = json.loads(
        (REPO_ROOT / "data" / "decks" / "vekn-2p" / f"{name}.json").read_text(encoding="utf-8")
    )
    resolved = load_resolved_fixture(fixture)
    result = check_and_build(resolved, allowed, cards, name=fixture["name"])
    assert result.legal, result.violations
    return result.deck_spec


def main() -> None:
    allowed = load_allowed_list(REPO_ROOT / "data" / "formats" / "2p" / "2026-10-03.json")
    cards: krcg.CardDict = krcg.load()
    decks = {name: load_deck(name, allowed, cards) for name in ("brujah", "ventrue", "toreador")}

    matchups = [
        ("brujah_vs_brujah", "brujah", "brujah", 1000),
        ("ventrue_vs_ventrue", "ventrue", "ventrue", 200),
        ("toreador_vs_toreador", "toreador", "toreador", 200),
        ("ventrue_vs_brujah", "ventrue", "brujah", 200),
        ("toreador_vs_brujah", "toreador", "brujah", 200),
        ("ventrue_vs_toreador", "ventrue", "toreador", 200),
    ]

    for label, deck_a, deck_b, count in matchups:
        batch = run_many(
            {"P1": decks[deck_a], "P2": decks[deck_b]},
            turn_order=["P1", "P2"],
            seeds=range(count),
            max_turns=500,
            report_dir=LOGS_DIR / label,
        )
        print(
            f"{label}: {len(batch.results)} games, {len(batch.crashes)} crashes, "
            f"{len(batch.stuck_seeds)} stuck -> {LOGS_DIR / label}"
        )


if __name__ == "__main__":
    main()
