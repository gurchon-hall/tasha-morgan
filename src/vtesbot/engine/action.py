"""Generic course of a minion-phase action: announce -> block attempt -> resolve.

Source: Rulebook SS4 Minion Phase (per the `vtes-rules-reference` skill
condensed mapping):
  1. "Announce (all terms fixed now ...), lock the acting minion."
  2. "Block attempts: directed action -> only the targeted Methuselah may
     block; undirected -> prey first, then predator. In 2P the opponent is
     both. Block succeeds if intercept >= stealth. Stealth may be added only
     when needed ...; intercept only when needed .... Declining to block is
     final unless the target changes."
  3. "If unblocked -> pay cost, resolve. If blocked -> action card burned,
     cost not paid, blocker locks, combat."

2P structural consequence (CLAUDE.md SS3, settled core structural rule, not
OQ-1 which is scoped to card-text wording): with exactly two Methuselahs,
the sole opponent is simultaneously prey and predator. The rulebook's
"prey first, then predator" sequencing exists to give each of several
*different* Methuselahs a chance to block in turn; when both roles are held
by the same single Methuselah there is only one decision-maker and no new
information arrives between a hypothetical "as prey" and "as predator" ask,
so this implementation collapses both directed and undirected actions to a
single block-attempt decision offered to that one opponent. No stealth or
intercept cards are implemented this milestone, so the "only when needed"
addition windows never have anything legal to add (Rulebook SS4 Minion
Phase): stealth stays at the action's baseline value, intercept stays 0, and
no decision is raised for those steps (nothing legal to offer).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from .combat import run_combat
from .decision import Choice, Decision

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay


def attempt_block(
    state: GameState, actor: str, defender: str, base_stealth: int
) -> VampireInPlay | None:
    """Offer `defender` the chance to block with a ready, unlocked vampire.

    Returns the blocking vampire if a block *succeeds* (intercept >=
    stealth); returns None once the defender declines. Rulebook SS4: "If one
    attempt to block fails, another can be made as often as the blocking
    Methuselah wishes" -- a *failed* attempt (stealth exceeds intercept) does
    not end the block-attempt window and does not lock the failed vampire
    (see OQ-5 on that specific lock-timing reading); the defender is
    re-offered the choice of another candidate vampire or declining, looping
    until they decline or a block succeeds. This is the "three states: no
    current block attempt / ongoing block attempt / blocks declined by all"
    model named by the `vtes-rules-reference` skill.
    """
    while True:
        candidates = state.ready_unlocked_vampires(defender)
        if not candidates:
            return None  # nothing legal to block with: no vacuous decision raised.

        choices = tuple(
            Choice(f"block_with:{v.instance_id}", f"Block with {v.card.name}") for v in candidates
        ) + (Choice("decline", "Decline to block"),)
        decision = Decision(
            player=defender,
            kind="block_attempt",
            choices=choices,
            context={"actor": actor, "base_stealth": base_stealth},
        )
        choice = state.ask(decision)
        if choice.value == "decline":
            return None

        instance_id = choice.value.split(":", 1)[1]
        blocker = state.players[defender].vampires[instance_id]

        # "only when needed" stealth/intercept additions: no stealth/intercept
        # cards are implemented this milestone, so neither can change here.
        stealth = base_stealth
        intercept = 0
        if intercept >= stealth:
            return blocker
        # Failed attempt: does not lock the blocker, does not end the
        # window -- loop back and re-offer another attempt or decline.


def perform_minion_action(
    state: GameState,
    actor_player: str,
    defender_player: str,
    vampire: VampireInPlay,
    base_stealth: int,
    resolve: Callable[[], None],
) -> None:
    """Announce (lock) -> block attempt -> resolve-or-combat (Rulebook SS4).

    `resolve` is called only if the action goes unblocked (declined or
    evaded); it must perform the action's own effect (e.g. bleed/hunt).
    """
    vampire.locked = True
    blocker = attempt_block(state, actor_player, defender_player, base_stealth)
    if blocker is not None:
        blocker.locked = True
        run_combat(state, actor_player, vampire, defender_player, blocker)
        return
    resolve()
