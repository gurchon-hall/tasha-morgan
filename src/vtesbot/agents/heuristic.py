"""Minimal rule-based agent (CLAUDE.md milestone 5, first pass).

Every rule is a design choice, not a VtES fact: see `docs/DECISIONS.md`
(D-8). Picks only from `decision.choices` and reads only the
`Observation`; any decision kind or choice shape it does not recognise
falls back to a seeded random pick, so it can never raise
`IllegalChoiceError`.
"""

import random

from vtesbot.engine.agent import Agent
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.observation import Observation, VampireView

CRITICAL_POOL = 2
LOW_BLOOD = 1


class HeuristicAgent(Agent):
    def __init__(self, player_id: str, seed: int) -> None:
        self.player_id = player_id
        self._random = random.Random(seed)

    def decide(self, observation: Observation, decision: Decision) -> Choice:
        handler = _HANDLERS.get(decision.kind)
        picked = handler(self, observation, decision) if handler else None
        if picked is None or picked not in decision.choices:
            return self._random.choice(decision.choices)
        return picked

    def _own_vampires(self, observation: Observation) -> dict[str, VampireView]:
        return {v.instance_id: v for v in observation.vampires if v.controller == self.player_id}

    def _influence(self, observation: Observation, decision: Decision) -> Choice | None:
        by_kind: dict[str, list[tuple[str, Choice]]] = {}
        for c in decision.choices:
            kind, _, arg = c.value.partition(":")
            by_kind.setdefault(kind, []).append((arg, c))
        own = self._own_vampires(observation)
        pool = observation.pool.get(self.player_id, 0)

        def fill(arg: str) -> tuple[int, int]:
            v = own.get(arg)
            if v is None or v.capacity is None:
                return (1 << 30, 0)
            return (v.capacity - v.blood, -v.blood)

        if "reveal" in by_kind:
            return by_kind["reveal"][0][1]
        if pool > CRITICAL_POOL:
            has_uncontrolled = any(v.zone == "uncontrolled" for v in own.values())
            if not has_uncontrolled and "bring_crypt" in by_kind:
                return by_kind["bring_crypt"][0][1]
            if "add_blood" in by_kind:
                return min(by_kind["add_blood"], key=lambda t: fill(t[0]))[1]
        elif "remove_blood" in by_kind:
            return max(
                by_kind["remove_blood"], key=lambda t: own[t[0]].blood if t[0] in own else 0
            )[1]
        return _by_value(decision, "end_phase")

    def _minion_phase(self, observation: Observation, decision: Decision) -> Choice | None:
        own = self._own_vampires(observation)
        acts = [c for c in decision.choices if c.value.startswith("act_with:")]
        if not acts:
            return None

        def blood(c: Choice) -> int:
            v = own.get(c.value.partition(":")[2])
            return v.blood if v else -1

        return max(acts, key=blood)

    def _action(self, observation: Observation, decision: Decision) -> Choice | None:
        v = self._own_vampires(observation).get(str(decision.context.get("vampire")))
        if v is None:
            return None
        return _by_value(decision, "hunt" if v.blood <= LOW_BLOOD else "bleed")

    def _master(self, observation: Observation, decision: Decision) -> Choice | None:
        del observation
        plays = [c for c in decision.choices if c.value != "pass"]
        return plays[0] if plays else None

    def _pass(self, observation: Observation, decision: Decision) -> Choice | None:
        del observation
        return _by_value(decision, "pass")

    def _forced_discard(self, observation: Observation, decision: Decision) -> Choice | None:
        del observation
        return decision.choices[0]


def _by_value(decision: Decision, value: str) -> Choice | None:
    return next((c for c in decision.choices if c.value == value), None)


_HANDLERS = {
    "influence_action": HeuristicAgent._influence,
    "minion_phase_choice": HeuristicAgent._minion_phase,
    "action_choice": HeuristicAgent._action,
    "master_phase_action": HeuristicAgent._master,
    "discard_phase_action": HeuristicAgent._pass,
    "hand_size_discard": HeuristicAgent._forced_discard,
}
