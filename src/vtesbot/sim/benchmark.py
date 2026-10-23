"""Seat-alternated batch benchmark: `python -m vtesbot.sim.benchmark [N]`."""

import functools
import json
import math
import sys
from collections.abc import Mapping
from pathlib import Path

import krcg

from vtesbot.agents import HeuristicAgent, RandomLegalAgent
from vtesbot.decks import check_and_build, load_resolved_fixture
from vtesbot.engine.agent import Agent
from vtesbot.engine.setup import DeckSpec
from vtesbot.formats import load_allowed_list

from .invariants import ACTION_NAMES, ECONOMIC_FIELDS
from .runner import AgentFactory, BatchResult, run_match

_ROOT = Path(__file__).resolve().parents[3]
_krcg_cards = functools.cache(krcg.load)  # ~0.8s per load; read-only after


def load_suggested_deck(name: str = "brujah") -> DeckSpec:
    allowed = load_allowed_list(_ROOT / "data" / "formats" / "2p" / "2026-10-03.json")
    fixture = json.loads((_ROOT / "data" / "decks" / "vekn-2p" / f"{name}.json").read_text("utf-8"))
    result = check_and_build(
        load_resolved_fixture(fixture), allowed, _krcg_cards(), name=fixture["name"]
    )
    assert result.legal and result.deck_spec is not None, result.violations
    return result.deck_spec


def run_alternating(
    decks: Mapping[str, DeckSpec],
    seeds: range | list[int],
    *,
    max_turns: int = 500,
    agent_factory: AgentFactory = RandomLegalAgent,
) -> BatchResult:
    """Odd seeds seat P2 first, so each Methuselah gets both seats."""
    batch = BatchResult()
    for seed in seeds:
        order = ["P1", "P2"] if seed % 2 == 0 else ["P2", "P1"]
        try:
            batch.results.append(
                run_match(decks, order, seed, agent_factory=agent_factory, max_turns=max_turns)
            )
        except Exception as exc:
            batch.crashes.append((seed, exc))
    return batch


def summarize(batch: BatchResult) -> str:
    rs = batch.results
    n = len(rs) or 1
    first_wins = sum(1 for r in rs if r.winner == _first_seat(r.seed))
    lines = [
        f"games={len(rs)} crashes={len(batch.crashes)} stuck={len(batch.stuck_seeds)} "
        f"ties={len(batch.tie_seeds)}",
        f"first-seat win rate: {first_wins / n:.3f}",
        f"P1 win rate: {sum(r.winner == 'P1' for r in rs) / n:.3f}",
        f"self-oust share: {sum(r.self_oust for r in rs) / n:.3f}",
        f"mean turns: {sum(r.turns_played for r in rs) / n:.1f}",
    ]
    for a in ACTION_NAMES:
        mean = sum(c.get(a, 0) for r in rs for c in r.action_counts.values()) / n
        lines.append(f"mean {a} per game (both players): {mean:.1f}")
    return "\n".join(lines)


def heuristic_vs_random_factory(player_id: str, seed: int) -> Agent:
    cls = HeuristicAgent if player_id == "P1" else RandomLegalAgent
    return cls(player_id, seed)


def heuristic_vs_heuristic_factory(player_id: str, seed: int) -> Agent:
    """Both seats `HeuristicAgent`, independently seeded (`run_alternating`
    already passes a distinct `seed` per seed/matchup via `run_match`'s own
    `seed_source`). Deck-agnostic by design -- the caller still supplies
    both decks through `decks=` to `run_alternating`/`run_many`, same as
    every other factory here; this just decides which agent class sits in
    each seat."""
    return HeuristicAgent(player_id, seed)


def wilson_interval(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (centre - half, centre + half)


def summarize_versus(batch: BatchResult, max_turns: int) -> str:
    """P1 is the HeuristicAgent, P2 the RandomLegalAgent; seats alternate by seed.

    Ties (simultaneous oust, DES-010) and stuck games count as non-wins for the heuristic."""
    rs = batch.results
    n = len(rs) or 1
    wins = sum(r.winner == "P1" for r in rs)
    lo, hi = wilson_interval(wins, len(rs))
    lines = [
        f"games={len(rs)} crashes={len(batch.crashes)} stuck(max_turns={max_turns})="
        f"{len(batch.stuck_seeds)} {batch.stuck_seeds[:10]} ties={len(batch.tie_seeds)}",
        f"heuristic wins={wins} losses={sum(r.winner == 'P2' for r in rs)} "
        f"win rate={wins / n:.3f} (95% Wilson {lo:.3f}-{hi:.3f})",
        f"first-seat win rate: {sum(r.winner == _first_seat(r.seed) for r in rs) / n:.3f}",
        f"mean turns: {sum(r.turns_played for r in rs) / n:.1f}",
    ]
    for a in ("reveal", "bleed", "hunt", "act_with", "add_blood", "remove_blood"):
        for p, label in (("P1", "heuristic"), ("P2", "random")):
            mean = sum(r.action_counts.get(p, {}).get(a, 0) for r in rs) / n
            lines.append(f"mean {a} per game [{label}]: {mean:.1f}")
    return "\n".join(lines)


def summarize_self_play(batch: BatchResult, max_turns: int) -> str:
    """Both seats run the identical `HeuristicAgent` (`heuristic_vs_
    heuristic_factory`) -- deliberately no "P1 is the good agent" framing
    like `summarize_versus`'s: a P1 win rate far from 50% here signals a
    bug (e.g. a hidden first-mover advantage), not strength, since there is
    no strength difference between the two seats to measure."""
    rs = batch.results
    n = len(rs) or 1
    wins = sum(r.winner == "P1" for r in rs)
    lo, hi = wilson_interval(wins, len(rs))
    lines = [
        f"games={len(rs)} crashes={len(batch.crashes)} stuck(max_turns={max_turns})="
        f"{len(batch.stuck_seeds)} {batch.stuck_seeds[:10]} ties={len(batch.tie_seeds)}",
        f"P1 win rate={wins / n:.3f} (95% Wilson {lo:.3f}-{hi:.3f})",
        f"first-seat win rate: {sum(r.winner == _first_seat(r.seed) for r in rs) / n:.3f}",
        f"mean turns: {sum(r.turns_played for r in rs) / n:.1f}",
    ]
    for field in ECONOMIC_FIELDS:
        for p in ("P1", "P2"):
            mean = sum(r.economic_counts.get(p, {}).get(field, 0) for r in rs) / n
            lines.append(f"mean {field} per game [{p}]: {mean:.1f}")
    return "\n".join(lines)


def summarize_position_swap(batch_a: BatchResult, batch_b: BatchResult) -> str:
    """`batch_a`/`batch_b`: the same seeds run twice with the P1/P2 agent
    assignment swapped between the two calls (the caller's own `agent_
    factory` choice, not done here). Reports the P1-win-rate delta over the
    seeds common to both -- isolates whether *this exact seed's* outcome
    flips when sides are swapped, which `run_alternating`'s own within-
    batch seat alternation (by seed parity, across *different* seeds)
    cannot answer; a first-mover artifact shows up here as a nonzero delta
    even when the same agent class occupies both seats across the two
    batches."""
    seeds_a = {r.seed: r for r in batch_a.results}
    seeds_b = {r.seed: r for r in batch_b.results}
    common = sorted(set(seeds_a) & set(seeds_b))
    n = len(common) or 1
    rate_a = sum(seeds_a[s].winner == "P1" for s in common) / n
    rate_b = sum(seeds_b[s].winner == "P1" for s in common) / n
    return (
        f"seeds_compared={len(common)}\n"
        f"batch_a P1 win rate={rate_a:.3f}\n"
        f"batch_b P1 win rate={rate_b:.3f}\n"
        f"delta (a - b)={rate_a - rate_b:+.3f}"
    )


def _first_seat(seed: int) -> str:
    return "P1" if seed % 2 == 0 else "P2"


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    mode = sys.argv[2] if len(sys.argv) > 2 else None
    deck = load_suggested_deck()
    if mode == "selfplay":
        batch = run_alternating(
            {"P1": deck, "P2": deck}, range(n), agent_factory=heuristic_vs_heuristic_factory
        )
        print(summarize_self_play(batch, 500))
    elif mode == "versus":
        batch = run_alternating(
            {"P1": deck, "P2": deck}, range(n), agent_factory=heuristic_vs_random_factory
        )
        print(summarize_versus(batch, 500))
    else:
        batch = run_alternating({"P1": deck, "P2": deck}, range(n), agent_factory=RandomLegalAgent)
        print(summarize(batch))
    for seed, exc in batch.crashes:
        print(f"CRASH seed={seed}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
