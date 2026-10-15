"""Standalone Master cards in play (OQ-23): bring in, detect/resolve a contest. krcg has
no `Type.LOCATION`; "Unique location." is free text on an ordinary `Master` card.
Mirrors `allies.py`'s shape."""

from typing import TYPE_CHECKING

from .decision import Choice, Decision
from .pool import can_afford_without_ousting, lose_pool
from .state import MasterCardInPlay

if TYPE_CHECKING:
    from .state import GameState


def bring_master_card_into_play(
    state: GameState,
    player: str,
    *,
    krcg_id: int,
    name: str,
) -> MasterCardInPlay:
    """Bring a new standalone Master card into play under `player`'s control. Starts
    `zone="in_play"`, `locked=False` (no "enters locked" clause, unlike Recruit Ally)."""
    p = state.players[player]
    instance_id = p.new_master_card_instance_id()
    card = MasterCardInPlay(
        instance_id=instance_id,
        krcg_id=krcg_id,
        name=name,
        controller=player,
    )
    p.master_cards[instance_id] = card
    return card


def detect_contest_on_bring_into_play(state: GameState, brought_in: MasterCardInPlay) -> None:
    """Flag `brought_in` and a same-named opposing instance as contested (§4, OQ-10/
    OQ-23; not 2P-overridden). Only for a "Unique" card; matched by `name`; self-contest
    unimplemented everywhere (OQ-16)."""
    opponent = state.other_player(brought_in.controller)
    for other in state.players[opponent].master_cards.values():
        if other.zone == "in_play" and other.name == brought_in.name:
            brought_in.contested_with = other.instance_id
            other.contested_with = brought_in.instance_id
            brought_in.zone = "contested"
            other.zone = "contested"
            return


def transfer_master_card_control(
    state: GameState, card: MasterCardInPlay, new_controller: str
) -> None:
    """Change controller of a standalone `MasterCardInPlay` (OQ-35; Disputed Territory
    [RTR 19980623]). Never "on" anything, so no re-host (contrast `attachments.py`).
    Re-keys into the new controller's dict."""
    old_controller = card.controller
    del state.players[old_controller].master_cards[card.instance_id]
    card.controller = new_controller
    state.players[new_controller].master_cards[card.instance_id] = card


def resolve_one_master_card_contest(state: GameState, player: str, card: MasterCardInPlay) -> None:
    """§4 Unlock + Contested Cards (OQ-15, generalized by OQ-23): pay 1 pool to keep
    contesting, or yield (burn own copy). No 2P override: survivor's `zone` restores
    only on its next unlock phase."""
    # OQ-42: paying must not leave the payer at 0 pool; yielding stays.
    pay = (Choice("pay", "Pay 1 pool to keep contesting"),)
    choices = (
        *(pay if can_afford_without_ousting(state, player, 1) else ()),
        Choice("yield", "Yield: burn this card"),
    )
    decision = Decision(
        player=player,
        kind="master_card_contest_resolution",
        choices=choices,
        context={"card": card.instance_id, "contested_with": card.contested_with},
    )
    choice = state.ask_unless_forced(decision)
    if choice.value == "pay":
        lose_pool(state, player, 1)
    else:
        opponent_card = _find_master_card_instance(state, card.contested_with)
        card.zone = "burned"
        card.locked = False
        if opponent_card is not None:
            # Cleared immediately (nothing contests the opponent's copy any
            # more), but its `zone` deliberately stays "contested" here --
            # see this function's own docstring and `_unlock_own_master_cards`.
            opponent_card.contested_with = None
        card.contested_with = None


def _find_master_card_instance(
    state: GameState, instance_id: str | None
) -> MasterCardInPlay | None:
    if instance_id is None:
        return None
    for player_state in state.players.values():
        if instance_id in player_state.master_cards:
            return player_state.master_cards[instance_id]
    return None
