"""Sergio Bueno (krcg id 201662, `src/vtesbot/cards/sergio_bueno.py`).

Card text: "Anarch Baron of Santo Domingo: Minions with 1 or more of your
corruption counters must burn 1 blood or life to attempt to block Sergio."
Ruling: "The passive ability applies even if the vampire is in torpor."
[LSJ 20011022].

Implemented against `engine/action.py::BLOCK_ATTEMPT_COST_HOOK`/
`BlockAttemptCost` (`tests/rules/test_block_attempt_cost.py` covers the
generic primitive itself; this file covers Sergio Bueno's own gating logic:
"your corruption counters" scoped to Sergio's own controller, "1 blood"
deducted on selection, and the title clause's generic `TITLE_VOTES` wiring,
unchanged from before this pass -- same pattern as `tests/cards/
test_leumeah.py`).
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.sergio_bueno import KRCG_ID
from vtesbot.engine import CryptCard
from vtesbot.engine.action import attempt_block
from vtesbot.engine.politics import political_action

NAME = "Sergio Bueno"


def _make_sergio_bueno(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Sergio Bueno's real printed
    identity (`CryptCard` is frozen)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name=NAME,
        capacity=8,
        group=6,
        clan="Ministry",
        title="Baron",
        disciplines=("aus", "pot", "OBF", "PRE", "PRO"),
    )


def test_registered_as_implemented_with_block_attempt_cost_hook():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.IMPLEMENTED
    assert reg.name == NAME
    assert reg.hooks == (registry.Hook.BLOCK_ATTEMPT_COST,)


def test_a_ready_sergio_bueno_contributes_2_votes_as_a_baron_title_source():
    """Rulebook §4 Politics > Gaining Votes: "2 votes for each ready prince
    or baron" -- `engine/politics.py::TITLE_VOTES["Baron"] == 2`. Proven
    here, end to end through the real `political_action`, to confirm this
    specific printed vampire's `title="Baron"` is wired to the generic
    title-vote source regardless of this card's own block-attempt-cost
    ability."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Sergio1", capacity=8, blood=1)
    _make_sergio_bueno(p1, "Sergio1")
    builder.player("P2", pool=30)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("polling_step_cast", "for:political_action_card:P1")
    actor.expect("polling_step_cast", "for:title:Sergio1")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = ScriptedAgent("P2")

    result = political_action(game.state, "P1", game.vampire("Sergio1"))

    assert result is True  # 1 (political action card) + 2 (Baron title) for vs 0 against
    actor.assert_exhausted()


def test_candidate_with_sergios_controllers_corruption_counter_must_burn_1_blood_to_attempt():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Sergio1", capacity=8, blood=1)
    _make_sergio_bueno(p1, "Sergio1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=2)
    game = builder.build()
    game.vampire("B1").corruption_counters["P1"] = 1
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("Sergio1")
    )

    assert blocker is not None
    assert blocker.instance_id == "B1"
    assert game.vampire("B1").blood == 1  # paid 1 blood to attempt
    defender.assert_exhausted()


def test_candidate_with_no_blood_cannot_attempt_to_block_sergio_at_all():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Sergio1", capacity=8, blood=1)
    _make_sergio_bueno(p1, "Sergio1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    game.vampire("B1").corruption_counters["P1"] = 1
    game.state.agents["P2"] = ScriptedAgent("P2")  # cannot afford: no decision at all

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("Sergio1")
    )

    assert blocker is None


def test_corruption_counters_placed_by_someone_other_than_sergios_controller_do_not_gate():
    """ "Your corruption counters" -- scoped to Sergio's own controller
    (`actor`); a counter placed by a different Methuselah (here, the
    candidate's own controller, P2) does not trigger the cost at all, so a
    candidate with 0 blood is still offered and still blocks for free."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Sergio1", capacity=8, blood=1)
    _make_sergio_bueno(p1, "Sergio1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=0)
    game = builder.build()
    game.vampire("B1").corruption_counters["P2"] = 1  # not Sergio's controller
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("Sergio1")
    )

    assert blocker is not None
    assert blocker.instance_id == "B1"
    assert game.vampire("B1").blood == 0  # no cost: never gated by this ability
    defender.assert_exhausted()


def test_passive_ability_applies_even_if_sergio_is_in_torpor():
    """[LSJ 20011022]: direct unit coverage, since the real action economy
    (`engine/phases/minion.py::minion_phase`) never lets a torpid vampire
    become `acting_vampire` in the first place -- this module's own gating
    function performs no `zone` check at all, so the ability still applies
    when `attempt_block` is (synthetically) called with a torpid Sergio as
    `acting_vampire`, proving no accidental zone-based bypass exists."""
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Sergio1", capacity=8, blood=1)
    _make_sergio_bueno(p1, "Sergio1")
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=1)
    game = builder.build()
    game.vampire("Sergio1").zone = "torpor"
    game.vampire("B1").corruption_counters["P1"] = 1
    defender = ScriptedAgent("P2").expect("block_attempt", "block_with:B1")
    game.state.agents["P2"] = defender

    blocker = attempt_block(
        game.state, "P1", "P2", base_stealth=0, acting_vampire=game.vampire("Sergio1")
    )

    assert blocker is not None
    assert game.vampire("B1").blood == 0  # the cost still applied
    defender.assert_exhausted()
