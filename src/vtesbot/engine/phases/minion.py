"""Minion phase: default actions (bleed, hunt) only.

Source: Rulebook SS4 Minion Phase (per the `vtes-rules-reference` skill
condensed mapping): "actions by ready unlocked minions; mandatory actions
first (a ready vampire with no blood must hunt). Each action fully resolves
before the next." "Default actions: bleed (directed, 0 stealth, bleed 1,
one bleed per minion per turn, successful bleed >=1 takes the Edge; ...),
hunt (undirected, +1 stealth, +1 blood)."

CLAUDE.md milestone-2 scope: only bleed and hunt are implemented; all other
minion actions (equip, political action, leave torpor, diablerie, become
Anarch, etc.) are out of scope and are never offered. "One bleed per minion
per turn" is enforced implicitly: acting locks the vampire (Rulebook SS4
step 1), and a locked vampire cannot act again until it next unlocks.

Bleed-amount hook wiring (`engine/hooks.py`, CLAUDE.md milestone-3 scaffolding
pass): once a bleed goes unblocked, the "pay cost, resolve" step (Rulebook
SS4 Minion Phase) is where bleed-amount-modifying cards apply (e.g. Bonding/
Threats/Enchant Kindred add bleed; Telepathic Counter/47th Street Royals
reduce it). This is the general two-sided impulse window (CLAUDE.md rule 4 /
Rulebook SS2 Sequencing), not the block attempt's narrower "only when
needed" ping-pong, so `_perform_bleed` uses `hooks.resolve_impulse_window`
directly. With no providers registered against the `"bleed_amount_modifier"`
hook (no such library cards implemented yet), the window offers nothing and
closes immediately, leaving the bleed at its base amount -- byte-for-byte
the milestone-2 result. A separate, mandatory, non-optional
`"bleed_amount_fixed_modifier"` hook (`hooks.sum_modifiers`) is applied
*before* that window opens, for an unconditional printed bonus such as a
vampire's flat "+1 bleed" ability text (CLAUDE.md rule 3's "mandatory
effects" exception -- not a card the player chooses to play, so it must not
be offered as a declinable choice).
"""

from typing import TYPE_CHECKING

from .. import hooks
from ..action import perform_minion_action
from ..damage import add_blood
from ..decision import Choice, Decision
from ..pool import lose_pool

if TYPE_CHECKING:
    from ..state import GameState, VampireInPlay

BLEED_STEALTH = 0
BLEED_AMOUNT = 1
HUNT_STEALTH = 1
HUNT_BLOOD_GAIN = 1
BLEED_AMOUNT_MODIFIER_HOOK = "bleed_amount_modifier"
BLEED_AMOUNT_FIXED_MODIFIER_HOOK = "bleed_amount_fixed_modifier"
"""Passive, mandatory numeric hook (`hooks.sum_modifiers`, CLAUDE.md rule 3's
"mandatory effects" exception) for an unconditional printed bonus (e.g. a
vampire's flat "+1 bleed" text), applied before the optional
`"bleed_amount_modifier"` impulse window opens, so an always-on bonus is
never mistakenly offered as a player choice with a "decline" option."""


def minion_phase(state: GameState, player: str) -> None:
    other = state.other_player(player)

    # Mandatory actions first: a ready, unlocked vampire with no blood must hunt.
    for vampire in list(state.ready_unlocked_vampires(player)):
        if state.game_over:
            return
        if vampire.blood == 0 and vampire.is_ready_unlocked:
            _perform_hunt(state, player, other, vampire)

    # Optional actions, in whatever order the acting player chooses (impulse).
    while True:
        if state.game_over:
            return
        candidates = state.ready_unlocked_vampires(player)
        if not candidates:
            return
        choices = tuple(
            Choice(f"act_with:{v.instance_id}", f"Act with {v.card.name}") for v in candidates
        ) + (Choice("end_minion_phase", "End minion phase"),)
        decision = Decision(player=player, kind="minion_phase_choice", choices=choices)
        choice = state.ask(decision)
        if choice.value == "end_minion_phase":
            return
        instance_id = choice.value.split(":", 1)[1]
        vampire = state.players[player].vampires[instance_id]
        _choose_and_perform_action(state, player, other, vampire)


def _choose_and_perform_action(
    state: GameState, player: str, other: str, vampire: VampireInPlay
) -> None:
    choices = (Choice("bleed", "Bleed"), Choice("hunt", "Hunt"))
    decision = Decision(
        player=player,
        kind="action_choice",
        choices=choices,
        context={"vampire": vampire.instance_id},
    )
    action = state.ask(decision).value
    if action == "bleed":
        _perform_bleed(state, player, other, vampire)
    else:
        _perform_hunt(state, player, other, vampire)


def _perform_bleed(state: GameState, player: str, other: str, vampire: VampireInPlay) -> None:
    """Rulebook SS4 default bleed action; 2P variant Edge mechanic.

    Directed at the acting Methuselah's prey -- in 2P there is only one
    possible target (the opponent), so no target decision is offered
    (nothing to choose among, Rulebook SS4 "only when needed" principle).
    """

    def resolve() -> None:
        base_amount = BLEED_AMOUNT + hooks.sum_modifiers(
            BLEED_AMOUNT_FIXED_MODIFIER_HOOK, state, player=player, vampire=vampire.instance_id
        )
        amount_box = [base_amount]
        hooks.resolve_impulse_window(
            state,
            BLEED_AMOUNT_MODIFIER_HOOK,
            player,
            other,
            context={"vampire": vampire.instance_id, "amount": amount_box},
        )
        amount = max(0, amount_box[0])
        lose_pool(state, other, amount)
        if amount >= 1:
            state.edge_holder = player

    perform_minion_action(state, player, other, vampire, BLEED_STEALTH, resolve)


def _perform_hunt(state: GameState, player: str, other: str, vampire: VampireInPlay) -> None:
    """Rulebook SS4 default hunt action: undirected, +1 stealth baseline, +1 blood on success."""

    def resolve() -> None:
        add_blood(vampire, HUNT_BLOOD_GAIN)

    perform_minion_action(state, player, other, vampire, HUNT_STEALTH, resolve)
