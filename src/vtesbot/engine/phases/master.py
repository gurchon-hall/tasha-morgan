"""Master phase (Rulebook §4): 1 action by default, trifle grants one
extra (max one/phase); parameterized by `master_phase_play` providers.
Out-of-turn master is out of scope (future hook).
"""

from typing import TYPE_CHECKING

from .. import hooks
from ..decision import Choice, Decision

if TYPE_CHECKING:
    from ..state import GameState

MASTER_PHASE_PLAY_HOOK = "master_phase_play"
BASE_MASTER_ACTIONS = 1
MAX_TRIFLE_BONUS_ACTIONS = 1
"""Rulebook §4 Master Phase: trifles grant one extra action, max one per phase."""


def master_phase(state: GameState, player: str) -> None:
    actions_remaining = BASE_MASTER_ACTIONS
    trifle_bonus_used = False

    while actions_remaining > 0 and not state.game_over:
        options = hooks.offer(MASTER_PHASE_PLAY_HOOK, state, player=player)
        if not options:
            return  # nothing legal to play: no vacuous decision raised.

        by_value = {o.choice.value: o for o in options}
        choices = tuple(o.choice for o in options) + (
            Choice("pass", "Pass (no master phase action)"),
        )
        decision = Decision(
            player=player,
            kind="master_phase_action",
            choices=choices,
            context={"actions_remaining": actions_remaining},
        )
        answer = state.ask(decision)
        if answer.value == "pass":
            return

        is_trifle = bool(by_value[answer.value].apply(state))
        if state.game_over:
            return
        actions_remaining -= 1
        if is_trifle and not trifle_bonus_used:
            trifle_bonus_used = True
            actions_remaining += MAX_TRIFLE_BONUS_ACTIONS
