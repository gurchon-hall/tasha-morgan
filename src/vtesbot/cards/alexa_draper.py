"""Alexa Draper (Vampire). krcg 201529. Snapshot: data/cards/201529.json
Any referendum; usable while locked, not from torpor, once per referendum
[ANK 20220705]. In hand, a card requires all its disciplines [LSJ 20011204-3]."""

from vtesbot.cards.card import Card
from vtesbot.engine.cards import LibraryCard, requires_discipline
from vtesbot.engine.hook_contexts import Pending, PollingStepContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 201529
DOMINATE = "dom"
PENDING_USED_KEY = "alexa_draper_used"

card = Card(KRCG_ID, "Alexa Draper")


def _controlled_ready_alexa(state: GameState, player: str) -> VampireInPlay | None:
    for vampire in state.players[player].vampires.values():
        if vampire.card.krcg_id == KRCG_ID and vampire.zone == "ready":
            return vampire
    return None


def _discard_one_card_from_hand_by_krcg_id(state: GameState, player: str, krcg_id: int) -> None:
    """A plain discard: no replacement. Copies are interchangeable."""
    hand = state.players[player].hand
    for index, hand_card in enumerate(hand):
        if hand_card.krcg_id == krcg_id:
            state.players[player].ash_heap.append(hand.pop(index))
            return
    raise AssertionError(
        f"{player} has no krcg_id={krcg_id} Dominate-requiring card left in hand to discard "
        "for Alexa Draper's +1 vote (engine invariant violation, not a legal game state)"
    )


@card.on(Hook.POLLING_STEP)
def _provide_alexa_draper(state: GameState, ctx: PollingStepContext) -> list[HookOption]:
    player = ctx["player"]
    alexa = _controlled_ready_alexa(state, player)
    if alexa is None:
        return []
    pending: Pending | None = ctx["pending"]
    if pending is None or pending.get(PENDING_USED_KEY, False):
        return []
    eligible: list[LibraryCard] = [
        c
        for c in state.players[player].hand
        if requires_discipline(c.discipline_requirement, DOMINATE)
    ]
    options: list[HookOption] = []
    for index, hand_card in enumerate(eligible):

        def _apply(s: GameState, krcg_id: int = hand_card.krcg_id) -> None:
            _discard_one_card_from_hand_by_krcg_id(s, player, krcg_id)
            pending[PENDING_USED_KEY] = True
            pending["extra_sources"].append(
                {
                    "source_id": f"alexa_draper:{alexa.instance_id}",
                    "player": player,
                    "votes": 1,
                    "label": "Alexa Draper: discard a card requiring Dominate for +1 vote",
                }
            )

        options.append(
            card.option(
                f"alexa_draper:{index}:{hand_card.krcg_id}",
                f"Alexa Draper [dom]: discard {hand_card.name} (requires Dominate) for +1 vote",
                _apply,
            )
        )
    return options
