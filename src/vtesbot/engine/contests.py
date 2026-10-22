"""2P contested crypt cards: stay in play, 1 pool/unlock or yield (burn);
same-named titles not contested. RUL-003 (resolved): contest triggers on reveal into play."""

from typing import TYPE_CHECKING

from .decision import Choice, Decision
from .pool import can_afford_without_ousting, lose_pool

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay


def detect_contest_on_reveal(state: GameState, revealed: VampireInPlay) -> None:
    """Rulebook §4 Advanced Rules > Contested Cards, plus the caution box's own "cannot
    contest yourself" clause (ENG-010), quoted verbatim: "You cannot control more than one
    of the same unique card at a time, and you cannot voluntarily contest cards with
    yourself (if some effect would force you to contest a card with yourself, then you
    simply burn the incoming copy of the unique card)." Checked first, against
    `revealed`'s own controller's other live same-named copies -- a same-controller
    collision burns `revealed` immediately and never reaches the opponent-side contest
    check below."""
    own = state.players[revealed.controller]
    for mine in own.vampires.values():
        if mine is revealed:
            continue
        if mine.zone in ("ready", "torpor") and mine.card.name == revealed.card.name:
            revealed.zone = "burned"
            revealed.locked = False
            return
    opponent = state.other_player(revealed.controller)
    for other in state.players[opponent].vampires.values():
        if other.zone in ("ready", "torpor") and other.card.name == revealed.card.name:
            revealed.contested_with = other.instance_id
            other.contested_with = revealed.instance_id
            return


def resolve_one_contest(state: GameState, player: str, vampire: VampireInPlay) -> None:
    """Rulebook §4 Unlock Phase + 2P variant: pay 1 pool to keep contesting
    `vampire`, or yield (burn it, clearing the opposing copy's contest too)."""
    # DES-009: paying must not leave the payer at 0 pool; yielding stays.
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
