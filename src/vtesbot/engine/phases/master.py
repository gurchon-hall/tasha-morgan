"""Master phase.

Source: Rulebook SS4 Master Phase (per the `vtes-rules-reference` skill
condensed mapping): "1 master phase action by default; trifles grant one
extra (max one per phase); an out-of-turn master played earlier removes
one; unused actions are lost."

CLAUDE.md milestone-3 scaffolding pass: no master *card* is implemented yet
(that is `card-implementer`'s next pass), but the phase itself now has the
real decision-offering structure the rule describes, parameterized entirely
by what `src/vtesbot/cards/` registers against the `"master_phase_play"`
hook (`engine/hooks.py`) -- CLAUDE.md SS6 "Card hooks: the engine exposes
hooks/events; card-specific behaviour lives in `src/vtesbot/cards/`. Do not
special-case card names in the engine." With no providers registered, every
call to `hooks.offer("master_phase_play", ...)` returns an empty list, so no
decision is ever raised (the project's "only when needed" / "never a
vacuous Decision" invariant) and `master_phase` behaves exactly as the
milestone-2 no-op it replaces.

A provider's `HookOption.apply(state)` must return a `bool`: `True` if the
card played is a trifle (Rulebook SS4: "trifles grant one extra [master
phase action] (max one per phase)"), `False` otherwise. "An out-of-turn
master played earlier removes one" (i.e. a master-phase action played as an
out-of-turn master card during a *previous* phase/turn) is out of scope for
this pass -- no out-of-turn master mechanism exists yet; this is noted as a
future hook point (`"out_of_turn_master_play"`) rather than guessed at here.
"""

from typing import TYPE_CHECKING

from .. import hooks
from ..decision import Choice, Decision

if TYPE_CHECKING:
    from ..state import GameState

MASTER_PHASE_PLAY_HOOK = "master_phase_play"
BASE_MASTER_ACTIONS = 1
MAX_TRIFLE_BONUS_ACTIONS = 1
"""Rulebook SS4 Master Phase: trifles grant one extra action, max one per phase."""


def master_phase(state: GameState, player: str) -> None:
    actions_remaining = BASE_MASTER_ACTIONS
    trifle_bonus_used = False

    while actions_remaining > 0:
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
        actions_remaining -= 1
        if is_trifle and not trifle_bonus_used:
            trifle_bonus_used = True
            actions_remaining += MAX_TRIFLE_BONUS_ACTIONS
