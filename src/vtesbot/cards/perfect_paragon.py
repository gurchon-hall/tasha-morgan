"""Perfect Paragon (Action Modifier). krcg 101387. Snapshot: data/cards/101387.json
1 blood paid as played. [pre] is the caller's alone, once per referendum (ENG-051).
[PRE] any time before resolution [LSJ 20020612]; "younger": ENG-011, RUL-009."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import acting_vampire, discipline_level, has_discipline
from vtesbot.engine.action import PENDING_INTERCEPT_DECREASE_KEY, ActiveInterceptDecrease
from vtesbot.engine.hook_contexts import InterceptDecreaseContext, Pending, PollingStepContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 101387
BLOOD_COST = 1
BASIC_VOTES = 3
SUPERIOR_INTERCEPT_DELTA = -1

card = Card(KRCG_ID, "Perfect Paragon", "Action Modifier")


@card.on(Hook.POLLING_STEP)
def _provide_perfect_paragon_basic(state: GameState, ctx: PollingStepContext) -> list[HookOption]:
    player = ctx["player"]
    if player != ctx["caller"]:
        return []
    vampire = state.players[player].vampires.get(ctx["caller_vampire_id"])
    if vampire is None or not has_discipline(state, vampire, "pre"):
        return []
    if not card.in_hand(state, player) or vampire.blood < BLOOD_COST:
        return []
    pending: Pending | None = ctx["pending"]
    if pending is None:
        return []
    source_id = f"perfect_paragon:{vampire.instance_id}"
    if any(extra["source_id"] == source_id for extra in pending["extra_sources"]):
        return []

    def _apply(s: GameState) -> None:
        card.play_from_hand(s, player)
        vampire.blood -= BLOOD_COST
        pending["extra_sources"].append(
            {
                "source_id": source_id,
                "player": player,
                "votes": BASIC_VOTES,
                "label": f"Perfect Paragon [pre] ({vampire.card.name})",
            }
        )

    return [
        card.option(
            "perfect_paragon:basic", "Perfect Paragon [pre]: this vampire gets +3 votes", _apply
        )
    ]


@card.on(Hook.INTERCEPT_DECREASE)
def _provide_perfect_paragon_superior(
    state: GameState, ctx: InterceptDecreaseContext
) -> list[HookOption]:
    """ "Allies" is vacuous: allies cannot block here. Playing it removes the
    card, so the hook's two offer points cannot both use it."""
    player, vampire = ctx["player"], acting_vampire(state, ctx)
    if vampire is None or discipline_level(state, vampire, "pre") < 2:
        return []
    if not card.in_hand(state, player) or vampire.blood < BLOOD_COST:
        return []
    pending: Pending | None = ctx["pending"]
    if pending is None:
        return []
    younger_than_capacity = vampire.card.capacity

    def _apply(s: GameState) -> None:
        card.play_from_hand(s, player)
        vampire.blood -= BLOOD_COST
        pending.setdefault(PENDING_INTERCEPT_DECREASE_KEY, []).append(
            ActiveInterceptDecrease(
                delta=SUPERIOR_INTERCEPT_DELTA,
                qualifies=lambda v: v.card.capacity < younger_than_capacity,
            )
        )

    return [
        card.option(
            "perfect_paragon:superior",
            "Perfect Paragon [PRE]: allies and younger vampires get -1 intercept",
            _apply,
        )
    ]
