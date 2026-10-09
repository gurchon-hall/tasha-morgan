"""Turn sequence orchestration.

Source: Rulebook SS4 (per the `vtes-rules-reference` skill condensed
mapping): the five phases in order are Unlock, Master, Minion, Influence,
Discard; the acting Methuselah alternates each turn in a 2-player duel.
`play_turn`/`run_until_game_over` are pure control-flow conveniences (not
separately-sourced rules) that drive the phase functions in order and stop
as soon as `state.game_over` becomes true (Rulebook SS5 Ending the Game:
the game ends immediately on an oust in a 2-player duel).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    state.turn_number += 1
    state.active_player = state.other_player(player)


def run_until_game_over(state: GameState, max_turns: int = 1000) -> None:
    """Drive `play_turn` until the game ends or `max_turns` is exceeded.

    `max_turns` is a safety valve for tests/sim runs, not a rule; a real
    game only ends via ousting (Rulebook SS5) or (later) advanced
    withdrawal rules, which are out of scope for this milestone.
    """
    turns_played = 0
    while not state.game_over and turns_played < max_turns:
        play_turn(state)
        turns_played += 1
