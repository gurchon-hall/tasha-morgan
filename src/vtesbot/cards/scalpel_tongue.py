"""Scalpel Tongue (Action Modifier / Reaction). krcg 101686. Snapshot: data/cards/101686.json
Needs both disciplines at the level used. The caller plays it as an action modifier,
the other side as a reaction (RUL-010, ENG-023). Title casts only: ENG-027, ENG-056."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import discipline_level
from vtesbot.engine.hook_contexts import PollingStepContext, PollingStepMidCastContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101686
BURN_AMOUNT = 1
CALLER_CARD_TYPE = "Action Modifier"
NON_CALLER_CARD_TYPE = "Reaction"

card = Card(KRCG_ID, "Scalpel Tongue", CALLER_CARD_TYPE)


def _has_combo(state: GameState, vampire: VampireInPlay, level: int) -> bool:
    return (
        discipline_level(state, vampire, "cel") >= level
        and discipline_level(state, vampire, "pre") >= level
    )


def _may_play(state: GameState, ctx: PollingStepMidCastContext, level: int) -> bool:
    """The caller's acting vampire need only be ready (RUL-010); the other
    side needs a ready, unlocked vampire, as for any reaction."""
    player = ctx["player"]
    if player == ctx["caller"]:
        vampire = state.players[player].vampires.get(ctx["caller_vampire_id"])
        return vampire is not None and vampire.zone == "ready" and _has_combo(state, vampire, level)
    return any(
        v.is_ready_unlocked and _has_combo(state, v, level)
        for v in state.players[player].vampires.values()
    )


def _offer(state: GameState, ctx: PollingStepContext, *, superior: bool) -> list[HookOption]:
    if ctx["phase"] != "mid_cast":
        return []
    player, level = ctx["player"], 2 if superior else 1
    if not _may_play(state, ctx, level) or not card.in_hand(state, player):
        return []
    played_card_type = CALLER_CARD_TYPE if player == ctx["caller"] else NON_CALLER_CARD_TYPE
    options: list[HookOption] = []
    for cast_player, source_id, _votes, _direction in ctx["casts"]:
        if not source_id.startswith("title:"):
            continue
        instance_id = source_id.split(":", 1)[1]
        target = state.players[cast_player].vampires.get(instance_id)
        if target is None:
            continue

        def _apply(
            s: GameState, cast_player: str = cast_player, instance_id: str = instance_id
        ) -> str:
            card.play_from_hand(s, player)
            vampire = s.players[cast_player].vampires[instance_id]
            vampire.locked = True
            if superior:
                vampire.blood = max(0, vampire.blood - BURN_AMOUNT)
            return f"title:{instance_id}"

        if superior:
            value = f"scalpel_tongue:superior:{source_id}"
            label = (
                f"Scalpel Tongue [CEL][PRE]: lock {target.card.name}, cancel their vote, "
                "and burn 1 blood"
            )
        else:
            value = f"scalpel_tongue:basic:{source_id}"
            label = f"Scalpel Tongue [cel][pre]: lock {target.card.name} and cancel their vote"
        options.append(card.option(value, label, _apply, played_card_type=played_card_type))
    return options


@card.on(Hook.POLLING_STEP)
def _provide_scalpel_tongue_basic(state: GameState, ctx: PollingStepContext) -> list[HookOption]:
    return _offer(state, ctx, superior=False)


@card.on(Hook.POLLING_STEP)
def _provide_scalpel_tongue_superior(state: GameState, ctx: PollingStepContext) -> list[HookOption]:
    return _offer(state, ctx, superior=True)
