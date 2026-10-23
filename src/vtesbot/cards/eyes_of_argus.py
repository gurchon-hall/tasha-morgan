"""Eyes of Argus (Reaction). krcg 100680. Snapshot: data/cards/100680.json
In a duel, "directed at you (or a card you control)" is `directed` (CLAUDE.md
§3). [AUS] wakes like On the Qui Vive (ENG-030, ENG-060). One play per vampire per action."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import discipline_level, has_discipline
from vtesbot.engine.hook_contexts import InterceptModifierContext, Pending, WakeLockedMinionContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 100680
NAME = "Eyes of Argus"
INTERCEPT_BONUS = 2
USED_BY_KEY = "eyes_of_argus_used_by"

card = Card(KRCG_ID, NAME, "Reaction")


def _used_by(pending: Pending | None) -> set[str]:
    return set() if pending is None else pending.setdefault(USED_BY_KEY, set())


@card.on(Hook.INTERCEPT_MODIFIER)
def _provide_eyes_of_argus_intercept(
    state: GameState, ctx: InterceptModifierContext
) -> list[HookOption]:
    player = ctx["player"]
    if ctx["directed"] is not True or not card.in_hand(state, player):
        return []
    used_by = _used_by(ctx["pending"])
    options: list[HookOption] = []
    for vampire in state.players[player].vampires.values():
        if not vampire.is_ready_unlocked or vampire.instance_id in used_by:
            continue
        if not has_discipline(state, vampire, "aus"):
            continue

        def _apply(s: GameState, v: VampireInPlay = vampire) -> int:
            card.play_from_hand(s, player)
            used_by.add(v.instance_id)
            return INTERCEPT_BONUS

        options.append(
            card.option(
                f"eyes_of_argus:basic:{vampire.instance_id}",
                f"Eyes of Argus [aus]: +{INTERCEPT_BONUS} intercept ({vampire.card.name})",
                _apply,
            )
        )
    return options


@card.on(Hook.WAKE_LOCKED_MINION)
def _provide_eyes_of_argus_wake(state: GameState, ctx: WakeLockedMinionContext) -> list[HookOption]:
    player = ctx["player"]
    if not card.in_hand(state, player):
        return []
    used_by = _used_by(ctx["pending"])
    eligible = [
        v
        for v in state.players[player].vampires.values()
        if v.zone == "ready"
        and v.locked
        and not v.woken
        and v.instance_id not in used_by
        and discipline_level(state, v, "aus") == 2
    ]
    options: list[HookOption] = []
    for vampire in eligible:

        def _apply(s: GameState, v: VampireInPlay = vampire) -> None:
            card.play_from_hand(s, player)
            used_by.add(v.instance_id)
            v.woken = True

        options.append(
            card.option(
                f"eyes_of_argus:superior:{vampire.instance_id}",
                f"Eyes of Argus [AUS]: wake {vampire.card.name}",
                _apply,
            )
        )
    return options
