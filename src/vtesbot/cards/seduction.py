"""Seduction (Action Modifier). krcg 101712. Snapshot: data/cards/101712.json
Targets the defender's current block candidates; "younger" is lower printed
capacity (ENG-011). The discard is in `cost`: a cancel spends no play (ENG-022)."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import acting_vampire, discipline_level, has_discipline
from vtesbot.engine.action import PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hook_contexts import BlockCandidateExclusionContext, Pending
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101712
SEDUCTION_PLAYED_KEY = "seduction_played"
"""Once per action, either level (Rulebook §2 Action Modifier cards)."""

card = Card(KRCG_ID, "Seduction", "Action Modifier")


def _eligible_targets(
    state: GameState,
    defender: str,
    pending: Pending | None,
    actor_vampire: VampireInPlay,
    require_younger: bool,
) -> list[VampireInPlay]:
    excluded = pending.get(PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY, set()) if pending else set()
    return [
        v
        for v in state.ready_unlocked_vampires(defender)
        if v.instance_id not in excluded
        and (not require_younger or v.card.capacity < actor_vampire.card.capacity)
    ]


def _offer(
    state: GameState, ctx: BlockCandidateExclusionContext, *, superior: bool
) -> list[HookOption]:
    player, vampire = ctx["player"], acting_vampire(state, ctx)
    if vampire is None:
        return []
    if superior and discipline_level(state, vampire, "dom") < 2:
        return []
    if not superior and not has_discipline(state, vampire, "dom"):
        return []
    defender, require_younger = ctx["defender"], not superior
    pending: Pending | None = ctx["pending"]
    if not card.in_hand(state, player) or (pending and pending.get(SEDUCTION_PLAYED_KEY, False)):
        return []
    if not _eligible_targets(state, defender, pending, vampire, require_younger):
        return []

    def _cost(s: GameState) -> None:
        card.play_from_hand(s, player)

    def _apply(s: GameState) -> None:
        targets = _eligible_targets(s, defender, pending, vampire, require_younger)
        if len(targets) == 1:
            target = targets[0]
        else:
            choices = tuple(
                Choice(f"seduction_target:{v.instance_id}", f"Choose {v.card.name}")
                for v in targets
            )
            decision = Decision(player=player, kind="seduction_target", choices=choices)
            target = s.players[defender].vampires[s.ask(decision).value.split(":", 1)[1]]
        if pending is not None:
            pending.setdefault(PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY, set()).add(target.instance_id)
            pending[SEDUCTION_PLAYED_KEY] = True

    if superior:
        value, label = "seduction:superior", "Seduction [DOM]: choose any vampire; cannot block"
    else:
        value, label = "seduction:basic", "Seduction [dom]: choose a younger vampire; cannot block"
    return [card.option(value, label, _apply, cost=_cost)]


@card.on(Hook.BLOCK_CANDIDATE_EXCLUSION)
def _provide_seduction_basic(
    state: GameState, ctx: BlockCandidateExclusionContext
) -> list[HookOption]:
    return _offer(state, ctx, superior=False)


@card.on(Hook.BLOCK_CANDIDATE_EXCLUSION)
def _provide_seduction_superior(
    state: GameState, ctx: BlockCandidateExclusionContext
) -> list[HookOption]:
    return _offer(state, ctx, superior=True)
