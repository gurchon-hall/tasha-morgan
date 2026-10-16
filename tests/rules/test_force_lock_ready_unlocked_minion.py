"""`engine/action.py::force_lock_ready_unlocked_minion`: forces a Methuselah
to lock one of their own ready unlocked vampires, their own choice among
ties -- never the caller's. Sourced from Brujah Debate's (krcg 100260)
ruling on the identical "[that Methuselah] locks a [vampire] they control"
construction: "If more than one Brujah shares the highest capacity amount,
the controller chooses which of them to lock during her master phase."
[LSJ 19980224].

Per the `rules-scenario-test` skill: these are scenario tests for the
*mechanism*, using a direct call (no real card wires to it yet) standing in
for Propaganda's own superior clause (krcg 101495, "the target Methuselah
locks a ready unlocked minion they control") -- that card's own wiring
remains `card-implementer`'s job once this capability exists; it stays
registered `blocked` until then.
"""

from helpers import ScenarioBuilder, ScriptedAgent
from vtesbot.engine.action import force_lock_ready_unlocked_minion


def test_locks_the_only_eligible_vampire_without_asking_when_forced():
    """A single eligible candidate is auto-picked via `ask_unless_forced`
    (`engine/log.py`'s own `"forced"` entry, not a `"decision"`) -- no
    agent call at all."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    game.state.agents["P1"] = ScriptedAgent("P1")  # no scripted answer needed: forced

    locked = force_lock_ready_unlocked_minion(game.state, "P1")

    assert locked is not None
    assert locked.instance_id == "V1"
    assert game.vampire("V1").locked is True


def test_affected_methuselah_chooses_among_multiple_eligible_candidates():
    """With more than one eligible vampire, the *affected* Methuselah
    (not the caller) makes the choice -- the Brujah Debate ruling's own
    point."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3).ready_vampire("V2", capacity=5)
    builder.player("P2", pool=30)
    game = builder.build()
    agent = ScriptedAgent("P1").expect("forced_lock_own_minion", "lock:V2")
    game.state.agents["P1"] = agent

    locked = force_lock_ready_unlocked_minion(game.state, "P1")

    assert locked is not None
    assert locked.instance_id == "V2"
    assert game.vampire("V1").locked is False
    assert game.vampire("V2").locked is True
    agent.assert_exhausted()


def test_already_locked_vampire_is_not_offered_as_a_candidate():
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, locked=True).ready_vampire(
        "V2", capacity=3
    )
    builder.player("P2", pool=30)
    game = builder.build()
    game.state.agents["P1"] = ScriptedAgent("P1")  # one candidate left: forced, no decision

    locked = force_lock_ready_unlocked_minion(game.state, "P1")

    assert locked is not None
    assert locked.instance_id == "V2"


def test_no_eligible_vampire_fizzles_with_no_decision_raised():
    """ "Cannot do the impossible" convention: a Methuselah with no ready
    unlocked vampire at all simply has nothing to lock."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3, locked=True)
    builder.player("P2", pool=30)
    game = builder.build()
    game.state.agents["P1"] = ScriptedAgent("P1")  # no scripted answer: no decision at all

    locked = force_lock_ready_unlocked_minion(game.state, "P1")

    assert locked is None
    assert game.vampire("V1").locked is True  # unchanged


def test_reason_is_surfaced_in_decision_context_only():
    """`reason` is purely informational (never consulted by the engine
    itself)."""
    builder = ScenarioBuilder(seed=1)
    builder.player("P1", pool=30).ready_vampire("V1", capacity=3).ready_vampire("V2", capacity=3)
    builder.player("P2", pool=30)
    game = builder.build()
    seen_decisions = []

    class RecordingAgent(ScriptedAgent):
        def decide(self, observation, decision):
            seen_decisions.append(decision)
            return super().decide(observation, decision)

    agent = RecordingAgent("P1").expect("forced_lock_own_minion", "lock:V1")
    game.state.agents["P1"] = agent

    force_lock_ready_unlocked_minion(game.state, "P1", reason="propaganda_superior")

    assert seen_decisions[0].context["reason"] == "propaganda_superior"
    agent.assert_exhausted()
