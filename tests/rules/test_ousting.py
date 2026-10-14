"""Ousting and victory (Rulebook SS5 Ending the Game).

"Pool 0 -> ousted. Prey ousted -> predator gets 1 VP + 6 pool. Last
Methuselah gets +1 VP. With two players left, each is the other's prey."
2P structural consequence (CLAUDE.md SS3, settled core rule): the sole
survivor of a 2-player duel collects both bonuses at once and the game ends.
"""

import pytest

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.errors import GameOverError
from vtesbot.engine.ousting import check_oust
from vtesbot.engine.phases.influence import INFLUENCE_PHASE_ACTION_HOOK, influence_phase
from vtesbot.engine.phases.master import master_phase
from vtesbot.engine.phases.unlock import unlock_phase
from vtesbot.engine.pool import lose_pool


def test_pool_at_zero_ousts_and_ends_the_game():
    game = ScenarioBuilder(seed=1).player("P1", pool=10).player("P2", pool=0).build()

    check_oust(game.state, "P2")

    assert "P2" in game.state.eliminated
    assert game.state.game_over is True
    assert game.state.winner == "P1"
    assert game.state.victory_points["P1"] == 2  # 1 (ousted prey) + 1 (last Methuselah)
    assert game.pool_of("P1") == 16  # 10 + 6


def test_positive_pool_does_not_oust():
    game = ScenarioBuilder(seed=1).player("P1", pool=10).player("P2", pool=1).build()

    check_oust(game.state, "P2")

    assert "P2" not in game.state.eliminated
    assert game.state.game_over is False


def test_checking_an_already_eliminated_player_is_a_no_op():
    game = ScenarioBuilder(seed=1).player("P1", pool=10).player("P2", pool=0).build()
    check_oust(game.state, "P2")
    pool_after_first = game.pool_of("P1")

    check_oust(game.state, "P2")

    assert game.pool_of("P1") == pool_after_first  # no double bonus


def test_minion_phase_decision_still_runs_after_oust_check_is_a_no_op_once_over():
    """Sanity: once game_over is set, no further decisions are solicited from
    either agent for the rest of the (already-ended) turn."""
    game = ScenarioBuilder(seed=1).player("P1", pool=10).player("P2", pool=0).build()
    game.state.agents["P1"] = ScriptedAgent("P1")
    game.state.agents["P2"] = ScriptedAgent("P2")

    check_oust(game.state, "P2")  # would raise if it asked anything

    assert game.state.game_over is True


def test_influence_phase_stops_asking_once_a_hook_option_ousts_the_actor():
    """A hook-offered influence option that ousts the actor (pool cost to 0)
    must end the phase with no further decision (Rulebook SS5 Ending the Game:
    the game continues only until one Methuselah is left; 2P: that is the
    opponent at once)."""

    def fake_option(state, context):
        return [
            hooks.HookOption(
                choice=Choice("pay_last_pool", "Pay the last pool"),
                apply=lambda s: lose_pool(s, "P2", 1) or 1,
            )
        ]

    hooks.register(INFLUENCE_PHASE_ACTION_HOOK, fake_option)
    game = (
        ScenarioBuilder(seed=1)
        .player("P1", pool=10)
        .player("P2", pool=1)
        .uncontrolled_vampire("U1", capacity=3, blood=0)
        .build()
    )
    p2 = ScriptedAgent("P2").expect("influence_action", "pay_last_pool")
    game.state.agents["P2"] = p2

    influence_phase(game.state, "P2")

    p2.assert_exhausted()
    assert game.state.game_over is True
    assert game.pool_of("P2") == 0


def _offered_on_first_influence_decision(pool: int, *, crypt: bool = False) -> list[str]:
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    p2 = builder.player("P2", pool=pool).uncontrolled_vampire("U1", capacity=3, blood=0)
    if crypt:
        p2.crypt_deck_cards(count=1, name_prefix="fresh")
    builder.player("P1", pool=10)
    game = builder.build()
    offered: list[str] = []

    class Recording(ScriptedAgent):
        def decide(self, observation, decision):
            offered.extend(c.value for c in decision.choices)
            return decision.choices[-1]

    game.state.agents["P2"] = Recording("P2")
    influence_phase(game.state, "P2")
    return offered


def test_transfer_that_would_zero_own_pool_is_not_offered_at_pool_1():
    """OQ-41 (user ruling): 2P format blocks a self-ousting transfer."""
    offered = _offered_on_first_influence_decision(1, crypt=True)
    assert "add_blood:U1" not in offered
    assert "bring_crypt" not in offered


def test_transfer_leaving_pool_1_is_offered_at_pool_2():
    offered = _offered_on_first_influence_decision(2, crypt=True)
    assert "add_blood:U1" in offered
    assert "bring_crypt" in offered


def test_pool_1_still_offers_pool_free_influence_actions():
    """OQ-41: only pool-paying transfers are blocked; remove_blood (gains pool)
    and reveal (free) stay."""
    builder = ScenarioBuilder(seed=1, first_influence_phase_used=True)
    p2 = builder.player("P2", pool=1)
    p2.uncontrolled_vampire("U1", capacity=3, blood=1)
    p2.uncontrolled_vampire("U2", capacity=3, blood=3)
    builder.player("P1", pool=10)
    game = builder.build()
    offered: list[str] = []

    class Recording(ScriptedAgent):
        def decide(self, observation, decision):
            offered.extend(c.value for c in decision.choices)
            return decision.choices[-1]

    game.state.agents["P2"] = Recording("P2")
    influence_phase(game.state, "P2")

    assert "remove_blood:U1" in offered
    assert "reveal:U2" in offered
    assert "add_blood:U1" not in offered


def test_first_influence_phase_three_transfers_at_pool_1_blocks_self_oust():
    builder = ScenarioBuilder(seed=1)  # first influence phase: 3 transfers
    builder.player("P2", pool=1).uncontrolled_vampire("U1", capacity=3, blood=0)
    builder.player("P1", pool=10)
    game = builder.build()
    offered: list[str] = []

    class Recording(ScriptedAgent):
        def decide(self, observation, decision):
            offered.extend(c.value for c in decision.choices)
            return decision.choices[-1]

    game.state.agents["P2"] = Recording("P2")
    influence_phase(game.state, "P2")

    assert "add_blood:U1" not in offered
    assert game.state.game_over is False


def test_ask_after_game_over_raises_game_over_error():
    game = ScenarioBuilder(seed=1).player("P1", pool=10).player("P2", pool=0).build()
    check_oust(game.state, "P2")
    decision = Decision(player="P1", kind="x", choices=(Choice("a", "A"),))

    with pytest.raises(GameOverError):
        game.state.ask(decision)


def test_master_phase_stops_after_a_trifle_ousts_the_actor():
    """A trifle's bonus action must not be offered once its own cost ousted the player."""

    def fake_trifle(state, context):
        if context.get("player") != "P1":
            return []
        return [
            hooks.HookOption(
                choice=Choice("play_trifle", "Play trifle"),
                apply=lambda s: lose_pool(s, "P1", 1) or True,
            )
        ]

    hooks.register("master_phase_play", fake_trifle)
    game = ScenarioBuilder(seed=1).player("P1", pool=1).player("P2", pool=10).build()
    p1 = ScriptedAgent("P1").expect("master_phase_action", "play_trifle")
    game.state.agents["P1"] = p1

    master_phase(game.state, "P1")

    p1.assert_exhausted()
    assert game.state.game_over is True
    assert game.state.winner == "P2"


def test_unlock_phase_does_not_offer_a_contest_payment_that_would_oust_the_payer():
    """OQ-42 (user ruling, central rule): the pay option is dropped at pool 1;
    the remaining lone `yield` is auto-resolved (no vacuous Decision)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=1).ready_vampire("P1-V1", blood=1)
    builder.player("P2", pool=10).ready_vampire("P2-V1", blood=1)
    game = builder.build()
    game.vampire("P1-V1").contested_with = "P2-V1"
    game.vampire("P2-V1").contested_with = "P1-V1"
    game.state.agents["P1"] = ScriptedAgent("P1")

    unlock_phase(game.state, "P1")

    assert game.vampire("P1-V1").zone == "burned"
    assert not [e for e in game.state.log.entries if e.kind == "decision"]
    assert game.state.game_over is False
    assert game.pool_of("P1") == 1
