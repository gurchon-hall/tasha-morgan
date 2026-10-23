"""Taste of Vitae (Combat). krcg 101945. Snapshot: data/cards/101945.json
Only the playing vampire's zone is checked: it can be played if the opponent
was burned [LSJ 20031201-2]. End-of-round window: ENG-020."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import window_sides
from vtesbot.engine.damage import add_blood, blood_lost_to_damage_this_round
from vtesbot.engine.hook_contexts import EndOfRoundContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 101945
_USED_KEY = "taste_of_vitae_used"
_EXCLUDED_ZONES = ("burned", "torpor")

card = Card(KRCG_ID, "Taste of Vitae", "Combat")


@card.on(Hook.END_OF_ROUND)
def _play(state: GameState, ctx: EndOfRoundContext) -> list[HookOption]:
    player, round_state = ctx["player"], ctx["round_state"]
    vampire_id, _, opponent_id = window_sides(ctx)
    vampire = state.players[player].vampires.get(vampire_id)
    if vampire is None or vampire.zone in _EXCLUDED_ZONES:
        return []
    if not card.in_hand(state, player):
        return []
    if round_state.get(_USED_KEY, {}).get(vampire_id):
        return []  # "A vampire can play only one Taste of Vitae each round."
    preview = blood_lost_to_damage_this_round(round_state, opponent_id)

    def _apply(s: GameState) -> int:
        card.play_from_hand(s, player)
        round_state.setdefault(_USED_KEY, {})[vampire_id] = True
        # Recomputed: the window repeats, so another effect may have run since the offer.
        return add_blood(s, vampire, blood_lost_to_damage_this_round(round_state, opponent_id))

    return [card.option("taste_of_vitae", f"Taste of Vitae: gain {preview} blood", _apply)]
