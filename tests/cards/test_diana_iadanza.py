"""Diana Iadanza (krcg id 201694, `src/vtesbot/cards/diana_iadanza.py`).

Card text: "Camarilla Toreador Justicar: During a referendum she calls,
Diana can burn 1 blood to cancel a reaction card as it is played (cost is
still paid). +1 bleed."

Clause 1 (cancel-as-played) is not built -- blocked on `docs/
OPEN_QUESTIONS.md` OQ-33 (no structured "is this a Reaction card" marker on
`apply_chosen_option`'s cancel context). Only clause 2 ("+1 bleed") has real
code; these are scenario tests against the real `BLEED_AMOUNT_FIXED_
MODIFIER_HOOK` machinery (`engine/phases/minion.py::_perform_bleed`), not a
fake provider.

One assertion per clause: registry status/reason, the +1 bonus for Diana
herself bleeding, no bonus for a different vampire's bleed (even a
different vampire controlled by the same Methuselah), and no bonus for the
opposing Methuselah's own bleed.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.cards import registry
from vtesbot.cards.diana_iadanza import KRCG_ID
from vtesbot.engine import CryptCard
from vtesbot.engine.phases.minion import minion_phase


def _make_diana(builder_player, instance_id: str) -> None:
    """Swap the just-built vampire's `card` for Diana's real printed
    identity (`CryptCard` is frozen, mirrors `test_carmelita_neillson.py::
    _make_carmelita`'s own swap-in pattern)."""
    vampire = next(v for v in builder_player.vampires if v.instance_id == instance_id)
    vampire.card = CryptCard(
        krcg_id=KRCG_ID,
        name="Diana Iadanza",
        capacity=9,
        group=7,
        clan="Toreador",
        title="Justicar",
        disciplines=("aus", "cel", "for", "pre"),
    )


def test_registered_as_blocked_on_oq_33_for_clause_1():
    reg = registry.get(KRCG_ID)
    assert reg is not None
    assert reg.status is registry.Status.BLOCKED
    assert reg.blocked_reason == "OQ-33"
    assert reg.name == "Diana Iadanza"


def test_plus_1_bleed_when_diana_herself_bleeds():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Diana1", capacity=9, blood=1)
    _make_diana(p1, "Diana1")
    builder.player("P2", pool=30).ready_vampire("D", capacity=3, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:Diana1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 28  # base bleed 1 + Diana's own +1
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_no_bonus_when_a_different_vampire_bleeds_for_the_same_controller():
    builder = ScenarioBuilder(seed=1)
    p1 = builder.player("P1", pool=30)
    p1.ready_vampire("Diana1", capacity=9, blood=1, locked=True)  # already acted this turn
    _make_diana(p1, "Diana1")
    p1.ready_vampire("Other1", capacity=3, blood=1)
    builder.player("P2", pool=30).ready_vampire("D", capacity=3, blood=0)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:Other1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    assert game.pool_of("P2") == 29  # base bleed 1 only, Diana did not act
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_no_bonus_for_the_opposing_methuselahs_own_bleed():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("Other1", capacity=3, blood=1)
    p2 = builder.player("P2", pool=30)
    p2.ready_vampire("Diana1", capacity=9, blood=1)  # not acting; just defending/blocking
    _make_diana(p2, "Diana1")
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("minion_phase_choice", "act_with:Other1")
    actor.expect("action_choice", "bleed")
    game.state.agents["P1"] = actor
    defender = ScriptedAgent("P2")
    defender.expect("block_attempt", "decline")
    game.state.agents["P2"] = defender

    minion_phase(game.state, "P1")

    # Diana belongs to the defending Methuselah here, not the bleeder: her
    # own "+1 bleed" is scoped to a bleed she herself performs, never one
    # performed against her.
    assert game.pool_of("P2") == 29
    actor.assert_exhausted()
    defender.assert_exhausted()
