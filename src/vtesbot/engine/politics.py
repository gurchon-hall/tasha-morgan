"""Political actions and referenda: announce, block, polling, tally
(Rulebook §4). See OQ-6,20,23,37,42,43,45,49."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import hooks
from .action import ACTION_POLITICAL, attempt_block
from .combat import run_combat
from .decision import Choice, Decision
from .hooks import HookOption
from .pool import lose_pool, max_voluntary_spend

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

POLITICAL_ACTION_STEALTH = 1
"""Rulebook §4 Minion Phase default action list: political action baseline stealth +1."""

POLLING_STEP_HOOK = "polling_step"
"""String value matches `Hook.POLLING_STEP`. Plain string constant since
engine modules never import `cards/registry.py` (CLAUDE.md §5/6)."""

REFERENDUM_TALLIED_HOOK = "referendum_tallied"
"""String value matches `Hook.REFERENDUM_TALLIED`. Fired via `run_effects`
once `resolve_referendum`'s tally is known, before pass/fail effects
(OQ-6)."""

REFERENDUM_RESULT_KEY = "referendum_result"
"""OQ-36: key `resolve_referendum` writes its tally/pass-fail outcome into,
inside `action_pending`. Mirrors (not imports) `action.py::
PENDING_REFERENDUM_RESULT_KEY`."""

VOTE_SOURCE_CAST_BONUS_HOOK = "vote_source_cast_bonus"
"""`sum_modifiers` hook: a bonus added to one specific `VoteSource`'s cast,
dispatched by `_cast_votes` right after cast-time effects, before tally
(OQ-49)."""

VOTE_AGAINST_POOL_COST_HOOK = "vote_against_pool_cost"
"""`sum_modifiers` hook: pool a Methuselah will be forced to lose later for
casting against this referendum; gates the choice only (OQ-43, D-9)."""

POLITICAL_ACTION_CARD_TYPE = "Political Action"
"""`LibraryCard.card_type` value for a political action card, confirmed
against `data/decks/vekn-2p/*.json`; used to find clause 2's
burn-from-hand source."""

TITLE_VOTES: dict[str, int] = {
    "Primogen": 1,
    "Prince": 2,
    "Baron": 2,
    "Justicar": 3,
    "Inner Circle": 4,
    "Bishop": 1,
    "Archbishop": 2,
    "Cardinal": 3,
    "Regent": 4,
}
"""Rulebook §4 Politics > Gaining Votes > Titled Vampires (Camarilla/Anarch
titles) and §6 Vampire Sects (Sabbat titles), verbatim: "During the polling
step of a referendum, a Methuselah gains: 1 vote for each ready bishop, 2
votes for each ready archbishop, 3 votes for each ready cardinal, 4 votes
for the ready regent." Keys match `CryptCard.title`. `Priscus` is
deliberately absent: §6's own "Prisci Block" is a 3-vote group/
sub-referendum mechanism, not a flat per-vampire vote value, and has no
engine mechanism yet (OQ-53, `docs/OPEN_QUESTIONS.md`)."""


@dataclass
class VoteSource:
    """One vote source a Methuselah may cast, as a group, for or against a
    referendum (Rulebook §4). `source_id` lets a hook provider target an
    existing source."""

    source_id: str
    player: str
    votes: int
    label: str
    burns_edge: bool = False
    burns_pac_from_hand: bool = False
    """When cast, burn one Political-Action-type `LibraryCard` from
    `player`'s hand to the ash heap; mirrors `burns_edge`'s cast-time
    mutation."""


def variable_pool_burn_vote_options(
    state: GameState,
    player: str,
    *,
    source_id_prefix: str,
    label: str,
    votes_per_pool: int,
    pending: dict[str, Any],
    on_burn: Callable[[GameState], None] | None = None,
) -> list[HookOption]:
    """Build a `POLLING_STEP_HOOK` option per legal X for a "burn X pool
    for Y*X votes" ability (OQ-23). X=0 never offered; capped at OQ-42."""
    options: list[HookOption] = []
    reserve = pending.get("pool_reserve", {}).get(player, 0)
    for x in range(1, max_voluntary_spend(state, player) - reserve + 1):
        votes = votes_per_pool * x

        def _apply(s: GameState, x: int = x, votes: int = votes) -> None:
            lose_pool(s, player, x)
            if on_burn is not None:
                on_burn(s)
            pending["extra_sources"].append(
                {
                    "source_id": f"{source_id_prefix}:{x}",
                    "player": player,
                    "votes": votes,
                    "label": f"{label} (burn {x} pool for {votes} votes)",
                }
            )

        options.append(
            HookOption(
                choice=Choice(
                    f"{source_id_prefix}:{x}",
                    f"{label}: burn {x} pool for {votes} votes",
                ),
                apply=_apply,
            )
        )
    return options


def political_action(
    state: GameState,
    actor_player: str,
    vampire: VampireInPlay,
) -> bool | None:
    """Announce, block, then combat or referendum (Rulebook §4). Returns
    None if blocked/game-over, else pass/fail. Not a card's entry point
    (OQ-34/36): a real card uses `perform_minion_action` instead."""
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
    if state.game_over:
        return None
    if blocker is not None:
        blocker.locked = True
        run_combat(state, actor_player, vampire, defender_player, blocker)
        return None
    votes_for, votes_against, _casts = resolve_referendum(
        state, actor_player, defender_player, vampire
    )
    if state.game_over:
        return None
    return votes_for > votes_against


def resolve_referendum(
    state: GameState,
    caller_player: str,
    other_player: str,
    caller_vampire: VampireInPlay,
    action_pending: dict[str, Any] | None = None,
    *,
    pool_reserve: Mapping[str, int] | None = None,
    include_caller_card_vote: bool = True,
) -> tuple[int, int, list[tuple[str, str, int, str]]]:
    """Run an unblocked referendum's polling and tally (Rulebook §4 steps
    2-3, OQ-6). `action_pending` (OQ-36) receives the result;
    `pool_reserve` (OQ-42/43/45) protects a mandatory post-tally cost.
    `include_caller_card_vote` (default True, matching every existing call
    site) gates the "+1 vote for casting a political action card" source
    (Rulebook §4 Politics > Gaining Votes > Political Action Cards clause
    1): true for every ordinary referendum, which by construction (this
    engine only ever reaches `resolve_referendum` via a political action
    actually cast) always has a caller who cast one. `False` only for the
    automatic Blood Hunt referendum (`engine/diablerie.py::resolve_diablerie`
    -- see that module's own docstring): nobody cast a political action
    card to trigger it, so granting that vote regardless would be a free,
    unearned vote for whichever side is passed as `caller_player`."""
    pending: dict[str, Any] = {
        "extra_sources": [],
        "forced_abstain": set(),
        "pool_reserve": dict(pool_reserve or {}),
    }
    _run_pre_cast_hook_window(state, caller_player, other_player, caller_vampire, pending)
    if state.game_over:
        return 0, 0, []
    sources = _collect_vote_sources(
        state,
        caller_player,
        other_player,
        pending,
        include_caller_card_vote=include_caller_card_vote,
    )
    votes_for, votes_against, casts = _cast_votes(
        state,
        caller_player,
        other_player,
        caller_vampire.instance_id,
        sources,
        pending,
        caller_vampire,
    )
    if state.game_over:
        return votes_for, votes_against, casts
    _dispatch_referendum_tallied(
        state, caller_player, other_player, caller_vampire, votes_for, votes_against, casts
    )
    if action_pending is not None:
        action_pending[REFERENDUM_RESULT_KEY] = {
            "votes_for": votes_for,
            "votes_against": votes_against,
            "passed": votes_for > votes_against,
        }
    return votes_for, votes_against, casts


def _run_pre_cast_hook_window(
    state: GameState,
    caller_player: str,
    other_player: str,
    caller_vampire: VampireInPlay,
    pending: dict[str, Any],
) -> None:
    """Rulebook §4 step 2: cards usable before casting, as a two-sided
    impulse window. Context ids are plain `str`, never the live object
    (CLAUDE.md "information hiding")."""
    hooks.resolve_impulse_window(
        state,
        POLLING_STEP_HOOK,
        caller_player,
        other_player,
        context={
            "caller": caller_player,
            "caller_vampire_id": caller_vampire.instance_id,
            "phase": "before_cast",
            "pending": pending,
        },
    )


def _dispatch_referendum_tallied(
    state: GameState,
    caller_player: str,
    other_player: str,
    caller_vampire: VampireInPlay,
    votes_for: int,
    votes_against: int,
    casts: list[tuple[str, str, int, str]],
) -> None:
    """Rulebook §4 step 3: mandatory, non-chosen per-provider reaction
    fired once results are tallied, before pass/fail effects
    (`run_effects`, no `Decision`). No provider registered: a no-op."""
    hooks.run_effects(
        REFERENDUM_TALLIED_HOOK,
        state,
        caller=caller_player,
        other=other_player,
        caller_vampire=caller_vampire,
        votes_for=votes_for,
        votes_against=votes_against,
        casts=casts,
    )


def _collect_vote_sources(
    state: GameState,
    caller_player: str,
    other_player: str,
    pending: dict[str, Any],
    *,
    include_caller_card_vote: bool = True,
) -> list[VoteSource]:
    """Enumerate every vote source either Methuselah may cast this polling
    step (Rulebook §4), minus any `pending["forced_abstain"]` source
    ids.

    The "burn a political action card from hand" source (clause 2 of
    Gaining Votes > Political Action Cards) is normally offered only to
    `other_player`: `caller_player` already claimed their one-per-
    Methuselah political-action-card vote via the "cast" source (clause
    1) below, and "[e]ach Methuselah can gain no more than 1 vote from
    political action cards" forbids a second. When
    `include_caller_card_vote` is False (the automatic Blood Hunt
    referendum, `engine/diablerie.py`: nobody cast anything, so neither
    side has claimed that one-per-Methuselah allotment yet), `caller_player`
    becomes eligible for the from-hand source too -- the two players are
    then fully symmetric vote sources, and which one is passed as
    `caller_player` makes no difference to actual voting rights."""
    forced_abstain: set[str] = pending.get("forced_abstain", set())
    sources: list[VoteSource] = []
    pac_source_id = f"political_action_card:{caller_player}"
    if include_caller_card_vote and pac_source_id not in forced_abstain:
        sources.append(
            VoteSource(
                source_id=pac_source_id,
                player=caller_player,
                votes=1,
                label="Political action card",
            )
        )
    pac_hand_eligible_players = (
        (other_player,) if include_caller_card_vote else (caller_player, other_player)
    )
    for hand_player in pac_hand_eligible_players:
        pac_hand_source_id = f"political_action_card_hand:{hand_player}"
        if pac_hand_source_id not in forced_abstain and _has_political_action_card_in_hand(
            state, hand_player
        ):
            sources.append(
                VoteSource(
                    source_id=pac_hand_source_id,
                    player=hand_player,
                    votes=1,
                    label="Burn a political action card from hand",
                    burns_pac_from_hand=True,
                )
            )
    for player in (caller_player, other_player):
        for vampire in state.players[player].vampires.values():
            if vampire.zone != "ready":
                continue  # torpor "must abstain" (module docstring); locked is irrelevant.
            title = vampire.card.title
            if title not in TITLE_VOTES:
                continue
            source_id = f"title:{vampire.instance_id}"
            if source_id in forced_abstain:
                continue
            sources.append(
                VoteSource(
                    source_id=source_id,
                    player=player,
                    votes=TITLE_VOTES[title],
                    label=f"{vampire.card.name} ({title})",
                )
            )
    if state.edge_holder is not None:
        source_id = f"edge:{state.edge_holder}"
        if source_id not in forced_abstain:
            sources.append(
                VoteSource(
                    source_id=source_id,
                    player=state.edge_holder,
                    votes=1,
                    label="Burn the Edge",
                    burns_edge=True,
                )
            )
    for extra in pending.get("extra_sources", ()):
        source_id = extra["source_id"]
        if source_id in forced_abstain:
            continue
        sources.append(
            VoteSource(
                source_id=source_id,
                player=extra["player"],
                votes=extra["votes"],
                label=extra["label"],
            )
        )
    return sources


def _has_political_action_card_in_hand(state: GameState, player: str) -> bool:
    """Clause 2 gate: does `player` hold at least one Political-Action-type
    card in hand? Which specific card is irrelevant; only presence
    matters."""
    return any(card.card_type == POLITICAL_ACTION_CARD_TYPE for card in state.players[player].hand)


def _burn_one_political_action_card_from_hand(state: GameState, player: str) -> None:
    """Cast-time effect of a `burns_pac_from_hand` source: move one
    Political-Action card from hand to the ash heap (first match)."""
    hand = state.players[player].hand
    for index, card in enumerate(hand):
        if card.card_type == POLITICAL_ACTION_CARD_TYPE:
            state.players[player].ash_heap.append(hand.pop(index))
            return
    raise AssertionError(
        f"{player} has no political action card left in hand to burn for a vote "
        "(engine invariant violation, not a legal game state)"
    )


def _cast_votes(
    state: GameState,
    caller_player: str,
    other_player: str,
    caller_vampire_id: str,
    sources: list[VoteSource],
    pending: dict[str, Any],
    caller_vampire: VampireInPlay | None = None,
) -> tuple[int, int, list[tuple[str, str, int, str]]]:
    """Rulebook §4 steps 2-3 (OQ-6/20/37/49): strict two-player
    alternation, caller first, closing on a full idle lap. Also offers
    mid-cast cancellation (OQ-37) and sums the cast bonus hook (OQ-49)."""
    votes_for = 0
    votes_against = 0
    casts: list[tuple[str, str, int, str]] = []

    remaining = {source.source_id: source for source in sources}
    turn = caller_player
    consecutive_passes = 0
    while consecutive_passes < 2 and not state.game_over:
        mine = sorted(
            (source for source in remaining.values() if source.player == turn),
            key=lambda source: source.source_id,
        )
        cancel_options = hooks.offer(
            POLLING_STEP_HOOK,
            state,
            player=turn,
            phase="mid_cast",
            caller=caller_player,
            caller_vampire_id=caller_vampire_id,
            other=other_player,
            votes_for=votes_for,
            votes_against=votes_against,
            casts=list(casts),
            pending=pending,
        )
        if not mine and not cancel_options:
            consecutive_passes += 1
        else:
            cancel_by_value = {o.choice.value: o for o in cancel_options}
            choices: tuple[Choice, ...] = ()
            against_cost = hooks.sum_modifiers(
                VOTE_AGAINST_POOL_COST_HOOK,
                state,
                player=turn,
                caller_vampire=caller_vampire,
                casts=casts,
            )
            can_cast_against = against_cost <= (
                max_voluntary_spend(state, turn) - pending.get("pool_reserve", {}).get(turn, 0)
            )
            for source in mine:
                choices += (
                    Choice(
                        f"for:{source.source_id}",
                        f"Cast {source.votes} vote(s) for ({source.label})",
                    ),
                )
                if can_cast_against:
                    choices += (
                        Choice(
                            f"against:{source.source_id}",
                            f"Cast {source.votes} vote(s) against ({source.label})",
                        ),
                    )
            choices += tuple(o.choice for o in cancel_options)
            choices += (Choice("pass", "Pass (hold back remaining votes for now)"),)
            hooks.ensure_unique_choice_values(choices, decision_kind="polling_step_cast")
            decision = Decision(
                player=turn,
                kind="polling_step_cast",
                choices=choices,
                context={
                    "caller": caller_player,
                    "votes_for": votes_for,
                    "votes_against": votes_against,
                },
            )
            answer = state.ask(decision).value
            if answer == "pass":
                consecutive_passes += 1
            elif answer in cancel_by_value:
                consecutive_passes = 0
                canceled_source_id = cancel_by_value[answer].apply(state)
                votes_for, votes_against = _apply_retroactive_vote_cancellation(
                    canceled_source_id, remaining, casts, votes_for, votes_against
                )
            else:
                consecutive_passes = 0
                direction, source_id = answer.split(":", 1)
                source = remaining.pop(source_id)
                if source.burns_edge:
                    state.edge_holder = None
                if source.burns_pac_from_hand:
                    _burn_one_political_action_card_from_hand(state, source.player)
                cast_votes = source.votes + hooks.sum_modifiers(
                    VOTE_SOURCE_CAST_BONUS_HOOK,
                    state,
                    caster=source.player,
                    burns_edge=source.burns_edge,
                    burns_pac_from_hand=source.burns_pac_from_hand,
                    direction=direction,
                )
                if direction == "for":
                    votes_for += cast_votes
                else:
                    votes_against += cast_votes
                casts.append((source.player, source.source_id, cast_votes, direction))
        turn = other_player if turn == caller_player else caller_player
    return votes_for, votes_against, casts


def _apply_retroactive_vote_cancellation(
    source_id: str,
    remaining: dict[str, VoteSource],
    casts: list[tuple[str, str, int, str]],
    votes_for: int,
    votes_against: int,
) -> tuple[int, int]:
    """OQ-37: generic half of a mid-cast `POLLING_STEP_HOOK` cancellation
    -- removes the source from `remaining`/`casts` and reverses its vote
    tally."""
    remaining.pop(source_id, None)
    for index, (_player, cast_source_id, votes, direction) in enumerate(casts):
        if cast_source_id == source_id:
            del casts[index]
            if direction == "for":
                votes_for -= votes
            else:
                votes_against -= votes
            break
    return votes_for, votes_against
