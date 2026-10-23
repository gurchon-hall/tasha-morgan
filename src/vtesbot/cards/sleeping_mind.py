"""The Sleeping Mind (Action Modifier). krcg 101805. Snapshot: data/cards/101805.json
[dom] only; [DOM] is ENG-059. A named locked vampire stays excluded once woken
[PIB 20150703]. Discard and blood are in `cost`: a cancel spends no play."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import acting_vampire, has_discipline
from vtesbot.engine.action import PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hook_contexts import BlockCandidateExclusionContext, Pending
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101805
BLOOD_COST = 1
SLEEPING_MIND_PLAYED_KEY = "sleeping_mind_played"
"""Once per action (Rulebook §2 Action Modifier cards)."""

card = Card(KRCG_ID, "Sleeping Mind, The", "Action Modifier")


def _eligible_locked_targets(
    state: GameState, defender: str, pending: Pending | None
) -> list[VampireInPlay]:
    excluded = pending.get(PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY, set()) if pending else set()
    return [
        v
        for v in state.players[defender].vampires.values()
        if v.zone == "ready" and v.locked and v.instance_id not in excluded
    ]


@card.on(Hook.BLOCK_CANDIDATE_EXCLUSION)
def _provide_sleeping_mind_basic(
    state: GameState, ctx: BlockCandidateExclusionContext
) -> list[HookOption]:
    player, vampire = ctx["player"], acting_vampire(state, ctx)
    if vampire is None or not has_discipline(state, vampire, "dom"):
        return []
    if not card.in_hand(state, player) or vampire.blood < BLOOD_COST:
        return []
    defender = ctx["defender"]
    pending: Pending | None = ctx["pending"]
    if pending and pending.get(SLEEPING_MIND_PLAYED_KEY, False):
        return []
    if not _eligible_locked_targets(state, defender, pending):
        return []

    def _cost(s: GameState) -> None:
        card.play_from_hand(s, player)
        vampire.blood -= BLOOD_COST

    def _apply(s: GameState) -> None:
        targets = _eligible_locked_targets(s, defender, pending)
        if len(targets) == 1:
            target = targets[0]
        else:
            choices = tuple(
                Choice(f"sleeping_mind_target:{v.instance_id}", f"Choose {v.card.name}")
                for v in targets
            )
            decision = Decision(player=player, kind="sleeping_mind_target", choices=choices)
            target = s.players[defender].vampires[s.ask(decision).value.split(":", 1)[1]]
        if pending is not None:
            pending.setdefault(PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY, set()).add(target.instance_id)
            pending[SLEEPING_MIND_PLAYED_KEY] = True

    return [
        card.option(
            "sleeping_mind:basic",
            "The Sleeping Mind [dom]: burn 1 blood, choose a locked vampire; cannot block",
            _apply,
            cost=_cost,
        )
    ]
