"""2P contested crypt cards.

Source: 2P variant (per the `vtes-rules-reference` skill condensed mapping):
"Rulebook: contested cards go face down, out of play. 2P: contested crypt
cards stay in play and usable; 1 pool each unlock phase or yield (burn). You
cannot contest with yourself." Titles on two copies of the same vampire are
explicitly *not* contested in 2P -- that title-contest exception is
politics-adjacent and deferred (CLAUDE.md task scope for this pass).

Open question (docs/OPEN_QUESTIONS.md OQ-4): the 2P variant text (as mapped
by the skill) gives the contest *resolution* cost but not the exact trigger
moment. Because 2P duel decks are built independently (unlike the combined-
crypt setup of 4-5 player VTES), the same unique vampire (by printed name,
Rulebook SS1: vampire names are unique) can appear in both players' crypts.
This module resolves the ambiguity conservatively: a contest is detected the
moment a vampire is *revealed into play* (ready/torpor) and the opponent
already controls a same-named vampire that is also in play -- not merely
while both copies sit face down, uncontrolled. See OQ-4 for the citation gap
and the alternative reading (contest on simultaneous uncontrolled presence).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .decision import Choice, Decision
from .pool import lose_pool

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay


def detect_contest_on_reveal(state: GameState, revealed: VampireInPlay) -> None:
    """Flag `revealed` and any same-named in-play opposing vampire as contested."""
    opponent = state.other_player(revealed.controller)
    for other in state.players[opponent].vampires.values():
        if other.zone in ("ready", "torpor") and other.card.name == revealed.card.name:
            revealed.contested_with = other.instance_id
            other.contested_with = revealed.instance_id
            return


def resolve_one_contest(state: GameState, player: str, vampire: VampireInPlay) -> None:
    """Rulebook SS4 Unlock Phase + 2P variant: pay 1 pool to keep contesting
    `vampire` this unlock phase, or yield (burn your copy, clearing the
    opposing copy's contested status too since nothing contests it anymore)."""
    choices = (
        Choice("pay", "Pay 1 pool to keep contesting"),
        Choice("yield", "Yield: burn this vampire"),
    )
    decision = Decision(
        player=player,
        kind="contest_resolution",
        choices=choices,
        context={"vampire": vampire.instance_id, "contested_with": vampire.contested_with},
    )
    choice = state.ask(decision)
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
