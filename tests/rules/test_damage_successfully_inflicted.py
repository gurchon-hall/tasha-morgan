"""Round-scoped "damage successfully inflicted" tracking (`engine/damage.py
::DAMAGE_SUCCESSFULLY_INFLICTED_KEY`/`record_damage_successfully_inflicted`/
`damage_successfully_inflicted_this_round`), keyed by the *inflicting*
vampire's own instance id -- distinct from, and in addition to, the
existing `BLOOD_LOST_TO_DAMAGE_KEY` (ENG-020), which is keyed by the
*damaged* vampire and only totals blood actually spent to mend/burn.
Sourced from "Counts up damage successfully inflicted during the round ...
retainers and environmental damage do not count." [TOM 19950304]
[LSJ 20010812].

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, standing in for Pulled Fangs' (krcg 101515) own playability
trigger ("usable at close range at the end of a round during which this
minion successfully inflicted more damage than the opposing vampire") --
that card's own wiring remains `card-implementer`'s job once this
capability exists; it stays registered `blocked` until then.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.combat import END_OF_ROUND_HOOK, ROUND_STATE_CONTEXT_KEY, run_combat
from vtesbot.engine.damage import (
    DAMAGE_PREVENTION_HOOK,
    apply_damage,
    damage_successfully_inflicted_this_round,
    record_damage_successfully_inflicted,
)


def _one_vampire_game(capacity: int = 3, blood: int = 0):
    builder = ScenarioBuilder(seed=1)
    builder.player("A").ready_vampire("V1", capacity=capacity, blood=blood)
    builder.player("B")
    return builder.build()


def test_query_with_no_round_state_degrades_to_zero():
    assert damage_successfully_inflicted_this_round(None, "V1") == 0


def test_query_with_no_entry_for_vampire_degrades_to_zero():
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "someone_else", 3)
    assert damage_successfully_inflicted_this_round(round_state, "V1") == 0


def test_record_is_a_no_op_with_no_round_state():
    # Must not raise -- mirrors `record_blood_lost_to_damage`'s own contract.
    record_damage_successfully_inflicted(None, "V1", 3)


def test_record_is_a_no_op_with_no_inflicted_by():
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, None, 3)
    assert round_state == {}


def test_record_is_a_no_op_for_non_positive_amount():
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "V1", 0)
    record_damage_successfully_inflicted(round_state, "V1", -1)
    assert round_state == {}


def test_record_accumulates_across_multiple_calls_same_round():
    round_state: dict = {}
    record_damage_successfully_inflicted(round_state, "V1", 2)
    record_damage_successfully_inflicted(round_state, "V1", 1)
    assert damage_successfully_inflicted_this_round(round_state, "V1") == 3


def test_apply_damage_records_the_post_prevention_pre_mend_total():
    """Distinct from `BLOOD_LOST_TO_DAMAGE_KEY`: a vampire with only 1
    blood taking 3 normal damage mends just 1 point (losing 1 blood), but
    the *inflicting* vampire's own "successfully inflicted" total is still
    the full 3 -- the whole reason this is a separate ledger."""
    game = _one_vampire_game(capacity=3, blood=1)
    game.state.agents["A"] = ScriptedAgent("A").expect("mend_damage", "1")
    round_state: dict = {}

    apply_damage(
        game.state,
        "A",
        game.vampire("V1"),
        normal=3,
        round_state=round_state,
        inflicted_by="attacker-id",
    )

    assert damage_successfully_inflicted_this_round(round_state, "attacker-id") == 3
    assert game.vampire("V1").blood == 0  # only 1 blood spent mending


def test_apply_damage_with_no_inflicted_by_records_nothing():
    """Damage with no attributable attacker (e.g. a retainer/environmental
    source, per the on-file ruling) is simply never credited to anyone."""
    game = _one_vampire_game(capacity=3, blood=0)
    game.state.agents["A"] = ScriptedAgent("A")  # blood=0: no mend decision
    round_state: dict = {}

    apply_damage(game.state, "A", game.vampire("V1"), normal=1, round_state=round_state)

    assert round_state == {}


def test_apply_damage_records_zero_when_fully_prevented():
    """Damage fully prevented before the mend step never counts as
    "successfully inflicted" at all."""

    def prevent_all(state, context):
        del state

        def apply(s):
            del s
            damage = context["damage"]
            damage["normal"] = 0

        return [hooks.HookOption(choice=hooks.Choice("prevent", "Prevent all"), apply=apply)]

    hooks.register(DAMAGE_PREVENTION_HOOK, prevent_all)
    game = _one_vampire_game(capacity=3, blood=0)
    agent = ScriptedAgent("A")
    agent.expect(DAMAGE_PREVENTION_HOOK, "prevent")
    agent.expect(DAMAGE_PREVENTION_HOOK, "pass")
    game.state.agents["A"] = agent
    round_state: dict = {}

    apply_damage(
        game.state,
        "A",
        game.vampire("V1"),
        normal=2,
        round_state=round_state,
        inflicted_by="attacker-id",
    )

    assert damage_successfully_inflicted_this_round(round_state, "attacker-id") == 0
    agent.assert_exhausted()


def test_run_combat_credits_each_combatant_with_their_own_inflicted_damage():
    """End-to-end through `run_combat`/`_resolve_strike_pair`: each side's
    own strike damage is credited to *that side's own vampire*, not the
    victim, for the actual production call sites in `engine/combat.py`."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=2)
    builder.player("P2", pool=30).ready_vampire("B1", capacity=3, blood=2)
    game = builder.build()
    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")  # B1 does not strike back
    defender.expect("mend_damage", "1")  # B1 mends the 1 damage V1 inflicted
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    captured: list[dict] = []

    def capture_round_state(state, context):
        del state
        captured.append(dict(context[ROUND_STATE_CONTEXT_KEY]))
        return []

    hooks.register(END_OF_ROUND_HOOK, capture_round_state)

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    v1_id = game.vampire("V1").instance_id
    b1_id = game.vampire("B1").instance_id
    round_state = captured[0]
    assert damage_successfully_inflicted_this_round(round_state, v1_id) == 1
    assert damage_successfully_inflicted_this_round(round_state, b1_id) == 0
    actor.assert_exhausted()
    defender.assert_exhausted()
