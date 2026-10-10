"""Political actions and referenda: announce/block scaffolding only.

Source: Rulebook SS4 Minion Phase (per the `vtes-rules-reference` skill
condensed mapping): political action is one of the default minion actions --
"political action (undirected, +1 stealth, one per vampire per turn)" -- so
it follows the same generic "announce -> block attempt -> resolve" course as
any other action (Rulebook SS4 Minion Phase, see `engine/action.py`):
announcing locks the acting vampire, the opponent gets a block attempt
(undirected: in 2P, the sole opponent, as both prey and predator -- CLAUDE.md
SS3 / `engine/action.py` module docstring), and if blocked, combat happens
and the referendum never occurs at all ("the action card is burned ... the
effects of the action do not take place", per OQ-5's verbatim rulebook
quote). `political_action` below implements exactly that much and nothing
more.

Politics (SS4) also names what happens *after* an unblocked political action
-- "Terms chosen only after success. Votes: 1 from a political action card
(max 1 per Methuselah), titles (primogen 1, prince/baron 2, justicar 3,
Inner Circle 4; Sabbat and other sects per SS6-7), burning the Edge = 1. Only
ready minions vote. Ties fail." -- but this condensed mapping does not state
what a referendum's votes are compared *against* to decide pass/fail (there
is no explicit "for/against" split named anywhere in the mapping), nor how
"ties fail" applies when there are only ever two Methuselahs who could ever
cast a vote (the 4-5 player design assumes several independent voters; card
rulings fetched for this pool's own political-action cards additionally
reference a distinct "a referendum that is automatically passing" state --
e.g. Perfect Paragon/Scalpel Tongue "[c]annot be used during a referendum
that is automatically passing" [PIB 20150105] [LSJ 19980107] -- that is not
explained by the mapping at all). This is not settled by the sources
available to this pass (see `docs/OPEN_QUESTIONS.md` OQ-6): resolving a
referendum's poll therefore raises `UnresolvedRulingError("OQ-6", ...)`
rather than guessing a pass/fail rule. Nothing calls `political_action` yet
(no political-action card is implemented this pass); this module exists so
that implementing one of this pool's three Political Action cards (Disputed
Territory, Kine Resources Contested, Parity Shift) only requires writing
`src/vtesbot/cards/<card>.py` plus resolving OQ-6, never touching
`engine/action.py` or `engine/combat.py` again for the announce/block part.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

from .action import ACTION_POLITICAL, attempt_block
from .combat import run_combat
from .errors import UnresolvedRulingError

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

POLITICAL_ACTION_STEALTH = 1
"""Rulebook SS4 Minion Phase default action list: political action baseline stealth +1."""


def political_action(
    state: GameState,
    actor_player: str,
    vampire: VampireInPlay,
) -> None:
    """Announce (lock) -> block attempt -> (blocked: combat) | (unblocked: referendum).

    Raises `UnresolvedRulingError("OQ-6")` once a political action goes
    unblocked, since resolving the referendum (polling step, vote tally,
    pass/fail) is not settled by the available sources (see module
    docstring). The announce/block/combat path above *is* fully sourced and
    tested (`tests/rules/test_politics.py`), so this is a real, usable hook
    for `card-implementer`, not a bare stub.
    """
    defender_player = state.other_player(actor_player)
    vampire.locked = True
    blocker = attempt_block(
        state,
        actor_player,
        defender_player,
        POLITICAL_ACTION_STEALTH,
        vampire,
        action=ACTION_POLITICAL,
    )
    if blocker is not None:
        blocker.locked = True
        run_combat(state, actor_player, vampire, defender_player, blocker)
        return
    raise UnresolvedRulingError(
        "OQ-6",
        "referendum polling-step/vote-tally/pass-fail procedure for exactly "
        "two Methuselahs is not settled by the available sources",
    )


PollingHook = Callable[["GameState", str], None]
"""Reserved name for a future `resolve_referendum` hook (OQ-6), so a future
card-implementer pass has a documented name to extend, instead of inventing
an ad hoc signature once OQ-6 is resolved."""
