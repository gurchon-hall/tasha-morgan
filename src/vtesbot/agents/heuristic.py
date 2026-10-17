"""Minimal rule-based agent (milestone 5). Every rule is a design choice,
not a VtES fact (D-8). Unrecognized decision kinds fall back to a seeded
random pick, so it can never raise `IllegalChoiceError`."""

import random

from vtesbot.engine.agent import Agent
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.observation import Observation, VampireView

CRITICAL_POOL = 2
LOW_BLOOD = 1
BLEED_AMOUNT_FLOOR = 1
"""The engine's own unmodified base bleed amount (`engine/phases/minion.py`'s
`BLEED_AMOUNT`), used here as a conservative lower bound on what a bleed is
worth: card-sourced bleed bonuses aren't visible generically to the agent
(D-14), so this floor can only undercount a bleed's true lethality, never
overcount it."""
ADD_BLOOD_BASE_SCORE = 10.0
"""Flat preference for spending a transfer on blood over ending the phase
(D-14), matching the pre-Phase-B unconditional choice; `_score_add_blood`'s
capacity-distance and critical-pool penalty terms are kept small relative to
this so they only perturb the ranking among `add_blood` targets and against
the critical-pool penalty, never flip add_blood-vs-end_phase on their own."""
ADD_BLOOD_CRITICAL_POOL_PENALTY = 1000.0
"""Large enough to push a self-critical `add_blood` (one that would itself
drop pool to/under `CRITICAL_POOL`) below `end_phase`'s baseline score of 0,
without making it a hard gate (D-14)."""
OTHER_ACTION_LOSES_TO_BLEED_SCORE = 0.5
OTHER_ACTION_BEATS_HUNT_SCORE = 1.5
"""D-15: scores for any `action_choice` option that is neither `bleed` nor
`hunt` (recruit/diablerise/action-card/attachment-removal options --
whatever the engine's hook providers legally offer alongside them, per
`engine/phases/minion.py::_choose_and_perform_action`). A flat score above
`_score_action`'s own `1.0` ceiling (so it always wins, even over a bleed
with blood to spare) was tried first and reverted: see this module's test
suite note and D-15's benchmark addendum -- it collapsed aggression
(repeatedly spending the minion action on a card play instead of bleeding)
and produced stuck (max-turns) games. These two scores instead keep
bleeding-with-blood as the dominant choice (`0.5 < 1.0`) and only let an
`action_choice` option outrank *hunting* (`1.5 > 1.0`) -- hunting is itself
just a no-damage fallback for a dry vampire, so taking a concrete
card-granted option instead is a narrower, cheaper bet than preferring it
over an available bleed. The agent still has no generic, card-blind way to
judge whether a specific option is actually worth taking (D-13 P3, deferred
past milestone 6); `inf` (a lethal bleed) always overrides both."""


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
        reveal = next((c for c in decision.choices if c.value.startswith("reveal:")), None)
        if reveal is not None:
            return reveal
        own = self._own_vampires(observation)
        pool = observation.pool.get(self.player_id, 0)
        return max(decision.choices, key=lambda c: _score_influence(c, own, pool))

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
        return max(decision.choices, key=lambda c: self._score_action(c, observation, v))

    def _score_action(
        self, choice: Choice, observation: Observation, vampire: VampireView
    ) -> float:
        if choice.value == "bleed":
            opponent = next(p for p in observation.pool if p != self.player_id)
            if observation.pool[opponent] <= BLEED_AMOUNT_FLOOR:
                return float("inf")
            return 1.0 if vampire.blood > LOW_BLOOD else 0.0
        if choice.value == "hunt":
            return 1.0 if vampire.blood <= LOW_BLOOD else 0.0
        return (
            OTHER_ACTION_BEATS_HUNT_SCORE
            if vampire.blood <= LOW_BLOOD
            else OTHER_ACTION_LOSES_TO_BLEED_SCORE
        )

    def _master(self, observation: Observation, decision: Decision) -> Choice | None:
        # Left as "play the first offered card" (D-8/D-14): `decision.choices`
        # is already legality-filtered by the engine's hook providers, and
        # `Observation` carries no effect-preview field, so "skip a useless
        # play" isn't cheaply derivable without card-specific knowledge --
        # deferred to milestone 6/7 (audit report P3), not an oversight.
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


def _score_influence(choice: Choice, own: dict[str, VampireView], pool: int) -> float:
    kind, _, arg = choice.value.partition(":")
    if kind == "add_blood":
        return _score_add_blood(arg, own, pool)
    if kind == "bring_crypt":
        return _score_bring_crypt(own, pool)
    if kind == "remove_blood":
        return _score_remove_blood(arg, own, pool)
    return 0.0  # end_phase and any unrecognized kind: neutral baseline.


def _score_add_blood(arg: str, own: dict[str, VampireView], pool: int) -> float:
    v = own.get(arg)
    if v is None or v.capacity is None:
        remaining, blood = float("inf"), 0
    else:
        remaining, blood = v.capacity - v.blood, v.blood
    score = ADD_BLOOD_BASE_SCORE - remaining * 0.01 + blood * 0.0001
    if pool - 1 <= CRITICAL_POOL:
        score -= ADD_BLOOD_CRITICAL_POOL_PENALTY
    return score


def _score_bring_crypt(own: dict[str, VampireView], pool: int) -> float:
    has_uncontrolled = any(v.zone == "uncontrolled" for v in own.values())
    if has_uncontrolled:
        return float("-inf")
    # `bring_crypt` is a flat 1-pool cost in this engine (`engine/phases/
    # influence.py::_apply`) -- there is no variable per-crypt-card cost to
    # account for here.
    pool_after_cost = pool - 1
    return pool_after_cost - CRITICAL_POOL


def _score_remove_blood(arg: str, own: dict[str, VampireView], pool: int) -> float:
    if pool > CRITICAL_POOL:
        return float("-inf")
    v = own.get(arg)
    return float(v.blood) if v is not None else 0.0


_HANDLERS = {
    "influence_action": HeuristicAgent._influence,
    "minion_phase_choice": HeuristicAgent._minion_phase,
    "action_choice": HeuristicAgent._action,
    "master_phase_action": HeuristicAgent._master,
    "discard_phase_action": HeuristicAgent._pass,
    "hand_size_discard": HeuristicAgent._forced_discard,
}
