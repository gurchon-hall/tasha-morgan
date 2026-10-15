"""Kine Resources Contested (Political Action). krcg id 101056.

Card text (verbatim, via the installed `krcg` package, 2026-10-11, matching
`data/cards/101056.json`):
    "Allocate 4 points among two or more Methuselahs. Successful referendum
    means each Methuselah burns 1 pool for each point allocated."

Rulings (verbatim, via krcg):
    - "Cannot allocate 4 points to a single Methuselah, but you can allocate
      points to yourself." [LSJ 20000622]
    - "If multiple ousts happen, players whose prey gets ousted get a
      victory point, even if they are being ousted themselves. Only the
      surviving ones get 6 pool from the oust of their prey (not of their
      grand-prey)." [LSJ 20000309]
    - "Can allocate more points than a Methuselah has pool." [LSJ 20020819]

Card type: Political Action (`types == ["Political Action"]`). No clan,
discipline or title requirement (`clan_requirement == []`,
`discipline_requirement is None`); `cost is None`.

Status: implemented (OQ-6, `docs/OPEN_QUESTIONS.md`, now resolved by
`engine/politics.py::resolve_referendum`).

Engine wiring: a political action card is the acting vampire's entire
minion action for the turn, exactly like an "Action"-type card -- the same
shape `engine/phases/minion.py::ACTION_CARD_PLAY_HOOK`/`ActionCardSpec`
already generalizes (see `enchant_kindred.py`, an "Action"-type card, for
the identical pattern this module mirrors). The hook's own mechanism is
card-type-agnostic (a provider decides which card(s) it looks for by
`krcg_id`; nothing in the engine filters by printed `types`), so no new
hook or engine change is needed -- this is the first registration against
it for a `"Political Action"`-type card, not a repurposing of anything.
`_provide_kine_resources_contested`'s `apply()` plays the card immediately
(`_shared.play_from_hand`, straight to the ash heap) since -- whether the
action ends up blocked (burned) or the referendum passes or fails -- a
political action card has no other printed destination either way (mirrors
`enchant_kindred.py`'s one-shot immediate-consumption cards, not Recruit
Ally's two-destination dance). `ActionCardSpec.action=ACTION_POLITICAL`,
`directed=False` (Rulebook §4 Minion Phase default action list: "political
action (undirected, +1 stealth ...)"; this card's own text names no single
target Methuselah up front, unlike Parity Shift's "Choose a Methuselah who
has more pool than you do").

`resolve()` only fires once `perform_minion_action`'s own block-attempt
phase (run with `action=ACTION_POLITICAL`, `base_stealth=
POLITICAL_ACTION_STEALTH`) has already gone unblocked -- so it must only
run the *referendum itself* (`engine/politics.py::resolve_referendum`'s
polling step + tally, Rulebook §4 "The Referendum" steps 2-3), not
re-announce or re-attempt a block: `engine/politics.py::political_action`
(which duplicates the announce/block/combat steps `perform_minion_action`
already ran) is deliberately *not* called here, to avoid running the
block-attempt phase twice. If the referendum fails (`votes_for <=
votes_against`, "tied referendums fail" per `resolve_referendum`'s own
contract), there is no effect at all -- Rulebook §4 "Resolve the
Referendum": "Otherwise, the referendum fails and has no effect."

Allocation: the split is the referendum's own term. Rulebook §4 "The
Referendum" step 1 "Choose the terms" precedes step 2 "Polling", and terms
are chosen only once the action succeeds (§4 "The Political Action"), so
`resolve()` raises the `"kine_resources_contested_allocation"` decision
first and locks it. User ruling 2026-10-13 (OQ-45, `docs/DECISIONS.md`
D-9): "la répartition est verrouillée avant le vote puis fenetre d'avant
votes [...] puis le vote a lieu puis fenetre de fin de tally [...] puis
résolution des effets du vote puis fenetre d'action modifier de fin
d'action". The locked self share is passed as `pool_reserve`, so the
vote-time pool gates keep it payable and the resolution cannot dead-end.

Legal splits in 2P (derived directly from the card's own text): "Allocate
4 points **among two or more Methuselahs**" requires at least two distinct
recipients to each receive a *nonzero* share (0 points is not "among" the
allocation at all). With exactly two Methuselahs in a 2P duel, "two or
more" can only mean "both of them", so each player must receive >=1 of the
4 points -- independently entailing the ruling's "cannot allocate 4 points
to a single Methuselah". The legal splits are therefore exactly `(1, 3)`,
`(2, 2)`, `(3, 1)` (self points, other points) -- never `(4, 0)` or
`(0, 4)`. The ruling's other clause, "but you can allocate points to
yourself", is not a separate restriction to enforce: `(1, 3)`/`(2, 2)`/
`(3, 1)` all do so by construction.

"Successful referendum means each Methuselah burns 1 pool for each point
allocated": a pure loss, not a transfer (contrast `parity_shift.py`, whose
own text has the target's pool "distributed" to a recipient, i.e. actually
awarded) -- both players' shares are applied as one event via
`engine.pool.lose_pool_simultaneously` (OQ-44), never `gain_pool`.
"Can allocate more points than a Methuselah has pool" needs no extra
code: `lose_pool` already floors the loss at the
player's current pool and still checks ousting (`engine/pool.py`), so
over-allocating simply drives that player to 0 pool and triggers the
ordinary oust path.

"If multiple ousts happen, players whose prey gets ousted get a victory
point ...": a multiplayer-only scenario (it presupposes at least a third
Methuselah whose own prey is distinct from this card's caller/target) --
structurally impossible in a 2-player duel, where `engine/ousting.py`
already documents that there is only ever one oust event, which ends the
game immediately (not a gap this card needs to fill, and not an Open
Question -- the engine's existing 2P oust model already fully covers the
only case that can actually arise here).

`resolve_referendum`'s own `action_pending=pending` argument (OQ-36,
`docs/OPEN_QUESTIONS.md`) is this `resolve()` closure's own `pending`
argument, forwarded through unchanged -- lets `perform_minion_action`
dispatch `REFERENDUM_RESOLVED_HOOK` (Voter Captivation's own trigger
moment) once this whole `resolve()` closure, including the allocation
above, returns. No provider is registered against that hook by this
module (Voter Captivation's own card module is a separate pass).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import ACTION_POLITICAL
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.errors import UnresolvedRulingError
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import ACTION_CARD_PLAY_HOOK, ActionCardSpec
from vtesbot.engine.politics import POLITICAL_ACTION_STEALTH, resolve_referendum
from vtesbot.engine.pool import lose_pool_simultaneously, max_voluntary_spend
from vtesbot.engine.state import GameState

KRCG_ID = 101056
TOTAL_POINTS = 4
"""Printed "Allocate 4 points ..."."""
CARD_TYPE = "Political Action"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): matches
this module's own "Card type: Political Action" docstring fact above."""


def _legal_self_points(state: GameState, player: str) -> range:
    """OQ-42 (user ruling, `docs/DECISIONS.md` D-9): the caller picks the
    split, so their own share may not zero their pool. The opponent's share
    is unrestricted (an opponent oust by the card is a normal oust)."""
    return range(1, min(TOTAL_POINTS, max_voluntary_spend(state, player) + 1))


def _provide_kine_resources_contested(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    player = context["player"]
    acting_vampire_id = context["vampire"]
    acting_vampire = state.players[player].vampires.get(acting_vampire_id)
    if acting_vampire is None:
        return []  # `player` is the defender this window, not the acting player.
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    if not _legal_self_points(state, player):
        return []
    other = state.other_player(player)

    def _apply(s: GameState) -> ActionCardSpec:
        play_from_hand(s, player, KRCG_ID)

        def resolve(pending: dict[str, Any]) -> None:
            choices = tuple(
                Choice(
                    f"allocate:{self_points}",
                    f"Allocate {self_points} point(s) to yourself, "
                    f"{TOTAL_POINTS - self_points} to your opponent "
                    "(each point burns 1 pool)",
                )
                for self_points in _legal_self_points(s, player)
            )
            if not choices:
                raise UnresolvedRulingError(
                    "Kine Resources Contested: no affordable self share when the terms "
                    "are chosen (pool dropped between announce and success)"
                )
            decision = Decision(
                player=player,
                kind="kine_resources_contested_allocation",
                choices=choices,
                context={"caller": player, "other": other},
            )
            self_points = int(s.ask_unless_forced(decision).value.split(":", 1)[1])
            other_points = TOTAL_POINTS - self_points

            # The locked self share is reserved so no vote-time cost (Marcos
            # tally burn, Oxford burn) can leave it unpayable at resolution.
            votes_for, votes_against, _casts = resolve_referendum(
                s,
                player,
                other,
                acting_vampire,
                action_pending=pending,
                pool_reserve={player: self_points},
            )
            if s.game_over or votes_for <= votes_against:
                return  # oust at tally, or fails ("tied referendums fail"): no effect.
            lose_pool_simultaneously(s, {player: self_points, other: other_points})

        return ActionCardSpec(
            base_stealth=POLITICAL_ACTION_STEALTH,
            directed=False,
            action=ACTION_POLITICAL,
            resolve=resolve,
        )

    return [
        HookOption(
            choice=Choice("kine_resources_contested:play", "Play Kine Resources Contested"),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


hooks.register(ACTION_CARD_PLAY_HOOK, _provide_kine_resources_contested)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Kine Resources Contested",
        status=Status.IMPLEMENTED,
        hooks=(Hook.ACTION_CARD_PLAY,),
        source=__name__,
    )
)
