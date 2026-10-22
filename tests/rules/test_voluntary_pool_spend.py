"""DES-009 (user ruling 2026-10-13, 2P-duel project simplification; see
DES-009): a Methuselah may not bring their own pool to 0
through their own voluntary choices. Central helper:
`engine/pool.py::can_afford_without_ousting` / `max_voluntary_spend`.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine.allies import detect_contest_on_recruit, recruit_ally
from vtesbot.engine.attachments import attach_card, detect_contest_on_attach
from vtesbot.engine.master_cards import (
    bring_master_card_into_play,
    detect_contest_on_bring_into_play,
)
from vtesbot.engine.phases.unlock import unlock_phase
from vtesbot.engine.politics import variable_pool_burn_vote_options
from vtesbot.engine.pool import can_afford_without_ousting, max_voluntary_spend


@pytest.mark.parametrize(
    ("pool", "amount", "ok", "cap"),
    [(0, 1, False, 0), (1, 1, False, 0), (2, 1, True, 1), (5, 4, True, 4), (5, 5, False, 4)],
)
def test_helper(pool, amount, ok, cap):
    game = ScenarioBuilder(seed=1).player("P1", pool=pool).player("P2", pool=5).build()
    assert can_afford_without_ousting(game.state, "P1", amount) is ok
    assert max_voluntary_spend(game.state, "P1") == cap


@pytest.mark.parametrize(("pool", "expected"), [(0, []), (1, []), (2, [1]), (4, [1, 2, 3])])
def test_burn_for_votes_is_capped_at_pool_minus_one(pool, expected):
    game = ScenarioBuilder(seed=1).player("P1", pool=pool).player("P2", pool=5).build()
    options = variable_pool_burn_vote_options(
        game.state,
        "P1",
        source_id_prefix="src",
        label="L",
        votes_per_pool=2,
        pending={"extra_sources": []},
    )
    assert [o.choice.value for o in options] == [f"src:{x}" for x in expected]


def _contest_choices(kind: str, pool: int, setup) -> list[str]:
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=pool).ready_vampire("V1", capacity=3, blood=1)
    builder.player("P2", pool=10).ready_vampire("V2", capacity=3, blood=1)
    game = builder.build()
    setup(game)
    seen: list[str] = []

    class Rec(ScriptedAgent):
        def decide(self, observation, decision):
            if decision.kind == kind:
                seen.extend(c.value for c in decision.choices)
                return next(c for c in decision.choices if c.value == "yield")
            return decision.choices[0]

    game.state.agents["P1"] = Rec("P1")
    unlock_phase(game.state, "P1")
    assert game.state.game_over is False
    return seen


def _crypt(game):
    game.vampire("V1").contested_with = "V2"
    game.vampire("V2").contested_with = "V1"


def _ally(game):
    kw = {"krcg_id": 102217, "name": "47th Street Royals", "life": 2}
    recruit_ally(game.state, "P2", **kw)
    detect_contest_on_recruit(game.state, recruit_ally(game.state, "P1", **kw))


def _attachment(game):
    kw = {"krcg_id": 100698, "name": "Fame"}
    attach_card(game.state, game.vampire("V2"), controller="P2", **kw)
    detect_contest_on_attach(
        game.state, attach_card(game.state, game.vampire("V1"), controller="P1", **kw)
    )


def _master(game):
    kw = {"krcg_id": 102180, "name": "Wider View"}
    bring_master_card_into_play(game.state, "P2", **kw)
    detect_contest_on_bring_into_play(
        game.state, bring_master_card_into_play(game.state, "P1", **kw)
    )


CONTESTS = [
    ("contest_resolution", _crypt),
    ("ally_contest_resolution", _ally),
    ("attachment_contest_resolution", _attachment),
    ("master_card_contest_resolution", _master),
]


@pytest.mark.parametrize(("kind", "setup"), CONTESTS)
def test_contest_with_only_yield_left_is_resolved_without_a_decision(kind, setup):
    """DES-009: at pool 1 a pool-1 player is forced to yield every contested
    card; the lone choice is taken without a vacuous `Decision`."""
    assert _contest_choices(kind, 1, setup) == []


@pytest.mark.parametrize(("kind", "setup"), CONTESTS)
def test_contest_payment_offered_when_it_leaves_pool_1(kind, setup):
    assert _contest_choices(kind, 2, setup) == ["pay", "yield"]


def test_burn_for_votes_respects_a_pool_reserve():
    game = ScenarioBuilder(seed=1).player("P1", pool=4).player("P2", pool=5).build()
    options = variable_pool_burn_vote_options(
        game.state,
        "P1",
        source_id_prefix="src",
        label="L",
        votes_per_pool=2,
        pending={"extra_sources": [], "pool_reserve": {"P1": 1}},
    )
    assert [o.choice.value for o in options] == ["src:1", "src:2"]
