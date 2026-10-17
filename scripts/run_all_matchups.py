"""Seat-alternated batch runs for every deck-vs-deck pairing in `DECKS`
(including a deck against itself), both sides piloted by the same `--agent`.
For each of the `len(DECKS) ** 2` matchups, runs `run_alternating` over the
requested seed range (P1/P2 seats swap by seed parity), prints a one-line
summary plus any crashes, and writes a full `write_batch_report` (CSV +
sample decision logs) under `--log-root/<agent>_<deck1>_vs_<agent>_<deck2>`.

Examples:
    python scripts/run_all_matchups.py --agent heuristic
    python scripts/run_all_matchups.py --agent random --games 200 --seed-start 1000
    python scripts/run_all_matchups.py --agent heuristic --sample-count 10 \\
        --log-root logs/heuristic-audit
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vtesbot.agents import HeuristicAgent, RandomLegalAgent  # noqa: E402
from vtesbot.engine.agent import Agent  # noqa: E402
from vtesbot.sim.benchmark import load_suggested_deck, run_alternating, summarize  # noqa: E402
from vtesbot.sim.report import write_batch_report  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

AGENTS = {
    "random": RandomLegalAgent,
    "heuristic": HeuristicAgent,
}

DECKS = ["brujah", "toreador", "ventrue"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", required=True, choices=sorted(AGENTS))
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--sample-count", type=int, default=5)
    parser.add_argument(
        "--log-root",
        type=Path,
        default=REPO_ROOT / "logs" / "games",
        help="base directory for batch reports (default: logs/games)",
    )
    args = parser.parse_args()

    agent_by_player = {"P1": AGENTS[args.agent], "P2": AGENTS[args.agent]}

    def agent_factory(player_id: str, seed: int) -> Agent:
        return agent_by_player[player_id](player_id, seed)

    seeds = range(args.seed_start, args.seed_start + args.games)

    for d1 in DECKS:
        for d2 in DECKS:
            decks = {
                "P1": load_suggested_deck(d1),
                "P2": load_suggested_deck(d2),
            }

            batch = run_alternating(decks, seeds, agent_factory=agent_factory)

            label = f"{args.agent}_{d1}_vs_{args.agent}_{d2}"
            print(f"=== {label} ===")
            print(summarize(batch))
            for seed, exc in batch.crashes:
                print(f"CRASH seed={seed}: {type(exc).__name__}: {exc}")

            report_dir = args.log_root / label
            write_batch_report(batch, report_dir, sample_count=args.sample_count)
            print(f"report written to {report_dir}")


if __name__ == "__main__":
    main()
