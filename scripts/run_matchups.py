"""Seat-alternated batch run between two independently chosen deck/agent
sides.

Usage:
    python scripts/run_matchups.py --p1-deck brujah --p1-agent heuristic \\
        --p2-deck toreador --p2-agent random [--games 1000] \\
        [--sample-count 5] [--seed-start 0]

Odd-vs-even seeds alternate which side moves first (`benchmark.py`'s
`run_alternating`), so across the batch each side gets a 50/50 split of
starting seat -- P1/P2 labels stay fixed to the chosen deck/agent, only the
turn order swaps.

Writes the batch report (`report.py::write_batch_report`) under
`logs/games/<p1_agent>_<p1_deck>_vs_<p2_agent>_<p2_deck>/`, so every
deck/agent combination gets its own directory and never overwrites another
one's report.
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p1-deck", required=True, help="deck name under data/decks/vekn-2p/")
    parser.add_argument("--p1-agent", required=True, choices=sorted(AGENTS))
    parser.add_argument("--p2-deck", required=True, help="deck name under data/decks/vekn-2p/")
    parser.add_argument("--p2-agent", required=True, choices=sorted(AGENTS))
    parser.add_argument("--games", type=int, default=1000)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--sample-count", type=int, default=5)
    parser.add_argument(
        "--log-root",
        type=Path,
        default=REPO_ROOT / "logs" / "games",
        help="base directory for batch reports (default: logs/games)",
    )
    args = parser.parse_args()

    decks = {
        "P1": load_suggested_deck(args.p1_deck),
        "P2": load_suggested_deck(args.p2_deck),
    }
    agent_by_player = {"P1": AGENTS[args.p1_agent], "P2": AGENTS[args.p2_agent]}

    def agent_factory(player_id: str, seed: int) -> Agent:
        return agent_by_player[player_id](player_id, seed)

    seeds = range(args.seed_start, args.seed_start + args.games)
    batch = run_alternating(decks, seeds, agent_factory=agent_factory)

    label = f"{args.p1_agent}_{args.p1_deck}_vs_{args.p2_agent}_{args.p2_deck}"
    print(f"=== {label} ===")
    print(summarize(batch))
    for seed, exc in batch.crashes:
        print(f"CRASH seed={seed}: {type(exc).__name__}: {exc}")

    report_dir = args.log_root / label
    write_batch_report(batch, report_dir, sample_count=args.sample_count)
    print(f"report written to {report_dir}")


if __name__ == "__main__":
    main()
