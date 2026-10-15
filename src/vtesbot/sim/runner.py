"""Bot-vs-bot match runner (CLAUDE.md §5 `sim/`). Wraps `setup_game` +
`run_until_game_over`: one top-level `seed` deterministically derives the
setup seed and each agent's seed."""

import random
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from vtesbot.agents import RandomLegalAgent
from vtesbot.engine.agent import Agent
from vtesbot.engine.log import ReplayLog
from vtesbot.engine.phases.turn import run_until_game_over
from vtesbot.engine.setup import DeckSpec, setup_game

from .invariants import action_counts, check_no_activity_after_oust, is_self_oust
from .report import write_batch_report, write_match_report

AgentFactory = Callable[[str, int], Agent]


@dataclass(frozen=True)
class MatchResult:
    seed: int
    turns_played: int
    game_over: bool
    winner: str | None
    victory_points: dict[str, int]
    log: ReplayLog
    final_pools: dict[str, int] = field(default_factory=dict)
    action_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    self_oust: bool = False

    @property
    def stuck(self) -> bool:
        """Hit `max_turns` without anyone being ousted -- a genuine property
        of this match's play (e.g. two purely-random agents stalling), not
        necessarily an engine bug; see `run_many` for batch-level triage."""
        return not self.game_over

    @property
    def tie(self) -> bool:
        """Simultaneous oust of both Methuselahs (OQ-44): over, no winner."""
        return self.game_over and self.winner is None


def run_match(
    decks: Mapping[str, DeckSpec],
    turn_order: Sequence[str],
    seed: int,
    *,
    agent_factory: AgentFactory = RandomLegalAgent,
    max_turns: int = 1000,
    report_dir: Path | None = None,
) -> MatchResult:
    """Runs one seeded match. `report_dir` (default `None`) opts in to a
    persisted summary + decision-log transcript (`write_match_report`)."""
    seed_source = random.Random(seed)
    setup_seed = seed_source.randrange(2**31)
    agents = {p: agent_factory(p, seed_source.randrange(2**31)) for p in turn_order}

    state = setup_game(decks, agents, turn_order=turn_order, seed=setup_seed)
    run_until_game_over(state, max_turns=max_turns)

    check_no_activity_after_oust(state.log)
    result = MatchResult(
        seed=seed,
        turns_played=state.turn_number,
        game_over=state.game_over,
        winner=state.winner,
        victory_points=dict(state.victory_points),
        log=state.log,
        final_pools={p: ps.pool for p, ps in state.players.items()},
        action_counts=action_counts(state.log, list(turn_order)),
        self_oust=is_self_oust(state.log),
    )
    if report_dir is not None:
        write_match_report(result, report_dir)
    return result


@dataclass
class BatchResult:
    results: list[MatchResult] = field(default_factory=list)
    crashes: list[tuple[int, BaseException]] = field(default_factory=list)

    @property
    def stuck_seeds(self) -> list[int]:
        return [r.seed for r in self.results if r.stuck]

    @property
    def tie_seeds(self) -> list[int]:
        return [r.seed for r in self.results if r.tie]


def run_many(
    decks: Mapping[str, DeckSpec],
    turn_order: Sequence[str],
    seeds: Iterable[int],
    *,
    agent_factory: AgentFactory = RandomLegalAgent,
    max_turns: int = 1000,
    report_dir: Path | None = None,
    report_sample_count: int = 3,
) -> BatchResult:
    """Runs `run_match` per seed, catching exceptions so one bad seed
    doesn't hide the rest (milestone 4). `report_dir` opts in to
    `write_batch_report`'s CSV/crash-log/sample output."""
    batch = BatchResult()
    for seed in seeds:
        try:
            batch.results.append(
                run_match(decks, turn_order, seed, agent_factory=agent_factory, max_turns=max_turns)
            )
        except Exception as exc:  # intentionally broad: this is a crash collector
            batch.crashes.append((seed, exc))
    if report_dir is not None:
        write_batch_report(batch, report_dir, sample_count=report_sample_count)
    return batch
