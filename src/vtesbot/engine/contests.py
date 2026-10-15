"""2P contested crypt cards: stay in play, 1 pool/unlock or yield (burn);
same-named titles not contested. OQ-4 (open): trigger moment is ambiguous
-- resolved here as detection on reveal into play."""

from typing import TYPE_CHECKING

from .decision import Choice, Decision
from .pool import can_afford_without_ousting, lose_pool

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay


def detect_contest_on_reveal(state: GameState, revealed: VampireInPlay) -> None:
    opponent = state.other_player(revealed.controller)
    for other in state.players[opponent].vampires.values():
        if other.zone in ("ready", "torpor") and other.card.name == revealed.card.name:
            revealed.contested_with = other.instance_id
            other.contested_with = revealed.instance_id
            return


def resolve_one_contest(state: GameState, player: str, vampire: VampireInPlay) -> None:
    """Rulebook §4 Unlock Phase + 2P variant: pay 1 pool to keep contesting
    `vampire`, or yield (burn it, clearing the opposing copy's contest too)."""
    # OQ-42: paying must not leave the payer at 0 pool; yielding stays.
    pay = (Choice("pay", "Pay 1 pool to keep contesting"),)
    choices = (
        *(pay if can_afford_without_ousting(state, player, 1) else ()),
        Choice("yield", "Yield: burn this vampire"),
    )
    decision = Decision(
        player=player,
        kind="contest_resolution",
        choices=choices,
        context={"vampire": vampire.instance_id, "contested_with": vampire.contested_with},
    )
    choice = state.ask_unless_forced(decision)
    if choice.value == "pay":
        lose_pool(state, player, 1)
    else:
        opponent_vampire = _find_instance(state, vampire.contested_with)
        vampire.zone = "burned"
        vampire.locked = False
        if opponent_vampire is not None:
            opponent_vampire.contested_with = None
        vampire.contested_with = None


def _find_instance(state: GameState, instance_id: str | None) -> VampireInPlay | None:
    if instance_id is None:
        return None
    for player_state in state.players.values():
        if instance_id in player_state.vampires:
            return player_state.vampires[instance_id]
    return None
