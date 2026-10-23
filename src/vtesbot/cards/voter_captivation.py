"""Voter Captivation (Action Modifier). krcg 102131. Snapshot: data/cards/102131.json
"This vampire" is the acting caller, so only the caller plays it (RUL-010); it is
locked by now, so lock is ignored. Discard in `cost`: a cancel spends no grant."""

from collections.abc import Callable

from vtesbot.cards.card import Card
from vtesbot.cards.common import discipline_level, has_discipline
from vtesbot.engine.damage import add_blood
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hook_contexts import ReferendumResolvedContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.pool import gain_pool
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 102131
MAX_REDIRECT = 2
GRANTED_KEY = "voter_captivation_granted_vampires"
"""Once per action, either level (Rulebook §2 Action Modifier cards)."""

card = Card(KRCG_ID, "Voter Captivation", "Action Modifier")


def _caller_vampire(state: GameState, ctx: ReferendumResolvedContext) -> VampireInPlay | None:
    vampire = state.players[ctx["caller"]].vampires.get(ctx["caller_vampire_id"])
    return vampire if vampire is not None and vampire.zone == "ready" else None


def _gate(state: GameState, ctx: ReferendumResolvedContext, level: int) -> VampireInPlay | None:
    """The caller's acting vampire, if it may play the card at `level`."""
    player = ctx["player"]
    if player != ctx["caller"] or not card.in_hand(state, player):
        return None
    granted: set[str] = ctx["pending"].setdefault(GRANTED_KEY, set())
    target = _caller_vampire(state, ctx)
    if target is None or target.instance_id in granted:
        return None
    if level == 1 and not has_discipline(state, target, "pre"):
        return None
    if level == 2 and discipline_level(state, target, "pre") < 2:
        return None
    return target


def _cost(player: str) -> Callable[[GameState], None]:
    def _discard(s: GameState) -> None:
        card.play_from_hand(s, player)

    return _discard


@card.on(Hook.REFERENDUM_RESOLVED)
def _provide_voter_captivation_basic(
    state: GameState, ctx: ReferendumResolvedContext
) -> list[HookOption]:
    target = _gate(state, ctx, 1)
    if target is None:
        return []
    player, margin, granted = ctx["player"], ctx["margin"], ctx["pending"][GRANTED_KEY]

    def _apply(s: GameState, target_id: str = target.instance_id) -> None:
        add_blood(s, s.players[player].vampires[target_id], margin)
        granted.add(target_id)

    return [
        card.option(
            f"voter_captivation:basic:{target.instance_id}",
            f"Voter Captivation [pre]: {target.card.name} gains {margin} blood",
            _apply,
            cost=_cost(player),
        )
    ]


@card.on(Hook.REFERENDUM_RESOLVED)
def _provide_voter_captivation_superior(
    state: GameState, ctx: ReferendumResolvedContext
) -> list[HookOption]:
    target = _gate(state, ctx, 2)
    if target is None:
        return []
    player, margin, granted = ctx["player"], ctx["margin"], ctx["pending"][GRANTED_KEY]

    def _apply(s: GameState, target_id: str = target.instance_id) -> int:
        granted.add(target_id)
        max_redirect = min(MAX_REDIRECT, margin)
        if max_redirect <= 0:
            moved = 0
        else:
            choices = tuple(
                Choice(f"redirect:{n}", f"Move {n} blood to your pool")
                for n in range(0, max_redirect + 1)
            )
            decision = Decision(player=player, kind="voter_captivation_redirect", choices=choices)
            moved = int(s.ask(decision).value.split(":", 1)[1])
        add_blood(s, s.players[player].vampires[target_id], margin - moved)
        gain_pool(s, player, moved)
        return moved

    return [
        card.option(
            f"voter_captivation:superior:{target.instance_id}",
            f"Voter Captivation [PRE]: {target.card.name} gains blood "
            "(move up to 2 to your pool instead)",
            _apply,
            cost=_cost(player),
        )
    ]
