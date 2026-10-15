"""Turn sequence (Rulebook §4): Unlock/Master/Minion/Influence/Discard,
acting Methuselah alternates; stops once `game_over` (Rulebook §5).
`clear_turn_cards_at_end_of_turn` runs after discard (OQ-34).
"""

from typing import TYPE_CHECKING

from ..turn_cards import clear_turn_cards_at_end_of_turn
from .discard import discard_phase
from .influence import influence_phase
from .master import master_phase
from .minion import minion_phase
from .unlock import unlock_phase

if TYPE_CHECKING:
    from ..state import GameState

_PHASES = (
    ("unlock", unlock_phase),
    ("master", master_phase),
    ("minion", minion_phase),
    ("influence", influence_phase),
    ("discard", discard_phase),
)


def play_turn(state: GameState) -> None:
    player = state.active_player
    for phase_name, phase_fn in _PHASES:
        state.phase = phase_name
        phase_fn(state, player)
        if state.game_over:
            return
    clear_turn_cards_at_end_of_turn(state, player)
    state.turn_number += 1
    state.active_player = state.other_player(player)


def run_until_game_over(state: GameState, max_turns: int = 1000) -> None:
    """Drive `play_turn` until game end or `max_turns`. `max_turns` is a
    safety valve for tests, not a rule -- a real game only ends via ousting
    (Rulebook §5)."""
    turns_played = 0
    while not state.game_over and turns_played < max_turns:
        play_turn(state)
        turns_played += 1
