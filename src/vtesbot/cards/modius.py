"""Modius (Vampire). krcg 201703. Snapshot: data/cards/201703.json
Any referendum, also from torpor [LSJ 20011022]; no cap but the master cards in
hand. Auto-passing referenda [PIB 20150105] do not exist in this engine yet."""

from vtesbot.cards.card import Card
from vtesbot.engine.hook_contexts import PollingStepContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 201703
MASTER_CARD_TYPE = "Master"

card = Card(KRCG_ID, "Modius")


def _controlled_modius(state: GameState, player: str) -> VampireInPlay | None:
    for vampire in state.players[player].vampires.values():
        if vampire.card.krcg_id == KRCG_ID and vampire.zone in ("ready", "torpor"):
            return vampire
    return None


def _discard_one_master_card_from_hand(state: GameState, player: str) -> None:
    """A plain discard, no replacement; which master card never matters."""
    hand = state.players[player].hand
    for index, hand_card in enumerate(hand):
        if hand_card.card_type == MASTER_CARD_TYPE:
            state.players[player].ash_heap.append(hand.pop(index))
            return
    raise AssertionError(
        f"{player} has no master card left in hand to discard for Modius's +1 vote "
        "(engine invariant violation, not a legal game state)"
    )


@card.on(Hook.POLLING_STEP)
def _provide_modius(state: GameState, ctx: PollingStepContext) -> list[HookOption]:
    player = ctx["player"]
    modius = _controlled_modius(state, player)
    if modius is None:
        return []
    if not any(c.card_type == MASTER_CARD_TYPE for c in state.players[player].hand):
        return []
    pending = ctx["pending"]

    def _apply(s: GameState) -> None:
        _discard_one_master_card_from_hand(s, player)
        suffix = len(pending["extra_sources"])
        pending["extra_sources"].append(
            {
                "source_id": f"modius:{modius.instance_id}:{suffix}",
                "player": player,
                "votes": 1,
                "label": "Modius: discard a master card for +1 vote",
            }
        )

    return [
        card.option(
            f"modius_discard_master:{modius.instance_id}",
            "Modius [pre]: discard a master card for +1 vote",
            _apply,
        )
    ]
