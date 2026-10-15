"""End of Round (`engine/combat.py`, Rulebook §4 Combat > Combat Sequence,
step 7, "End of Round: End of round cards and effects are played here") and
the round-scoped "blood lost to damage" tracking (`engine/damage.py`) it was
built alongside -- both resolve `docs/OPEN_QUESTIONS.md` OQ-29 (Taste of
Vitae, krcg id 101945). No combat card registers against either mechanism
yet (OQ-29 is still open, left for a future `card-implementer` pass) -- these
are scenario tests for the generic mechanisms only, using fake providers and
direct calls to prove the shape rather than any one card's wording.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine import hooks
from vtesbot.engine.combat import END_OF_ROUND_HOOK, ROUND_STATE_CONTEXT_KEY, run_combat
from vtesbot.engine.damage import (
    apply_damage,
    blood_lost_to_damage_this_round,
    record_blood_lost_to_damage,
)
from vtesbot.engine.decision import Choice


def _combat_game(*, acting_blood: int = 2, blocking_blood: int = 0, blocking_wounded: bool = False):
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, blood=acting_blood)
    builder.player("P2", pool=30).ready_vampire(
        "B1", capacity=3, blood=blocking_blood, wounded=blocking_wounded
    )
    return builder.build()


def _register_logging_provider(calls: list[str]) -> None:
    """A fake `END_OF_ROUND_HOOK` provider that never actually offers a real
    option (so no `Decision` is ever raised, CLAUDE.md "only when needed")
    but records every `context["player"]` it is queried for -- `hooks.
    resolve_impulse_window`'s own loop calls `offer()` once per turn, so the
    recorded sequence is exactly the offer order `_ask_end_of_round` produces
    each time it runs."""

    def provider(state, context):
        calls.append(context["player"])
        return []

    hooks.register(END_OF_ROUND_HOOK, provider)


# --- Fires on every exit path (mirrors test_combat.py's own three scenarios) ---


def test_end_of_round_fires_once_on_a_normal_end():
    """Normal end: neither side presses -- mirrors `test_combat.py::
    test_combat_round_with_mend_and_declined_press`."""
    calls: list[str] = []
    _register_logging_provider(calls)
    game = _combat_game(acting_blood=2, blocking_blood=0)

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("mend_damage", "1")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "hand_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert calls == ["P1", "P2"]  # exactly one round's worth of offers
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_end_of_round_fires_once_on_a_premature_end_with_no_press_decision():
    """Premature end: B1 (already wounded, 0 blood) is sent to torpor by the
    initial strike pair, before the Press step is ever reached -- mirrors
    `test_combat.py::test_combat_ends_immediately_when_a_combatant_enters_
    torpor`. Taste of Vitae's own ruling ("can be played if the round ends
    prematurely" [RTR 20001020] [LSJ 20001024] [RTR 20030519]) requires this
    window still fires even though no `press` decision was ever raised for
    either side."""
    calls: list[str] = []
    _register_logging_provider(calls)
    game = _combat_game(acting_blood=2, blocking_blood=0, blocking_wounded=True)

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.zone_of("B1") == "torpor"
    assert calls == ["P1", "P2"]  # fired once, despite no press decision at all
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_end_of_round_fires_each_round_when_someone_presses():
    """Someone presses, so a second round follows -- mirrors `test_combat.py
    ::test_pressing_continues_combat_to_another_round`. End of Round fires
    once for round 1 (after the press that continues combat) and once more
    for round 2 (which ends the combat), i.e. twice total -- "end of round
    happens regardless of whether a new round follows"."""
    calls: list[str] = []
    _register_logging_provider(calls)
    game = _combat_game(acting_blood=2, blocking_blood=0)

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("mend_damage", "1")
    actor.expect("press", "press")  # round 1, actor's turn: press
    actor.expect("press", "end_combat")  # round 1, actor's turn: decline, closes the window
    actor.expect("strike_choice", "hand_strike")  # round 2
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "hand_strike")
    defender.expect("press", "end_combat")  # round 1, blocking's turn: decline
    defender.expect("strike_choice", "no_strike")  # round 2
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.zone_of("B1") == "torpor"  # round 2 ends combat
    assert calls == ["P1", "P2", "P1", "P2"]  # two rounds' worth of offers
    actor.assert_exhausted()
    defender.assert_exhausted()


# --- Controller order: acting combatant's controller first -----------------


def test_end_of_round_offers_the_acting_combatants_controller_first():
    """Both sides have a real, one-shot option available; the acting
    combatant's controller (P1) must be asked -- and decide -- first, per the
    Press-step ordering precedent this mechanism shares (OQ-3, module
    docstring): P1's option is claimed (and exhausted) before P2 is ever
    offered theirs. Each provider is one-shot (consumes itself once used),
    so only one `end_of_round` decision is ever raised per side -- proving
    the ordering without relying on the generic impulse-window
    "returns-to-acting"/"closes on two passes" machinery, which `tests/
    rules/test_hooks.py` already covers on its own."""
    acting_used = {"value": False}
    blocking_used = {"value": False}

    def acting_provider(state, context):
        if context["player"] != "P1" or acting_used["value"]:
            return []

        def use(s):
            acting_used["value"] = True

        return [hooks.HookOption(choice=Choice("acting_option", "P1's option"), apply=use)]

    def blocking_provider(state, context):
        if context["player"] != "P2" or blocking_used["value"]:
            return []

        def use(s):
            blocking_used["value"] = True

        return [hooks.HookOption(choice=Choice("blocking_option", "P2's option"), apply=use)]

    hooks.register(END_OF_ROUND_HOOK, acting_provider)
    hooks.register(END_OF_ROUND_HOOK, blocking_provider)
    game = _combat_game(acting_blood=2, blocking_blood=0)

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("mend_damage", "1")
    actor.expect("press", "end_combat")
    actor.expect("end_of_round", "acting_option")  # P1 offered -- and decides -- first
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "hand_strike")
    defender.expect("press", "end_combat")
    defender.expect("end_of_round", "blocking_option")  # only then offered to P2
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert acting_used["value"] is True
    assert blocking_used["value"] is True
    actor.assert_exhausted()
    defender.assert_exhausted()


def test_no_end_of_round_decision_without_a_registered_provider():
    """Regression guard: with no `END_OF_ROUND_HOOK` provider registered, no
    `end_of_round` decision is ever raised (CLAUDE.md "only when needed") --
    byte-for-byte the pre-OQ-29 result."""
    game = _combat_game(acting_blood=2, blocking_blood=0)

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("mend_damage", "1")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "hand_strike")
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    actor.assert_exhausted()
    defender.assert_exhausted()


# --- Round-scoped "blood lost to damage" tracking (engine/damage.py) -------


def _one_vampire_game(capacity: int = 3, blood: int = 0, wounded: bool = False):
    builder = ScenarioBuilder(seed=1)
    builder.player("A").ready_vampire("V1", capacity=capacity, blood=blood, wounded=wounded)
    builder.player("B")
    return builder.build()


def test_blood_lost_to_damage_records_mend_only():
    """Mended normal damage costs exactly 1 blood per point actually
    mended -- unmended normal damage left as `wounded` costs nothing."""
    game = _one_vampire_game(capacity=5, blood=3)
    game.state.agents["A"] = ScriptedAgent("A").expect("mend_damage", "1")
    round_state: dict = {}
    vampire = game.vampire("V1")

    apply_damage(game.state, "A", vampire, normal=2, round_state=round_state)

    assert vampire.blood == 2  # mended 1 of the 2 points; 1 point left unmended (wounded)
    assert vampire.wounded is True
    assert blood_lost_to_damage_this_round(round_state, vampire.instance_id) == 1


def test_blood_lost_to_damage_records_aggravated_burn_only():
    """Reproduces the Tamoszius worked example (`test_damage.py::
    test_multiple_aggravated_points_wound_torpor_then_burn_blood`): the first
    aggravated point wounds-and-torpors for free; the remaining two points
    each burn 1 blood while blood remains."""
    game = _one_vampire_game(capacity=3, blood=2)
    game.state.agents["A"] = ScriptedAgent("A")  # aggravated is never mendable
    round_state: dict = {}
    vampire = game.vampire("V1")

    apply_damage(game.state, "A", vampire, aggravated=3, round_state=round_state)

    assert vampire.blood == 0
    assert game.zone_of("V1") == "torpor"
    assert blood_lost_to_damage_this_round(round_state, vampire.instance_id) == 2


def test_blood_lost_to_damage_records_mixed_mend_and_aggravated_burn():
    """One `apply_damage` call resolving both normal (partially mended) and
    aggravated damage: normal is handled first (Rulebook §4: "Normal damage
    is handled before aggravated"), so the vampire is already wounded by the
    time the aggravated point(s) apply."""
    game = _one_vampire_game(capacity=5, blood=3)
    # Mend only 1 of the 2 normal points, not both: fully mending would leave
    # the vampire undamaged instead of wounded.
    game.state.agents["A"] = ScriptedAgent("A").expect("mend_damage", "1")
    round_state: dict = {}
    vampire = game.vampire("V1")

    apply_damage(game.state, "A", vampire, normal=2, aggravated=1, round_state=round_state)

    # Mend step: mends 1 of 2 normal points (1 blood spent), leaving 1
    # unmended normal point -> wounded. The aggravated point then hits an
    # already-wounded vampire: burns 1 more blood (blood remains: 3-1=2>0).
    assert vampire.wounded is True
    assert vampire.blood == 1  # 3 - 1 (mend) - 1 (aggravated burn)
    assert blood_lost_to_damage_this_round(round_state, vampire.instance_id) == 2


def test_blood_lost_to_damage_resets_fresh_each_round():
    """A fresh `round_state` dict (as `run_combat` creates at the top of
    every round) starts the accumulator back at 0, independent of any
    earlier round's own total."""
    game = _one_vampire_game(capacity=5, blood=3)
    game.state.agents["A"] = ScriptedAgent("A").expect("mend_damage", "0")
    vampire = game.vampire("V1")
    round_1_state: dict = {}

    apply_damage(game.state, "A", vampire, normal=1, round_state=round_1_state)
    assert blood_lost_to_damage_this_round(round_1_state, vampire.instance_id) == 0

    round_2_state: dict = {}
    game.state.agents["A"] = ScriptedAgent("A").expect("mend_damage", "1")
    vampire.wounded = False  # simulate a fresh round's own healthy state for this check

    apply_damage(game.state, "A", vampire, normal=1, round_state=round_2_state)

    assert blood_lost_to_damage_this_round(round_1_state, vampire.instance_id) == 0
    assert blood_lost_to_damage_this_round(round_2_state, vampire.instance_id) == 1


def test_blood_lost_to_damage_unaffected_by_unrelated_blood_changes():
    """A blood-moving effect unrelated to `apply_damage`'s own mend/
    aggravated-burn branches (e.g. a card directly setting `vampire.blood`,
    or `record_blood_lost_to_damage` never being called for it) must never
    contribute to this total."""
    game = _one_vampire_game(capacity=5, blood=3)
    game.state.agents["A"] = ScriptedAgent("A").expect("mend_damage", "1")
    round_state: dict = {}
    vampire = game.vampire("V1")

    apply_damage(game.state, "A", vampire, normal=2, round_state=round_state)
    assert blood_lost_to_damage_this_round(round_state, vampire.instance_id) == 1

    # Unrelated blood loss the same round/turn (e.g. a different card's own
    # effect), applied directly rather than via apply_damage:
    vampire.blood -= 1

    assert vampire.blood == 1
    assert blood_lost_to_damage_this_round(round_state, vampire.instance_id) == 1  # unchanged


def test_blood_lost_to_damage_remains_readable_after_the_vampire_is_burned():
    """OQ-29: "Can be played if the opponent was burned" [LSJ 20031201-2] --
    the record must survive the tracked vampire's own zone transition to
    `"burned"`, which only flips `zone`/`locked` and never touches this
    separate dict."""
    game = _one_vampire_game(capacity=3, blood=0, wounded=True)
    game.state.agents["A"] = ScriptedAgent("A")  # aggravated: never mendable
    round_state: dict = {}
    vampire = game.vampire("V1")

    apply_damage(game.state, "A", vampire, aggravated=1, round_state=round_state)

    assert game.zone_of("V1") == "burned"  # already wounded, 0 blood: burns outright
    assert blood_lost_to_damage_this_round(round_state, vampire.instance_id) == 0

    # Give it something to have recorded first, then burn it, to prove the
    # *non-zero* case also survives (not just the "burned with nothing
    # recorded" edge case above):
    round_state_2: dict = {}
    record_blood_lost_to_damage(round_state_2, vampire.instance_id, 2)
    vampire.zone = "burned"

    assert blood_lost_to_damage_this_round(round_state_2, vampire.instance_id) == 2


def test_blood_lost_to_damage_degrades_gracefully_without_a_round_state():
    """`round_state=None` (every call site outside a combat round, e.g. a
    direct card effect or a scenario test not exercising this mechanism) is
    a no-op for tracking, and `blood_lost_to_damage_this_round(None, ...)`
    degrades to 0 -- matching the project's usual degrade-gracefully
    convention for round-scoped helpers."""
    game = _one_vampire_game(capacity=5, blood=3)
    game.state.agents["A"] = ScriptedAgent("A").expect("mend_damage", "1")
    vampire = game.vampire("V1")

    apply_damage(game.state, "A", vampire, normal=2)  # no round_state given

    assert vampire.blood == 2
    assert blood_lost_to_damage_this_round(None, vampire.instance_id) == 0


def test_blood_lost_to_damage_resets_fresh_every_round_of_real_combat():
    """Authentic reproduction via `run_combat` (not just a unit-level dict
    check): V1 mends 1 point in round 1 (recorded); round 2 (B1 presses never
    happen here -- V1's own hand strike instead sends the already-wounded,
    0-blood B1 to torpor, ending combat) -- B1 never strikes back in round 2,
    so V1 takes no damage and mends nothing. If `round_state` were wrongly
    carried over between rounds instead of recreated fresh, round 2's own
    reading would still show round 1's total (1); the correctly-reset
    reading is 0."""
    captured: list[int] = []

    def reader(state, context):
        if context["player"] != "P1":
            return []
        round_state = context.get(ROUND_STATE_CONTEXT_KEY)
        captured.append(blood_lost_to_damage_this_round(round_state, context["acting_vampire"]))
        return []

    hooks.register(END_OF_ROUND_HOOK, reader)
    game = _combat_game(acting_blood=2, blocking_blood=0)

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("mend_damage", "1")  # round 1: V1 mends 1 of the 1 point taken
    actor.expect("press", "press")  # round 1, actor's turn: press
    actor.expect("press", "end_combat")  # round 1, actor's turn: decline, closes the window
    actor.expect("strike_choice", "hand_strike")  # round 2
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "hand_strike")  # round 1
    defender.expect("press", "end_combat")  # round 1, blocking's turn: decline
    defender.expect("strike_choice", "no_strike")  # round 2: B1 already wounded -> torpor ends it
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert game.zone_of("B1") == "torpor"
    assert captured == [1, 0]  # round 1's mend recorded; round 2 starts back at 0
    actor.assert_exhausted()
    defender.assert_exhausted()


# --- End-to-end: the accumulator is actually reachable from a real combat --


def test_end_of_round_provider_can_read_this_rounds_blood_loss_record():
    """Proves the full wiring: `run_combat` threads the same `round_state`
    dict through both `_resolve_strike_pair` (which `apply_damage` records
    into) and `_ask_end_of_round` (whose hook context carries it under
    `ROUND_STATE_CONTEXT_KEY`) -- a future `END_OF_ROUND_HOOK` provider (e.g.
    Taste of Vitae) can read one combatant's own "blood lost to damage this
    round" total from the other combatant's own strike earlier the same
    round."""
    captured: list[int] = []

    def reader(state, context):
        if context["player"] != "P1":
            return []
        round_state = context.get(ROUND_STATE_CONTEXT_KEY)
        captured.append(blood_lost_to_damage_this_round(round_state, context["blocking_vampire"]))
        return []

    hooks.register(END_OF_ROUND_HOOK, reader)
    game = _combat_game(acting_blood=2, blocking_blood=3)

    actor = ScriptedAgent("P1")
    actor.expect("strike_choice", "hand_strike")
    actor.expect("press", "end_combat")
    defender = ScriptedAgent("P2")
    defender.expect("strike_choice", "no_strike")
    defender.expect("mend_damage", "1")  # B1 mends the 1 point taken from V1's hand strike
    defender.expect("press", "end_combat")
    game.state.agents["P1"] = actor
    game.state.agents["P2"] = defender

    run_combat(game.state, "P1", game.vampire("V1"), "P2", game.vampire("B1"))

    assert captured == [1]  # B1 lost exactly 1 blood to damage (the mend) this round
    actor.assert_exhausted()
    defender.assert_exhausted()
