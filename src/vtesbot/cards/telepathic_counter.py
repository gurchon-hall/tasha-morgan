"""Telepathic Counter (Reaction). krcg 101948. Snapshot: data/cards/101948.json
Played after blocks, which gives the same result as before [TOM 19960303]. The
discard and the once-per-minion mark are in `cost`, so a cancel keeps them (ENG-022)."""

from collections.abc import Callable

from vtesbot.cards.card import Card
from vtesbot.cards.common import bleed_bookkeeping, discipline_level, has_discipline
from vtesbot.engine.hook_contexts import BleedAmountModifierContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 101948
USED_BY_KEY = "telepathic_counter_used_by"

card = Card(KRCG_ID, "Telepathic Counter", "Reaction")


def _reduce(amount_box: list[int], delta: int) -> Callable[[GameState], None]:
    def _apply(_s: GameState) -> None:
        amount_box[0] -= delta

    return _apply


@card.on(Hook.BLEED_AMOUNT_MODIFIER)
def _play(state: GameState, ctx: BleedAmountModifierContext) -> list[HookOption]:
    player = ctx["player"]
    if ctx["vampire"] in state.players[player].vampires:
        return []  # `player` is the bleeder
    if not card.in_hand(state, player):
        return []
    amount_box = ctx["amount"]
    used_by: set[str] = bleed_bookkeeping(ctx["pending"]).setdefault(USED_BY_KEY, set())
    eligible = [
        v
        for v in state.players[player].vampires.values()
        if v.is_ready_unlocked and v.instance_id not in used_by and has_discipline(state, v, "aus")
    ]
    options: list[HookOption] = []
    for vampire in eligible:
        vampire_id, name = vampire.instance_id, vampire.card.name

        def _cost(s: GameState, vampire_id: str = vampire_id) -> None:
            card.play_from_hand(s, player)
            used_by.add(vampire_id)

        options.append(
            card.option(
                f"telepathic_counter:basic:{vampire_id}",
                f"Telepathic Counter [aus]: reduce bleed by 1 ({name})",
                _reduce(amount_box, 1),
                cost=_cost,
            )
        )
        if discipline_level(state, vampire, "aus") == 2:
            options.append(
                card.option(
                    f"telepathic_counter:superior:{vampire_id}",
                    f"Telepathic Counter [AUS]: reduce bleed by 2 ({name})",
                    _reduce(amount_box, 2),
                    cost=_cost,
                )
            )
    return options
