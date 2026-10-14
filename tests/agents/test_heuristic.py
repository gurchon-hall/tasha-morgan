"""`HeuristicAgent` rules (docs/DECISIONS.md D-8) on hand-built decisions,
plus a seeded-sim guard that it never answers outside `decision.choices`."""

from vtesbot.agents import HeuristicAgent, RandomLegalAgent
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.observation import Observation, VampireView
from vtesbot.sim.benchmark import load_suggested_deck, run_alternating


def _vamp(iid: str, zone: str, blood: int, capacity: int = 5, controller: str = "P1"):
    return VampireView(
        instance_id=iid,
        controller=controller,
        zone=zone,
        locked=False,
        wounded=False,
        blood=blood,
        contested=False,
        name=iid,
        capacity=capacity,
    )


def _obs(vampires=(), pool: int = 20) -> Observation:
    return Observation(
        viewer="P1",
        phase="influence",
        active_player="P1",
        turn_number=1,
        edge_holder=None,
        pool={"P1": pool, "P2": 20},
        hand=(),
        opponent_hand_count=0,
        own_library_count=30,
        opponent_library_count=30,
        own_crypt_deck_count=5,
        opponent_crypt_deck_count=5,
        ash_heap={"P1": (), "P2": ()},
        vampires=tuple(vampires),
        allies=(),
        master_cards=(),
    )


def _decision(kind: str, *values: str, **context) -> Decision:
    return Decision("P1", kind, tuple(Choice(v, v) for v in values), context)


def _pick(obs: Observation, decision: Decision, seed: int = 0) -> str:
    return HeuristicAgent("P1", seed).decide(obs, decision).value


def test_reveal_is_preferred():
    obs = _obs([_vamp("V1", "uncontrolled", 5)])
    d = _decision("influence_action", "add_blood:V2", "reveal:V1", "end_phase")
    assert _pick(obs, d) == "reveal:V1"


def test_add_blood_concentrates_on_vampire_closest_to_capacity():
    obs = _obs(
        [
            _vamp("V1", "uncontrolled", 1),
            _vamp("V2", "uncontrolled", 3),
            _vamp("V3", "uncontrolled", 0),
        ]
    )
    d = _decision("influence_action", "add_blood:V1", "add_blood:V2", "add_blood:V3", "end_phase")
    assert _pick(obs, d) == "add_blood:V2"


def test_never_removes_blood_when_pool_is_healthy():
    obs = _obs([_vamp("V1", "uncontrolled", 2)], pool=10)
    d = _decision("influence_action", "remove_blood:V1", "end_phase")
    assert _pick(obs, d) == "end_phase"


def test_removes_blood_when_pool_critical_and_nothing_better():
    obs = _obs([_vamp("V1", "uncontrolled", 2), _vamp("V2", "uncontrolled", 4)], pool=2)
    d = _decision("influence_action", "remove_blood:V1", "remove_blood:V2", "end_phase")
    assert _pick(obs, d) == "remove_blood:V2"


def test_critical_pool_does_not_add_blood():
    obs = _obs([_vamp("V1", "uncontrolled", 2)], pool=2)
    d = _decision("influence_action", "add_blood:V1", "end_phase")
    assert _pick(obs, d) == "end_phase"


def test_brings_crypt_when_no_uncontrolled_vampire():
    obs = _obs([_vamp("V1", "ready", 3)])
    d = _decision("influence_action", "bring_crypt", "end_phase")
    assert _pick(obs, d) == "bring_crypt"


def test_ignores_opponent_uncontrolled_vampires_for_bring_crypt():
    opp = _vamp("P2-V1", "uncontrolled", 0, controller="P2")
    obs = _obs([opp])
    d = _decision("influence_action", "bring_crypt", "end_phase")
    assert _pick(obs, d) == "bring_crypt"


def test_acts_with_highest_blood_vampire_before_ending():
    obs = _obs([_vamp("V1", "ready", 1), _vamp("V2", "ready", 4)])
    d = _decision("minion_phase_choice", "act_with:V1", "act_with:V2", "end_minion_phase")
    assert _pick(obs, d) == "act_with:V2"


def test_bleeds_with_blood_and_hunts_when_low():
    d = _decision("action_choice", "bleed", "hunt", vampire="V1")
    assert _pick(_obs([_vamp("V1", "ready", 3)]), d) == "bleed"
    assert _pick(_obs([_vamp("V1", "ready", 1)]), d) == "hunt"


def test_master_plays_when_offered_else_nothing_to_play():
    obs = _obs()
    assert _pick(obs, _decision("master_phase_action", "play:0", "pass")) == "play:0"
    assert _pick(obs, _decision("master_phase_action", "pass")) == "pass"


def test_discard_phase_passes_but_hand_size_discard_discards():
    obs = _obs()
    assert _pick(obs, _decision("discard_phase_action", "discard:0", "pass")) == "pass"
    assert _pick(obs, _decision("hand_size_discard", "discard:0", "discard:1")) == "discard:0"


def test_unknown_kind_falls_back_to_seeded_random_within_choices():
    d = _decision("never_heard_of_it", "a", "b", "c")
    first = [HeuristicAgent("P1", 3).decide(_obs(), d).value for _ in range(1)]
    second = [HeuristicAgent("P1", 3).decide(_obs(), d).value for _ in range(1)]
    assert first == second
    agent = HeuristicAgent("P1", 9)
    assert {agent.decide(_obs(), d).value for _ in range(60)} == {"a", "b", "c"}


def test_known_kind_with_unexpected_choice_shape_does_not_crash():
    d = _decision("action_choice", "something_else", vampire="missing")
    assert _pick(_obs(), d) == "something_else"
    d = _decision("influence_action", "weird")
    assert _pick(_obs(), d) == "weird"


class _CheckedHeuristic(HeuristicAgent):
    def decide(self, observation, decision):
        choice = super().decide(observation, decision)
        assert choice in decision.choices
        return choice


def _checked_random(player_id: str, seed: int):
    return (
        _CheckedHeuristic(player_id, seed)
        if player_id == "P1"
        else RandomLegalAgent(player_id, seed)
    )


def test_seeded_sim_games_never_leave_choices_and_never_crash():
    deck = load_suggested_deck()
    decks = {"P1": deck, "P2": deck}
    for factory in (_CheckedHeuristic, _checked_random):
        batch = run_alternating(decks, range(20), agent_factory=factory)
        assert batch.crashes == []
        assert len(batch.results) == 20
