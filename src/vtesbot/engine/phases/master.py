"""Master phase (Rulebook §4): 1 action by default, trifle grants one
extra (max one/phase); parameterized by `master_phase_play` providers.
Out-of-turn master is out of scope (future hook).

`MASTER_PHASE_ABILITY_HOOK` is a second, independent provider point for a
crypt card's own printed "during your master phase" ability (e.g. Lucinde,
Alastor: "During your master phase, Lucinde can burn 1 blood to choose a
vampire..."). Rulebook §4 Master Phase draws exactly this distinction:
"You may use a master phase action to play a master card, and some cards
can give you alternate ways to use your master phase actions" (that's
`MASTER_PHASE_PLAY_HOOK`'s own "actions" economy) versus "If other effects
happen during your master phase, you choose the order in which these
effects and your master phase actions are performed" -- a printed vampire
ability activating is exactly such an "other effect": distinct from, and
not drawn from, the action count, with the choice of ordering between the
two left to the acting Methuselah. Both hooks are therefore offered every
iteration of the same loop below, merged into one `Decision`, so the
acting Methuselah keeps that same free ordering choice (also Rulebook §2
Sequencing / CLAUDE.md rule 4) -- not a card-text ambiguity needing a
RUL entry, the rulebook settles it directly.
"""

from typing import TYPE_CHECKING

from .. import hooks
from ..decision import Choice, Decision
from ..hooks import Hook

if TYPE_CHECKING:
    from ..state import GameState

MASTER_PHASE_PLAY_HOOK = Hook.MASTER_PHASE_PLAY
MASTER_PHASE_ABILITY_HOOK = Hook.MASTER_PHASE_ABILITY
BASE_MASTER_ACTIONS = 1
MAX_TRIFLE_BONUS_ACTIONS = 1
"""Rulebook §4 Master Phase: trifles grant one extra action, max one per phase."""


def master_phase(state: GameState, player: str) -> None:
    actions_remaining = BASE_MASTER_ACTIONS
    trifle_bonus_used = False

    while not state.game_over:
        play_options = (
            hooks.offer(MASTER_PHASE_PLAY_HOOK, state, player=player)
            if actions_remaining > 0
            else []
        )
        ability_options = hooks.offer(MASTER_PHASE_ABILITY_HOOK, state, player=player)
        if not play_options and not ability_options:
            return  # nothing legal to play or activate: no vacuous decision raised.

        by_value = {o.choice.value: o for o in play_options}
        by_value.update({o.choice.value: o for o in ability_options})
        ability_values = {o.choice.value for o in ability_options}
        choices = (
            tuple(o.choice for o in play_options)
            + tuple(o.choice for o in ability_options)
            + (Choice("pass", "Pass (no master phase action)"),)
        )
        hooks.ensure_unique_choice_values(choices, decision_kind="master_phase_action")
        decision = Decision(
            player=player,
            kind="master_phase_action",
            choices=choices,
            context={"actions_remaining": actions_remaining},
        )
        answer = state.ask(decision)
        if answer.value == "pass":
            return

        result = by_value[answer.value].apply(state)
        if state.game_over:
            return
        if answer.value in ability_values:
            # Crypt-card ability: additional to the action economy
            # (module docstring) -- actions_remaining/trifle untouched.
            continue

        actions_remaining -= 1
        if bool(result) and not trifle_bonus_used:
            trifle_bonus_used = True
            actions_remaining += MAX_TRIFLE_BONUS_ACTIONS
