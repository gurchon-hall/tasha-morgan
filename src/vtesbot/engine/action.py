"""Minion action: announce, block, resolve/combat (Rulebook §4; 2P collapses
prey/predator, CLAUDE.md §3). See OQ-9,11,17,25,26,30,31,34,36,39,46,48,60."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import hooks
from .combat import run_combat, seed_block_time_combat_grants, seed_pre_combat_maneuver_grant
from .decision import Choice, Decision

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

STEALTH_MODIFIER_HOOK = "stealth_modifier"
INTERCEPT_MODIFIER_HOOK = "intercept_modifier"
BLOCK_CANDIDATE_INJECTION_HOOK = "block_candidate_injection"
"""OQ-26: mirrors `Hook.BLOCK_CANDIDATE_INJECTION`. `apply()` must unlock
the vampire and return it as an unconditional successful block. Every
option must also set `HookOption.block_candidate_instance_id` to that same
vampire's own `instance_id` -- `attempt_block` filters injected options
against `BLOCK_CANDIDATE_EXCLUSION_HOOK`'s own exclusion set by this id,
same as it already does for the hardcoded `ready_unlocked_vampires` list,
so a named-and-excluded vampire (e.g. `cards/sleeping_mind.py`) cannot be
forced back in as an injected candidate (rules-auditor finding)."""

INTERCEPT_DECREASE_HOOK = "intercept_decrease"
"""OQ-30/31: mirrors `Hook.INTERCEPT_DECREASE`. Offered to `actor`
proactively and reactively; `apply()` appends an `ActiveInterceptDecrease`
to `pending`, not a delta."""

PENDING_INTERCEPT_DECREASE_KEY = "intercept_decrease_modifiers"
"""`pending[...]` key (OQ-30): holds a `list[ActiveInterceptDecrease]`,
appended to (never replaced) by each activated `INTERCEPT_DECREASE_HOOK`
option's own `apply` closure."""

STEALTH_INCREASE_HOOK = "stealth_increase"
"""OQ-39: `INTERCEPT_DECREASE_HOOK`'s sibling for actor's stealth.
`apply()` appends an `ActiveStealthIncrease` to `pending`; no `qualifies`
predicate needed."""

PENDING_STEALTH_INCREASE_KEY = "stealth_increase_modifiers"
"""`pending[...]` key (OQ-39): holds a `list[ActiveStealthIncrease]`,
appended to (never replaced) by each activated `STEALTH_INCREASE_HOOK`
option's own `apply` closure."""

WAKE_LOCKED_MINION_HOOK = "wake_locked_minion"
"""OQ-48: defender-side sibling of `INTERCEPT_DECREASE_HOOK`/
`STEALTH_INCREASE_HOOK`. `apply()` sets `woken = True` on a locked
vampire; block stays fully contestable."""

BLOCK_CANDIDATE_EXCLUSION_HOOK = "block_candidate_exclusion"
"""Subtractive sibling of `BLOCK_CANDIDATE_INJECTION_HOOK`: offered to
`actor` in the same proactive slot as `INTERCEPT_DECREASE_HOOK`/
`STEALTH_INCREASE_HOOK` (Rulebook §4: "as the action is announced",
before the defender's block-candidate list is computed at all).
`apply()` adds the chosen vampire's `instance_id` to
`pending[PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY]` -- it does not touch
stealth/intercept, since the named vampire must not be a block candidate
in the first place, not merely fail an attempt. Needed by
`cards/seduction.py` (krcg 101712) and `cards/sleeping_mind.py` (krcg
101805); generic plumbing, not a rule of its own -- see those modules for
the citations."""

PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY = "block_candidate_exclusions"
"""`pending[...]` key: holds a `set[str]` of excluded `instance_id`s,
added to (never replaced) by each activated `BLOCK_CANDIDATE_EXCLUSION_
HOOK` option's own `apply` closure. Consulted by `attempt_block`'s
candidate-list filter on every pass through its retry loop, so the
exclusion survives a later `WAKE_LOCKED_MINION_HOOK` making the same
vampire eligible again (`cards/sleeping_mind.py`'s own docstring). Also
consulted against `BLOCK_CANDIDATE_INJECTION_HOOK`'s own offered options,
by each one's `HookOption.block_candidate_instance_id` -- without this
second filter, a defender holding e.g. Second Tradition: Domain or
Organized Resistance could unlock-and-force-block with a vampire the actor
had just named excluded, defeating the exclusion entirely (rules-auditor
finding)."""


PENDING_BLOCK_TIME_COMBAT_GRANT_KEY = "block_time_combat_grants"
"""`pending[...]` key (OQ-60): holds `dict[str, dict[str, int]]`, vampire
instance id -> {grant_name: count}, written by `grant_block_time_combat_
effect` from a reaction's own `apply` closure, played during the block
attempt's own stealth/intercept resolution (`_duel_stealth_intercept`,
before `run_combat` even exists) -- e.g. Precognition's (krcg 101475)
superior clause, "this vampire can prevent 1 damage during the first round
of the resulting combat if they block." `perform_minion_action` forwards
only the entry keyed by the vampire that ends up the successful `blocker`
into that one combat's own `initial_combat_state`
(`combat.py::seed_block_time_combat_grants`) -- a grant recorded for a
vampire that attempted and failed, or never got to attempt, is simply never
read, and nothing here ever threads into a second, later `run_combat` call
(each `perform_minion_action` call owns one `pending` dict, forwarded at
most once). Matches [LSJ 20010813] (successful block, resulting combat
only), [LSJ 20010819-2] (no carryover to a follow-up combat), and
[LSJ 20010814-2] (re-earned fresh on a second block attempt, since the
reaction is played, and this dict written, again each time)."""


def grant_block_time_combat_effect(
    pending: dict[str, Any] | None, vampire_id: str, grant_name: str, count: int = 1
) -> None:
    """Record a one-shot combat-time effect grant (OQ-60), tied to
    `vampire_id` -- the specific vampire whose controller played the
    block-attempt-time reaction, read back by `combat.py::block_time_
    combat_grant_available`/`consume_block_time_combat_grant` once (and
    only if) that vampire ends up the successful blocker -- see
    `PENDING_BLOCK_TIME_COMBAT_GRANT_KEY` above. A provider calls this from
    its own `apply` closure, passing the `pending` dict it received via its
    own provider `context["pending"]` (the same convention every other
    `pending`-writing helper in this module uses). `pending is None` is a
    no-op, mirroring `ActiveInterceptDecrease`'s own `pending`-is-optional
    contract."""
    if pending is None:
        return
    grants = pending.setdefault(PENDING_BLOCK_TIME_COMBAT_GRANT_KEY, {})
    per_vampire = grants.setdefault(vampire_id, {})
    per_vampire[grant_name] = per_vampire.get(grant_name, 0) + count


def _excluded_block_candidates(pending: dict[str, Any] | None) -> set[str]:
    """Read-only view of `PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY`; mirrors
    `_active_intercept_decrease`'s own `pending`-is-optional contract."""
    if not pending:
        return set()
    return pending.get(PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY, set())


@dataclass(frozen=True)
class ActiveInterceptDecrease:
    """One Action Modifier's persistent intercept decrease (OQ-30). `delta`
    applies while `qualifies(blocker)` matches; never floored at 0
    (Rulebook §4)."""

    delta: int
    qualifies: Callable[[VampireInPlay], bool]


@dataclass(frozen=True)
class ActiveStealthIncrease:
    """One Action Modifier's persistent stealth increase (OQ-39). `delta`
    adds to `base_stealth` unconditionally; never floored at 0 (Rulebook
    §4)."""

    delta: int


def _active_stealth_increase(pending: dict[str, Any] | None) -> int:
    """Sum every `ActiveStealthIncrease` (OQ-39) in `pending`; mirrors
    `_active_intercept_decrease` minus the per-candidate `qualifies` filter."""
    if not pending:
        return 0
    modifiers: list[ActiveStealthIncrease] = pending.get(PENDING_STEALTH_INCREASE_KEY, [])
    return sum(modifier.delta for modifier in modifiers)


ACTION_BLEED = "bleed"
ACTION_HUNT = "hunt"
ACTION_RECRUIT_ALLY = "recruit_ally"
ACTION_POLITICAL = "political_action"
ACTION_ACTION_CARD = "action_card"
ACTION_DIABLERIE = "diablerise"
ACTION_ATTACHMENT_REMOVAL = "attachment_removal_action"
"""Action discriminator constants (OQ-9) for `action=` passed to
`attempt_block`/`perform_minion_action`. `ACTION_ATTACHMENT_REMOVAL`
(`engine/phases/minion.py::build_attachment_removal_action_spec`) is kept
distinct from `ACTION_ACTION_CARD` even though both resolve through the
same `ActionCardSpec` shape: this mechanism never plays a card from hand
(it burns an in-play attachment via accumulated contributions), so a
future hook keyed on "an Action-type library card was played" (no such
consumer exists yet -- `Perfectionist` itself gates on `ACTION_SUCCEEDED_
HOOK` plus `hooks.PENDING_REACTION_PLAYED_KEY`, not on this discriminator
or `played_card_type`, per its own card text's unqualified "a successful
action") must not mistake this for one if it is ever added."""

ACTION_SUCCEEDED_HOOK = "action_succeeded"
"""OQ-34: mirrors `Hook.ACTION_SUCCEEDED`. Rulebook §4: success means not
blocked. Dispatched via `run_effects` after `resolve(pending)`; never on
the blocked branch. Forwards this action's own `pending` dict in context
so a provider can read anything recorded during the action (e.g.
`hooks.PENDING_REACTION_PLAYED_KEY`, for `cards/perfectionist.py`'s krcg
101388 "no reaction cards were played" gate)."""

PENDING_REFERENDUM_RESULT_KEY = "referendum_result"
"""Mirrors `politics.py::REFERENDUM_RESULT_KEY` (duplicated, not imported,
to avoid a circular import). See `REFERENDUM_RESOLVED_HOOK` below."""

REFERENDUM_RESOLVED_HOOK = "referendum_resolved"
"""OQ-36: mirrors `Hook.REFERENDUM_RESOLVED`, strictly after a political
action's `resolve()` returns, only if it passed; dispatched via
`resolve_impulse_window`."""


def clear_woken_vampires(state: GameState) -> None:
    """Clear `VampireInPlay.woken` for both players (OQ-46), On the Qui
    Vive's end-of-action scope. Called from every `perform_minion_action`
    exit."""
    for player_state in state.players.values():
        for vampire in player_state.vampires.values():
            vampire.woken = False


def _active_intercept_decrease(pending: dict[str, Any] | None, blocker: VampireInPlay) -> int:
    """Sum every `ActiveInterceptDecrease` (OQ-30) in `pending` whose
    `qualifies` matches `blocker`, right now -- never cached, so a retried
    attempt (OQ-11) against a different `blocker` is re-checked fresh."""
    if not pending:
        return 0
    modifiers: list[ActiveInterceptDecrease] = pending.get(PENDING_INTERCEPT_DECREASE_KEY, [])
    return sum(modifier.delta for modifier in modifiers if modifier.qualifies(blocker))


def _duel_stealth_intercept(
    state: GameState,
    actor: str,
    defender: str,
    base_stealth: int,
    acting_vampire: VampireInPlay | None,
    blocker: VampireInPlay,
    action: str | None = None,
    directed: bool | None = None,
    pending: dict[str, Any] | None = None,
) -> tuple[int, int]:
    """Resolve the stealth/intercept ping-pong for one block attempt.
    Baselines fold active `ActiveInterceptDecrease`/`ActiveStealthIncrease`
    (OQ-30/39)."""
    stealth = base_stealth + _active_stealth_increase(pending)
    intercept = _active_intercept_decrease(pending, blocker)
    context = {
        "actor": actor,
        "defender": defender,
        "acting_vampire": acting_vampire.instance_id if acting_vampire is not None else None,
        "blocking_vampire": blocker.instance_id,
        "action": action,
        "directed": directed,
        "pending": pending,
    }
    while True:
        if stealth > intercept:
            # Block currently fails: intercept may be added, only now needed.
            options = hooks.offer(
                INTERCEPT_MODIFIER_HOOK,
                state,
                player=defender,
                stealth=stealth,
                intercept=intercept,
                **context,
            )
            if not options:
                return stealth, intercept
            delta = _ask_modifier(state, defender, INTERCEPT_MODIFIER_HOOK, options, context)
            if delta is None or state.game_over:
                return stealth, intercept
            intercept += delta
        else:
            # Block currently succeeds: stealth may be added, only now
            # needed (OQ-31/39: actor may also decrease intercept or
            # increase stealth here, reactively; see _ask_stealth_or_modifier).
            stealth_options = hooks.offer(
                STEALTH_MODIFIER_HOOK,
                state,
                player=actor,
                stealth=stealth,
                intercept=intercept,
                **context,
            )
            decrease_options = hooks.offer(
                INTERCEPT_DECREASE_HOOK,
                state,
                player=actor,
                stealth=stealth,
                intercept=intercept,
                **context,
            )
            increase_options = hooks.offer(
                STEALTH_INCREASE_HOOK,
                state,
                player=actor,
                stealth=stealth,
                intercept=intercept,
                **context,
            )
            if not stealth_options and not decrease_options and not increase_options:
                return stealth, intercept
            chosen = _ask_stealth_or_modifier(
                state, actor, stealth_options, decrease_options, increase_options, context
            )
            if chosen is None:
                return stealth, intercept
            option, kind = chosen
            if kind == "intercept_decrease":
                option.apply(state)
                if state.game_over:
                    return stealth, intercept
                # Re-evaluated fresh, same as the baseline at the top of
                # this function: never cached (OQ-11).
                intercept = _active_intercept_decrease(pending, blocker)
            elif kind == "stealth_increase":
                option.apply(state)
                stealth = base_stealth + _active_stealth_increase(pending)
            else:
                stealth += option.apply(state)
                if state.game_over:
                    return stealth, intercept


def _ask_modifier(
    state: GameState,
    player: str,
    hook_name: str,
    options: list[hooks.HookOption],
    context: dict,
) -> int | None:
    """Offer `options` plus decline; return the applied delta or None.
    Sanitizes context (OQ-30) since `pending` must never reach an agent."""
    by_value = {o.choice.value: o for o in options}
    choices = tuple(o.choice for o in options) + (Choice("decline", "Decline"),)
    decision = Decision(
        player=player,
        kind=hook_name,
        choices=choices,
        context=hooks.sanitize_decision_context(context),
    )
    answer = state.ask(decision)
    if answer.value == "decline":
        return None
    option = by_value[answer.value]
    hooks.mark_reaction_played(context.get(hooks.PENDING_CONTEXT_KEY), option)
    return option.apply(state)


def _ask_stealth_or_modifier(
    state: GameState,
    actor: str,
    stealth_options: list[hooks.HookOption],
    decrease_options: list[hooks.HookOption],
    increase_options: list[hooks.HookOption],
    context: dict,
) -> tuple[hooks.HookOption, str] | None:
    """Merge `STEALTH_MODIFIER_HOOK`/`INTERCEPT_DECREASE_HOOK`/
    `STEALTH_INCREASE_HOOK` into one `Decision` (OQ-31/39). Returns
    `(option, kind)` or `None`."""
    decrease_values = {o.choice.value for o in decrease_options}
    increase_values = {o.choice.value for o in increase_options}
    by_value = {o.choice.value: o for o in stealth_options}
    by_value.update({o.choice.value: o for o in decrease_options})
    by_value.update({o.choice.value: o for o in increase_options})
    choices = (
        tuple(o.choice for o in stealth_options)
        + tuple(o.choice for o in decrease_options)
        + tuple(o.choice for o in increase_options)
        + (Choice("decline", "Decline"),)
    )
    hooks.ensure_unique_choice_values(choices, decision_kind=STEALTH_MODIFIER_HOOK)
    decision = Decision(
        player=actor,
        kind=STEALTH_MODIFIER_HOOK,
        choices=choices,
        context=hooks.sanitize_decision_context(context),
    )
    answer = state.ask(decision)
    if answer.value == "decline":
        return None
    option = by_value[answer.value]
    hooks.mark_reaction_played(context.get(hooks.PENDING_CONTEXT_KEY), option)
    if answer.value in decrease_values:
        return option, "intercept_decrease"
    if answer.value in increase_values:
        return option, "stealth_increase"
    return option, "stealth_delta"


def _candidate_allowed_by_predicate(
    state: GameState,
    defender: str,
    predicate: Callable[[VampireInPlay], bool] | None,
    instance_id: str | None,
) -> bool:
    """Whether `instance_id` (one of `defender`'s own vampires) satisfies
    `predicate`, or vacuously true when there is no predicate at all.
    Shared by the hardcoded `ready_unlocked_vampires` candidate list and
    `BLOCK_CANDIDATE_INJECTION_HOOK`'s own offered options -- mirrors
    `BLOCK_CANDIDATE_EXCLUSION_HOOK`'s own dual-filter precedent (an
    action-card-level predicate must veto an injected candidate too, or a
    defender holding e.g. Second Tradition: Domain could force-block with a
    vampire this action's own printed text already forbids from blocking
    at all)."""
    if predicate is None:
        return True
    if instance_id is None:
        return False
    vampire = state.players[defender].vampires.get(instance_id)
    return vampire is not None and predicate(vampire)


def attempt_block(
    state: GameState,
    actor: str,
    defender: str,
    base_stealth: int,
    acting_vampire: VampireInPlay | None = None,
    action: str | None = None,
    directed: bool | None = None,
    pending: dict[str, Any] | None = None,
    block_candidate_predicate: Callable[[VampireInPlay], bool] | None = None,
) -> VampireInPlay | None:
    """Offer `defender` a block with a ready unlocked vampire. Returns the
    blocker on success, None on decline; loops on failed attempts
    (Rulebook §4).

    `block_candidate_predicate` (generic plumbing, not a rule of its own --
    see the calling action card's own module for the citation, e.g.
    `cards/propaganda.py` krcg 101495, "Titled vampires cannot block this
    action"): an unconditional, property-based filter tied to *this
    action's own printed text*, distinct from `BLOCK_CANDIDATE_EXCLUSION_
    HOOK`'s actor-chosen, per-vampire `instance_id` set -- both apply
    together (a vampire excluded by either mechanism cannot block). Unlike
    that hook, this is not offered as a `Decision`: it is supplied once by
    the action's own `ActionCardSpec` (`engine/phases/minion.py`) and
    re-evaluated live on every pass through this function's own retry
    loop, since `candidates`/`injected_options` are rebuilt fresh each
    iteration -- a vampire that only becomes a candidate later in the same
    loop (e.g. via `WAKE_LOCKED_MINION_HOOK`) is still checked against it
    then, not against a stale snapshot taken before the loop started."""
    if pending is None:
        pending = {}
    while not state.game_over:
        proactive_context = {
            "actor": actor,
            "defender": defender,
            "acting_vampire": acting_vampire.instance_id if acting_vampire is not None else None,
            "action": action,
            "directed": directed,
            "base_stealth": base_stealth,
            "pending": pending,
        }
        hooks.offer_until_pass(state, INTERCEPT_DECREASE_HOOK, actor, proactive_context)
        if state.game_over:
            return None
        hooks.offer_until_pass(state, STEALTH_INCREASE_HOOK, actor, proactive_context)
        if state.game_over:
            return None
        hooks.offer_until_pass(state, BLOCK_CANDIDATE_EXCLUSION_HOOK, actor, proactive_context)
        if state.game_over:
            return None
        hooks.offer_until_pass(state, WAKE_LOCKED_MINION_HOOK, defender, proactive_context)
        if state.game_over:
            return None
        excluded = _excluded_block_candidates(pending)
        candidates = [
            v
            for v in state.ready_unlocked_vampires(defender)
            if v.instance_id not in excluded
            and _candidate_allowed_by_predicate(
                state, defender, block_candidate_predicate, v.instance_id
            )
        ]
        candidate_choices = tuple(
            Choice(f"block_with:{v.instance_id}", f"Block with {v.card.name}") for v in candidates
        )

        injected_options = hooks.offer(
            BLOCK_CANDIDATE_INJECTION_HOOK,
            state,
            player=defender,
            actor=actor,
            defender=defender,
            acting_vampire=acting_vampire.instance_id if acting_vampire is not None else None,
            action=action,
            directed=directed,
            base_stealth=base_stealth,
            pending=pending,
        )
        for injected in injected_options:
            if injected.block_candidate_instance_id is None:
                raise AssertionError(
                    f"{BLOCK_CANDIDATE_INJECTION_HOOK!r} option "
                    f"{injected.choice.value!r} did not set "
                    "block_candidate_instance_id -- required so "
                    "BLOCK_CANDIDATE_EXCLUSION_HOOK can veto it (engine "
                    "invariant, see HookOption's own docstring)"
                )
        injected_options = [
            injected
            for injected in injected_options
            if injected.block_candidate_instance_id not in excluded
            and _candidate_allowed_by_predicate(
                state, defender, block_candidate_predicate, injected.block_candidate_instance_id
            )
        ]
        by_injected_value = {o.choice.value: o for o in injected_options}

        offered_choices = candidate_choices + tuple(o.choice for o in injected_options)
        if not offered_choices:
            return None  # nothing legal to block with: no vacuous decision raised.

        choices = offered_choices + (Choice("decline", "Decline to block"),)
        hooks.ensure_unique_choice_values(choices, decision_kind="block_attempt")
        decision = Decision(
            player=defender,
            kind="block_attempt",
            choices=choices,
            context={
                "actor": actor,
                "base_stealth": base_stealth,
                "action": action,
                "directed": directed,
            },
        )
        choice = state.ask(decision)
        if choice.value == "decline":
            return None

        if choice.value in by_injected_value:
            # OQ-26: an immediate, unconditional successful block -- never
            # runs the stealth/intercept ping-pong for this candidate.
            injected_option = by_injected_value[choice.value]
            hooks.mark_reaction_played(pending, injected_option)
            injected_blocker = injected_option.apply(state)
            return None if state.game_over else injected_blocker

        instance_id = choice.value.split(":", 1)[1]
        blocker = state.players[defender].vampires[instance_id]

        stealth, intercept = _duel_stealth_intercept(
            state,
            actor,
            defender,
            base_stealth,
            acting_vampire,
            blocker,
            action=action,
            directed=directed,
            pending=pending,
        )
        if state.game_over:
            return None
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
    resolve: Callable[[dict[str, Any]], None],
    action: str | None = None,
    directed: bool | None = None,
    on_blocked: Callable[[dict[str, Any]], None] | None = None,
    maneuver_grant: str | None = None,
    block_candidate_predicate: Callable[[VampireInPlay], bool] | None = None,
) -> None:
    """Announce, block attempt, resolve or combat (Rulebook §4). Dispatches
    `ACTION_SUCCEEDED_HOOK` (OQ-34) then `REFERENDUM_RESOLVED_HOOK`
    (OQ-36). `block_candidate_predicate` is forwarded unchanged to
    `attempt_block` -- see that function's own docstring. Also forwards any
    `PENDING_BLOCK_TIME_COMBAT_GRANT_KEY` entry (OQ-60) recorded for the
    successful blocker into that combat's own `initial_combat_state` -- see
    `grant_block_time_combat_effect`'s own docstring."""
    vampire.locked = True
    pending: dict[str, Any] = {}
    blocker = attempt_block(
        state,
        actor_player,
        defender_player,
        base_stealth,
        vampire,
        action=action,
        directed=directed,
        pending=pending,
        block_candidate_predicate=block_candidate_predicate,
    )
    if state.game_over:
        clear_woken_vampires(state)
        return
    if blocker is not None:
        blocker.locked = True
        initial_combat_state: dict[str, Any] | None = (
            seed_pre_combat_maneuver_grant(maneuver_grant) if maneuver_grant is not None else None
        )
        block_time_grants = pending.get(PENDING_BLOCK_TIME_COMBAT_GRANT_KEY, {}).get(
            blocker.instance_id
        )
        if block_time_grants:
            seeded = seed_block_time_combat_grants({blocker.instance_id: dict(block_time_grants)})
            initial_combat_state = (
                seeded if initial_combat_state is None else {**initial_combat_state, **seeded}
            )
        run_combat(state, actor_player, vampire, defender_player, blocker, initial_combat_state)
        if state.game_over:
            clear_woken_vampires(state)
            return
        if on_blocked is not None:
            on_blocked(pending)
        clear_woken_vampires(state)
        return
    resolve(pending)
    hooks.run_effects(
        ACTION_SUCCEEDED_HOOK,
        state,
        actor_player=actor_player,
        vampire=vampire,
        action=action,
        pending=pending,
    )
    if action == ACTION_POLITICAL:
        result = pending.get(PENDING_REFERENDUM_RESULT_KEY)
        if result is not None and result["passed"]:
            hooks.resolve_impulse_window(
                state,
                REFERENDUM_RESOLVED_HOOK,
                actor_player,
                defender_player,
                context={
                    "caller": actor_player,
                    "other": defender_player,
                    "caller_vampire_id": vampire.instance_id,
                    "margin": result["votes_for"] - result["votes_against"],
                    "pending": pending,
                },
            )
    clear_woken_vampires(state)


def force_lock_ready_unlocked_minion(
    state: GameState, player: str, *, reason: str | None = None
) -> VampireInPlay | None:
    """Force `player` to lock one of their own ready unlocked vampires,
    their own choice among ties, never the caller's.

    Sourced from the closest on-file precedent for this exact "[that
    Methuselah] locks a [vampire] they control" construction (no
    "of their choice"/"you choose" qualifier naming a different decision
    maker): Brujah Debate (krcg 100260) reads "that Methuselah locks one of
    the oldest Brujah they control", and its own ruling settles who
    chooses -- "If more than one Brujah shares the highest capacity amount,
    the controller chooses which of them to lock during her master phase."
    [LSJ 19980224]. Sowing Dissension (krcg 101838, "Each other Methuselah
    locks an unlocked ready younger vampire he or she controls") and
    Propaganda's own superior clause (krcg 101495, "the target Methuselah
    locks a ready unlocked minion they control") use the identical
    grammatical pattern -- the affected Methuselah is the subject
    performing the lock, so the affected Methuselah is who chooses, per the
    Brujah Debate ruling.

    Scoped to vampires only, matching `GameState.ready_unlocked_vampires`/
    `engine/phases/minion.py::minion_phase`'s own vampire-only action
    economy -- no card implemented in this project grants an ally or
    retainer its own minion action, so "minion" here has nothing to
    generalize to beyond vampires yet.

    Mandatory once at least one eligible vampire exists (no decline
    option -- the cited cards all read "locks", never "may lock"); returns
    `None` with no `Decision` raised at all when `player` has no ready
    unlocked vampire (nothing to comply with, mirroring `_perform_
    diablerise`'s bound-target fizzle convention for "cannot do the
    impossible"). `reason` is an optional caller-supplied string surfaced
    in the `Decision.context` only, for an agent that wants to distinguish
    which card forced this (not consulted by the engine itself)."""
    candidates = state.ready_unlocked_vampires(player)
    if not candidates:
        return None
    choices = tuple(Choice(f"lock:{v.instance_id}", f"Lock {v.card.name}") for v in candidates)
    decision = Decision(
        player=player,
        kind="forced_lock_own_minion",
        choices=choices,
        context={"reason": reason} if reason is not None else {},
    )
    choice = state.ask_unless_forced(decision)
    instance_id = choice.value.split(":", 1)[1]
    vampire = state.players[player].vampires[instance_id]
    vampire.locked = True
    return vampire
