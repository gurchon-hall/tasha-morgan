"""Fiorenza Savona (Vampire). krcg 201616. Snapshot: data/cards/201616.json
+1 on an Edge or political-action-card-from-hand cast by her controller, while
she is in play; the caller's own card vote does not count (ENG-031)."""

from vtesbot.cards.card import Card
from vtesbot.engine.hook_contexts import VoteSourceCastBonusContext
from vtesbot.engine.hooks import Hook
from vtesbot.engine.state import GameState

KRCG_ID = 201616
_OUT_OF_PLAY = ("uncontrolled", "burned", "removed_from_game")

card = Card(KRCG_ID, "Fiorenza Savona")


@card.on(Hook.VOTE_SOURCE_CAST_BONUS)
def _cast_bonus(state: GameState, ctx: VoteSourceCastBonusContext) -> int:
    if not (ctx["burns_edge"] or ctx["burns_pac_from_hand"]):
        return 0
    in_play = any(
        vampire.card.krcg_id == KRCG_ID and vampire.zone not in _OUT_OF_PLAY
        for vampire in state.players[ctx["caster"]].vampires.values()
    )
    return 1 if in_play else 0
