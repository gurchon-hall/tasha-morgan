"""Parity Shift (Political Action). krcg id 101353.

Card text (verbatim, via the installed `krcg` package, 2026-10-11, matching
`data/cards/101353.json`):
    "Requires a prince or justicar.
    Choose a Methuselah who has more pool than you do and allocate 3 of
    their pool among 1 or more other Methuselahs (including you).
    Successful referendum means the pool is distributed as you chose."

Rulings (verbatim, via krcg):
    - "The pool awarded can be used to play {Life Boon} to save the target
      from an oust." [LSJ 20100527]
    - "If the target has less than 3 pool when referendum passes, the
      Methuselah calling the referendum chooses how to distribute within the
      bounds of the terms." [LSJ 20010606]
    - "Changes in pool during the referendum (after terms are chosen) do not
      affect the outcome." [LSJ 20041004]
    - "Cannot be used or played if the conditions for the terms of the
      referendum cannot be met (e.g. no legal selection, insufficient
      cards/players to choose from, prohibited by card text, uniqueness,
      etc)." [LSJ 20100129] [ANK 20191228]

Card type: Political Action (`types == ["Political Action"]`).
`clan_requirement == []`, `discipline_requirement is None`, `cost is None`.
"Requires a prince or justicar" gates *which acting vampire* may play this
card at all (Rulebook SS2 Card Types > "Requirements for Playing Cards"
binds a minion card's requirement to the specific acting minion, the same
reading `engine/phases/minion.py`'s own docstring already settled for
Allies/Action cards, OQ-13) -- checked against `CryptCard.title`, using the
same plain-capitalized-keyword convention `engine/politics.py::TITLE_VOTES`
already relies on (`title in {"Prince", "Justicar"}`).

Status: implemented (OQ-6, `docs/OPEN_QUESTIONS.md`, now resolved).

Engine wiring: mirrors `kine_resources_contested.py`'s own use of
`engine/phases/minion.py::ACTION_CARD_PLAY_HOOK`/`ActionCardSpec` (see that
module's docstring for why this hook, not a new one, is the right engine
entry point for a `"Political Action"`-type card; no engine change needed).
`directed=True` here (unlike Kine Resources Contested): this card's own
text literally names a single target ("Choose a Methuselah who has more
pool than you do"), the Rulebook glossary's "Directed Action" shape
(`engine/action.py`'s own module docstring) -- 2P still structurally
collapses this to the same single-opponent block-attempt call either way,
so the flag changes no mechanics here, only the action's own replay-log
accuracy (same non-mechanical role `enchant_kindred.py`'s basic clause
already documents for its own `directed=True`).

Target selection in 2P ("Choose a Methuselah who has more pool than you
do"): with exactly two Methuselahs, the only *possible* target is the sole
opponent, and only when their pool strictly exceeds the acting player's at
the moment the card would be played (never yourself: "more pool than you
do" is never true of your own pool). Per the ruling "cannot be used or
played if the conditions for the terms of the referendum cannot be met
(e.g. no legal selection ...)", `_provide_parity_shift` simply does not
offer the play when the opponent's pool does not strictly exceed the
acting player's -- no "announce it anyway and let it fizzle" path (matching
`enchant_kindred.py`'s superior clause). Rulebook SS4 "Announce the
Action": "all terms fixed now, except referendum terms" -- the target is
fixed at announce (deterministically the sole opponent), not re-decided
later.

Allocation ("Terms chosen only after success"): "allocate 3 of their [the
target's] pool among 1 or more **other** Methuselahs (including you)" --
"other" is relative to the target, so recipients are drawn from every
Methuselah *except* the target. With exactly two Methuselahs and the
target fixed as the sole opponent, the acting player is the only possible
"other" recipient -- unlike Kine Resources Contested's genuine 3-way split,
this is not a real choice in 2P: 100% of the awarded amount always goes to
the caller. No `Decision` is raised for it (the "never a vacuous Decision"
invariant, `engine/decision.py::Decision.__post_init__`) -- `resolve()`
simply computes the amount and transfers it once the referendum passes.

Amount ("allocate 3 of their pool", ruling "if the target has less than 3
pool when referendum passes, the Methuselah calling the referendum chooses
how to distribute within the bounds of the terms"): `amount = min(3,
target's current pool)`, read at the moment `resolve_referendum` reports a
pass -- with only one possible recipient in 2P, "chooses how to distribute"
has nothing left to choose either. "Changes in pool during the referendum
... do not affect the outcome": this engine resolves the tally and this
card's pass-effect synchronously within one `resolve()` call, so no extra
code is needed. "Successful referendum means the pool is distributed": a
real transfer, not a burn (contrast `kine_resources_contested.py`'s pure
pool-loss) -- `lose_pool` on the target plus `gain_pool` on the caller.
"The pool awarded can be used to play Life Boon to save the target from an
oust": consistent with a genuine `gain_pool`; Life Boon is a separate,
unimplemented card and needs no code here.

`resolve_referendum`'s own `action_pending=pending` argument (OQ-36,
`docs/OPEN_QUESTIONS.md`) is this `resolve()` closure's own `pending`
argument, forwarded through unchanged -- lets `perform_minion_action`
dispatch `REFERENDUM_RESOLVED_HOOK` (Voter Captivation's own trigger
moment) once this whole `resolve()` closure, including the transfer
above, returns. No provider is registered against that hook by this
module (Voter Captivation's own card module is a separate pass).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import ACTION_POLITICAL
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, ActionCardSpec
from vtesbot.engine.politics import POLITICAL_ACTION_STEALTH, resolve_referendum
from vtesbot.engine.pool import gain_pool, lose_pool
from vtesbot.engine.state import GameState

KRCG_ID = 101353
REQUIRED_TITLES = frozenset({"Prince", "Justicar"})
"""Verbatim "Requires a prince or justicar."."""
MAX_ALLOCATION = 3
"""Printed "allocate 3 of their pool ...."."""
CARD_TYPE = "Political Action"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): matches
this module's own "Card type: Political Action" docstring fact above."""


def _provide_parity_shift(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    acting_vampire_id = context["vampire"]
    acting_vampire = state.players[player].vampires.get(acting_vampire_id)
    if acting_vampire is None:
        return []  # `player` is the defender this window, not the acting player.
    if acting_vampire.card.title not in REQUIRED_TITLES:
        return []
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    other = state.other_player(player)
    if state.players[other].pool <= state.players[player].pool:
        # No legal target: "cannot be used or played if the conditions ... cannot be met".
        return []

    def _apply(s: GameState) -> ActionCardSpec:
        play_from_hand(s, player, KRCG_ID)

        def resolve(pending: dict[str, Any]) -> None:
            votes_for, votes_against, _casts = resolve_referendum(
                s, player, other, acting_vampire, action_pending=pending
            )
            if s.game_over or votes_for <= votes_against:
                return  # oust at tally, or fails ("tied referendums fail"): no effect.

            # "1 or more other Methuselahs" excludes the target itself; with
            # only two Methuselahs total, the caller is the only possible
            # recipient, so the whole awarded amount goes to them -- no
            # allocation Decision to raise (module docstring).
            amount = min(MAX_ALLOCATION, s.players[other].pool)
            lose_pool(s, other, amount)
            gain_pool(s, player, amount)

        return ActionCardSpec(
            base_stealth=POLITICAL_ACTION_STEALTH,
            directed=True,
            action=ACTION_POLITICAL,
            resolve=resolve,
        )

    return [
        HookOption(
            choice=Choice("parity_shift:play", "Play Parity Shift"),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


hooks.register(ACTION_CARD_PLAY_HOOK, _provide_parity_shift)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Parity Shift",
        status=Status.IMPLEMENTED,
        hooks=(Hook.ACTION_CARD_PLAY,),
        source=__name__,
    )
)
