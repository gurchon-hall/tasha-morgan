"""`vtesbot.sim.benchmark` summaries (Phase A,
`tmp/heuristic-agent-audit-plan.md`): self-play baseline and position-swap
check, on top of the existing heuristic-vs-random `summarize_versus`."""

from vtesbot.sim.benchmark import (
    heuristic_vs_heuristic_factory,
    load_suggested_deck,
    run_alternating,
    summarize_position_swap,
    summarize_self_play,
)


def test_summarize_self_play_reports_labeled_lines_seeded_small_n():
    deck = load_suggested_deck()
    batch = run_alternating(
        {"P1": deck, "P2": deck}, range(6), agent_factory=heuristic_vs_heuristic_factory
    )

    text = summarize_self_play(batch, 500)

    assert batch.crashes == []
    assert "games=6" in text
    assert "P1 win rate=" in text
    assert "first-seat win rate:" in text
    assert "mean turns:" in text
    assert "mean bleed_pool_dealt per game [P1]:" in text
    assert "mean bleed_pool_dealt per game [P2]:" in text
    assert "mean recruit_count per game [P1]:" in text


def test_summarize_position_swap_reports_delta_between_two_same_seed_batches():
    deck = load_suggested_deck()
    seeds = range(4)
    normal = run_alternating(
        {"P1": deck, "P2": deck}, seeds, agent_factory=heuristic_vs_heuristic_factory
    )
    swapped = run_alternating(
        {"P1": deck, "P2": deck}, seeds, agent_factory=heuristic_vs_heuristic_factory
    )

    text = summarize_position_swap(normal, swapped)

    assert "seeds_compared=4" in text
    assert "batch_a P1 win rate=" in text
    assert "batch_b P1 win rate=" in text
    assert "delta (a - b)=" in text


def test_summarize_position_swap_only_compares_seeds_present_in_both_batches():
    deck = load_suggested_deck()
    batch_a = run_alternating(
        {"P1": deck, "P2": deck}, range(3), agent_factory=heuristic_vs_heuristic_factory
    )
    batch_b = run_alternating(
        {"P1": deck, "P2": deck}, range(1, 3), agent_factory=heuristic_vs_heuristic_factory
    )

    text = summarize_position_swap(batch_a, batch_b)

    assert "seeds_compared=2" in text
