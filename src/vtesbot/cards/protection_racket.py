"""Protection Racket (Reaction). krcg 101501. Snapshot: data/cards/101501.json
"Requires an Anarch" applies to the reacting vampire; "titled" reads the acting
vampire's printed title."""

from vtesbot.cards.card import Card
from vtesbot.engine.cards import Sect
from vtesbot.engine.hook_contexts import InterceptModifierContext, Pending
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101501
USED_BY_KEY = "protection_racket_used_by"

card = Card(KRCG_ID, "Protection Racket", "Reaction")


def _acting_vampire_titled(state: GameState, ctx: InterceptModifierContext) -> bool:
    acting_vampire_id = ctx["acting_vampire"]
    if acting_vampire_id is None:
        return False
    acting_vampire = state.players[ctx["actor"]].vampires.get(acting_vampire_id)
    return acting_vampire is not None and acting_vampire.card.title is not None


@card.on(Hook.INTERCEPT_MODIFIER)
def _provide_protection_racket(state: GameState, ctx: InterceptModifierContext) -> list[HookOption]:
    player = ctx["player"]
    if not card.in_hand(state, player):
        return []
    pending: Pending | None = ctx["pending"]
    used_by: set[str] = pending.setdefault(USED_BY_KEY, set()) if pending is not None else set()
    eligible = [
        v
        for v in state.players[player].vampires.values()
        if v.is_ready_unlocked and v.instance_id not in used_by and v.card.sect is Sect.ANARCH
    ]
    if not eligible:
        return []
    bonus = 2 if _acting_vampire_titled(state, ctx) else 1
    options: list[HookOption] = []
    for vampire in eligible:

        def _apply(s: GameState, v: VampireInPlay = vampire) -> int:
            card.play_from_hand(s, player)
            used_by.add(v.instance_id)
            return bonus

        options.append(
            card.option(
                f"protection_racket:{vampire.instance_id}",
                f"Protection Racket: +{bonus} intercept ({vampire.card.name})",
                _apply,
            )
        )
    return options
