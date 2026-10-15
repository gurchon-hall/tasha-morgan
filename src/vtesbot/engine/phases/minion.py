"""Minion phase: default actions (bleed, hunt, recruit ally, action cards),
Rulebook §4. Mandatory hunt first; lock enforces one action per vampire
per turn. See OQ-9/11/12/17/21/25 below.

`build_enter_combat_action_spec`/`EnterCombatGrant`/
`grant_enter_combat_this_turn`/`active_enter_combat_grants` generalize
`cards/line_brawl.py`'s own `[pot]` "Enter combat with a minion" clause
into a reusable primitive: an `ACTION_CARD_PLAY_HOOK` option offering to
enter combat with an already-bound target, whether the option comes from
playing a card or from a crypt text's own printed ability grant (e.g. a
future Lucinde, Alastor module). Proven generically by this module's own
docstrings plus `tests/rules/test_enter_combat_grant.py`, mirroring how
`engine/combat.py::commit_strike_for_round` was proven before `cards/
slam.py` became its first production user.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .. import hooks
from ..action import (
    ACTION_ACTION_CARD,
    ACTION_BLEED,
    ACTION_HUNT,
    ACTION_RECRUIT_ALLY,
    perform_minion_action,
)
from ..allies import detect_contest_on_recruit, recruit_ally
from ..combat import run_combat
from ..damage import add_blood
from ..decision import Choice, Decision
from ..pool import lose_pool
from ..state import EnterCombatGrant

if TYPE_CHECKING:
    from ..allies import RecruitAllySpec
    from ..hooks import HookOption
    from ..state import GameState, VampireInPlay

BLEED_STEALTH = 0
BLEED_AMOUNT = 1
HUNT_STEALTH = 1
HUNT_BLOOD_GAIN = 1
RECRUIT_ALLY_STEALTH = 1
"""Rulebook §4 Recruit Ally: "Default stealth: +1 stealth." """
RECRUIT_ALLY_PLAY_HOOK = "recruit_ally_play"
"""`HookOption` hook (mirrors `master.py`'s `master_phase_play`): offers one
option per playable Ally card in hand; `apply(state)` returns a
`RecruitAllySpec` (OQ-12)."""
ACTION_CARD_PLAY_HOOK = "action_card_play"
"""`HookOption` hook (OQ-17): generalizes `RECRUIT_ALLY_PLAY_HOOK` to
Action-type library cards; offers one option per playable Action card in
hand; `apply(state)` returns an `ActionCardSpec` below."""
BLEED_AMOUNT_MODIFIER_HOOK = "bleed_amount_modifier"
BLEED_AMOUNT_FIXED_MODIFIER_HOOK = "bleed_amount_fixed_modifier"
"""Mandatory numeric hook (`hooks.sum_modifiers`, CLAUDE.md rule 3) for an
unconditional printed bleed bonus, applied before the optional
`bleed_amount_modifier` window opens."""
PENDING_BLEED_AMOUNT_KEY = "bleed_amount_bonus"
"""Scratch-dict key (OQ-11): an earlier stealth/intercept provider in this
same bleed action stores a running bonus here; `_perform_bleed`'s `resolve`
folds it into `base_amount`."""


@dataclass(frozen=True)
class ActionCardSpec:
    """What an `action_card_play` hook option's `apply(state)` returns
    (OQ-17): base_stealth/directed, `resolve`/`on_blocked` callbacks,
    `action` discriminator (OQ-9), `maneuver_grant` (OQ-25)."""

    base_stealth: int
    directed: bool
    resolve: Callable[[dict[str, Any]], None]
    on_blocked: Callable[[dict[str, Any]], None] | None = None
    action: str = ACTION_ACTION_CARD
    maneuver_grant: str | None = None


def build_enter_combat_action_spec(
    state: GameState,
    player: str,
    acting_vampire: VampireInPlay,
    opponent: str,
    target_vampire_id: str,
) -> ActionCardSpec:
    """Shared "Ⓓ Enter combat with a minion" resolution shape: the target is
    bound now (at `apply()` time, not deferred to `resolve()`), and
    `run_combat` runs against it only if the action goes unblocked -- see
    `cards/line_brawl.py`'s own `[pot]` clause docstring (OQ-21, resolved)
    for the full reasoning, worked out there first. `resolve()` treats a
    target that has left `zone == "ready"` between binding and resolve as
    "nothing to do" (fizzles), the same convention OQ-21 settled.

    Reused by any `ACTION_CARD_PLAY_HOOK` provider offering an equivalent
    "enter combat with this specific, already-bound target" option,
    regardless of what makes the option available: playing a card
    (`cards/line_brawl.py`'s `[pot]` clause, its first consumer, refactored
    onto this shared helper) or a crypt text's own ability grant
    (`EnterCombatGrant`/`active_enter_combat_grants` below, e.g. a future
    Lucinde, Alastor module). Callers remain responsible for their own
    eligibility gate on which vampire may use the option at all (mirrors
    `line_brawl.py`'s "Requires an Anarch" gate) -- this helper only builds
    the `ActionCardSpec` for a target already decided to be legal."""

    def resolve(pending: dict[str, Any]) -> None:
        del pending  # no later hook window of its own to feed.
        target = state.players[opponent].vampires.get(target_vampire_id)
        if target is None or target.zone != "ready":
            return  # fizzles (OQ-21); the target left "ready" since binding.
        run_combat(state, player, acting_vampire, opponent, target)

    return ActionCardSpec(base_stealth=0, directed=True, resolve=resolve)


def grant_enter_combat_this_turn(
    state: GameState, player: str, *, target_player: str, target_vampire_id: str
) -> EnterCombatGrant:
    """Record a new `EnterCombatGrant` for `player`, naming
    `target_vampire_id` (controlled by `target_player`) as the fixed
    target, timestamped with the current turn (Rulebook §4 Master Phase: a
    crypt card's own printed master-phase ability is additional to, not
    drawn from, the action economy -- CLAUDE.md task framing; not itself a
    card play, so no `played_card_type`/cost bookkeeping is owned here,
    only by the caller). Does not itself check who may use the grant."""
    grant = EnterCombatGrant(
        target_player=target_player,
        target_vampire_id=target_vampire_id,
        granted_turn=state.turn_number,
    )
    state.players[player].enter_combat_grants.append(grant)
    return grant


def active_enter_combat_grants(state: GameState, player: str) -> list[EnterCombatGrant]:
    """Every `EnterCombatGrant` made to `player` on the current turn
    (`GameState.turn_number`) -- see `EnterCombatGrant`'s own docstring for
    why no explicit end-of-turn clearing is needed. A provider consuming
    this must itself check, at offer time, whether `target_vampire_id` is
    still `zone == "ready"` before building an option for it (mirrors
    `cards/line_brawl.py`'s own `_eligible_combat_targets` guard: never
    offer a play that cannot resolve); `build_enter_combat_action_spec`'s
    own `resolve()` fizzle check is a safety net for the gap between offer
    and resolve, not a substitute for that gate."""
    return [
        grant
        for grant in state.players[player].enter_combat_grants
        if grant.granted_turn == state.turn_number
    ]


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
    """Rulebook §4: offers default actions plus one choice per
    `recruit_ally_play` (OQ-12)/`action_card_play` (OQ-17) option; degrades
    to bleed/hunt alone when none offered (OQ-13 context)."""
    recruit_options = hooks.offer(
        RECRUIT_ALLY_PLAY_HOOK, state, player=player, vampire=vampire.instance_id
    )
    action_card_options = hooks.offer(
        ACTION_CARD_PLAY_HOOK, state, player=player, vampire=vampire.instance_id
    )
    recruit_by_value: dict[str, HookOption] = {o.choice.value: o for o in recruit_options}
    action_card_by_value: dict[str, HookOption] = {o.choice.value: o for o in action_card_options}
    choices = (
        (Choice(ACTION_BLEED, "Bleed"), Choice(ACTION_HUNT, "Hunt"))
        + tuple(o.choice for o in recruit_options)
        + tuple(o.choice for o in action_card_options)
    )
    decision = Decision(
        player=player,
        kind="action_choice",
        choices=choices,
        context={"vampire": vampire.instance_id},
    )
    action = state.ask(decision).value
    if action == ACTION_BLEED:
        _perform_bleed(state, player, other, vampire)
    elif action == ACTION_HUNT:
        _perform_hunt(state, player, other, vampire)
    elif action in recruit_by_value:
        _perform_recruit_ally(state, player, other, vampire, recruit_by_value[action])
    else:
        _perform_action_card(state, player, other, vampire, action_card_by_value[action])


def _perform_bleed(state: GameState, player: str, other: str, vampire: VampireInPlay) -> None:
    """Rulebook §4 default bleed; 2P Edge mechanic. Directed at prey; in 2P
    only one target exists so no target decision is offered."""

    def resolve(pending: dict[str, Any]) -> None:
        base_amount = (
            BLEED_AMOUNT
            + hooks.sum_modifiers(
                BLEED_AMOUNT_FIXED_MODIFIER_HOOK, state, player=player, vampire=vampire.instance_id
            )
            + pending.get(PENDING_BLEED_AMOUNT_KEY, 0)
        )
        amount_box = [base_amount]
        hooks.resolve_impulse_window(
            state,
            BLEED_AMOUNT_MODIFIER_HOOK,
            player,
            other,
            context={"vampire": vampire.instance_id, "amount": amount_box, "pending": pending},
        )
        amount = max(0, amount_box[0])
        lose_pool(state, other, amount)
        if amount >= 1:
            state.edge_holder = player

    perform_minion_action(
        state, player, other, vampire, BLEED_STEALTH, resolve, action=ACTION_BLEED, directed=True
    )


def _perform_hunt(state: GameState, player: str, other: str, vampire: VampireInPlay) -> None:
    """Rulebook §4 default hunt action: undirected, +1 stealth baseline, +1 blood on success."""

    def resolve(pending: dict[str, Any]) -> None:
        # Hunt has no later hook window for an earlier stealth/intercept
        # provider to feed (OQ-11 is specific to bleed's later
        # "bleed_amount_modifier" window); `pending` is accepted only to
        # match `perform_minion_action`'s shared `resolve` call-site
        # signature, and is otherwise unused here.
        del pending
        add_blood(state, vampire, HUNT_BLOOD_GAIN)

    perform_minion_action(
        state, player, other, vampire, HUNT_STEALTH, resolve, action=ACTION_HUNT, directed=False
    )


def _perform_recruit_ally(
    state: GameState,
    player: str,
    other: str,
    vampire: VampireInPlay,
    option: HookOption,
) -> None:
    """Rulebook §4 Recruit Ally: undirected, +1 stealth, ally's cost paid
    only on success, can't act this turn (OQ-12). Chosen hook option's ally
    placed via `recruit_ally` if unblocked, else burned."""
    spec: RecruitAllySpec = option.apply(state)

    def resolve(pending: dict[str, Any]) -> None:
        del pending  # recruit ally has no later hook window of its own to feed
        if spec.pay_cost is not None:
            spec.pay_cost(state)
        ally = recruit_ally(
            state,
            player,
            krcg_id=spec.card.krcg_id,
            name=spec.card.name,
            life=spec.life,
            strength=spec.strength,
            bleed=spec.bleed,
        )
        # OQ-10 (`docs/OPEN_QUESTIONS.md`, resolved): a unique ally (printed
        # "Unique", e.g. 47th Street Royals) can collide with an opposing
        # same-named ally already in play -- mirrors `engine/phases/
        # influence.py`'s own `detect_contest_on_reveal` call after a
        # vampire's reveal.
        detect_contest_on_recruit(state, ally)

    def on_blocked(pending: dict[str, Any]) -> None:
        del pending
        state.players[player].ash_heap.append(spec.card)

    perform_minion_action(
        state,
        player,
        other,
        vampire,
        RECRUIT_ALLY_STEALTH,
        resolve,
        action=ACTION_RECRUIT_ALLY,
        directed=False,
        on_blocked=on_blocked,
    )


def _perform_action_card(
    state: GameState,
    player: str,
    other: str,
    vampire: VampireInPlay,
    option: HookOption,
) -> None:
    """Rulebook §2+§4 (OQ-17): a printed Action-type card is itself the
    vampire's whole minion action. `option`'s `ActionCardSpec` is forwarded
    to `perform_minion_action` unchanged."""
    spec: ActionCardSpec = option.apply(state)
    perform_minion_action(
        state,
        player,
        other,
        vampire,
        spec.base_stealth,
        spec.resolve,
        action=spec.action,
        directed=spec.directed,
        on_blocked=spec.on_blocked,
        maneuver_grant=spec.maneuver_grant,
    )
