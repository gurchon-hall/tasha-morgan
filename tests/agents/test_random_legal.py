"""`RandomLegalAgent` (CLAUDE.md milestone 4 baseline).

Picks uniformly among `decision.choices`; always returns one of them (by
construction -- `self._random.choice(decision.choices)` cannot return
anything else, but worth asserting since `GameState.ask` relies on it to
never raise `IllegalChoiceError`), and is deterministic for a given seed
(the reproducibility `sim/runner.py::run_match` depends on).
"""

from vtesbot.agents import RandomLegalAgent
from vtesbot.engine.decision import Choice, Decision

_CHOICES = (Choice("a", "A"), Choice("b", "B"), Choice("c", "C"))
_DECISION = Decision(player="P1", kind="test_decision", choices=_CHOICES)


def test_decision_is_always_one_of_the_offered_choices():
    agent = RandomLegalAgent("P1", seed=0)
    for _ in range(50):
        choice = agent.decide(observation=None, decision=_DECISION)
        assert choice in _CHOICES


def test_same_seed_is_deterministic():
    agent_a = RandomLegalAgent("P1", seed=42)
    agent_b = RandomLegalAgent("P1", seed=42)
    sequence_a = [agent_a.decide(None, _DECISION).value for _ in range(20)]
    sequence_b = [agent_b.decide(None, _DECISION).value for _ in range(20)]
    assert sequence_a == sequence_b


def test_different_seeds_can_differ():
    agent_a = RandomLegalAgent("P1", seed=1)
    agent_b = RandomLegalAgent("P1", seed=2)
    sequence_a = [agent_a.decide(None, _DECISION).value for _ in range(20)]
    sequence_b = [agent_b.decide(None, _DECISION).value for _ in range(20)]
    assert sequence_a != sequence_b


def test_single_choice_decision_always_returns_it():
    agent = RandomLegalAgent("P1", seed=7)
    single = Decision(player="P1", kind="test_decision", choices=(Choice("only", "Only"),))
    for _ in range(5):
        assert agent.decide(None, single).value == "only"
