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
the sole opponent is simultaneously prey and predator, so the rulebook's
"prey first, then predator" sequencing (meant to give several *different*
Methuselahs each a turn) collapses to a single block-attempt decision,
offered to that one opponent, for both directed and undirected actions.

Stealth/intercept ping-pong (`engine/hooks.py`): per the rule quoted above,
the *blocking* Methuselah may add intercept only while the attempt is
currently failing (stealth > intercept); the *acting* Methuselah may add
stealth only while it is currently succeeding (intercept >= stealth) --
this is a strict alternation, not the general "both sides get a turn"
impulse window. `_duel_stealth_intercept` below implements it via the
`"stealth_modifier"`/`"intercept_modifier"` hooks; with no providers
registered for either hook yet, each offer is empty and the loop terminates
immediately at (stealth=base_stealth, intercept=0).

Open-question plumbing threaded through `attempt_block`/
`_duel_stealth_intercept`/`perform_minion_action` below (`docs/
OPEN_QUESTIONS.md`; see each parameter's own docstring for how it is used):
- OQ-9: `action: str | None` (the `ACTION_*` constants below) lets a hook
  provider gate on which minion action is in progress (e.g. Bonding's
  "cannot be used to increase the stealth of a non-bleed action") instead of
  guessing from `base_stealth`'s numeric value.
- OQ-17: `directed: bool | None` records the Rulebook glossary's Directed
  vs. Undirected Action distinction; the 2P collapse above means it changes
  no mechanics here today, it is threaded through only as context for a
  future hook/decision consumer.
- OQ-11: `perform_minion_action` builds one shared mutable `pending:
  dict[str, Any]` per attempt so a card play spanning the block-attempt and
  resolve/on_blocked phases can carry state between them (see `engine/
  phases/minion.py` for the worked example).
- OQ-26 (resolved): `attempt_block` also offers `BLOCK_CANDIDATE_INJECTION_
  HOOK` to the defender each retry, so a provider can contribute a candidate
  built from one of the defender's own *locked* vampires (e.g. Organized
  Resistance). Per the controlling ruling [LSJ 20090514] such a block cannot
  fail once chosen, so it bypasses `_duel_stealth_intercept` entirely. With
  no provider registered, this is a no-op.
- OQ-25 (resolved): `perform_minion_action`'s `maneuver_grant` seeds one
  optional pre-combat maneuver grant into this function's own blocked-branch
  `run_combat` call (see `engine/combat.py`'s "Pre-combat grant seeding"
  section for the unblocked-path counterpart).
- OQ-30 (resolved): `attempt_block` also offers `INTERCEPT_DECREASE_HOOK` to
  `actor` (never `defender`), at the top of its own retry loop -- before any
  blocking candidate is even chosen, and again on every retry (OQ-11) --
  independent of the `"stealth_modifier"`/`"intercept_modifier"` "only when
  needed" ping-pong, per the rulebook's own "some cards and other effects
  can be used to increase or decrease (even below 0) a minion's stealth or
  intercept" (`data/sources/rulebook/2026-10-09/
  4-detailed-turn-sequence.md:556-557`) and Perfect Paragon's own on-file
  ruling that such a play needs no block attempt in progress. A provider's
  `apply` must append one `ActiveInterceptDecrease` (a `delta` plus a
  blocking-candidate `qualifies` predicate) to `pending[PENDING_INTERCEPT_
  DECREASE_KEY]` rather than return a one-shot numeric delta;
  `_duel_stealth_intercept` re-evaluates every recorded modifier's own
  predicate against *whichever* candidate is currently fixed, every call,
  so a modifier activated before any candidate existed still correctly
  applies to a later-chosen (or retried, OQ-11) one. With no provider
  registered, this is a no-op. Every `Decision` this module raises from a
  hook `context` that may carry `pending` (`_ask_modifier`,
  `_ask_stealth_or_decrease`, and `hooks.offer_until_pass`/
  `resolve_impulse_window` generally) is built via `hooks.
  sanitize_decision_context`, never a bare `dict(context)`, so `pending` --
  and the `Callable` it may hold since this entry -- never reaches an agent
  (`rules-auditor` finding on this entry's first landing).
- OQ-31 (resolved -- Reading B, the project owner's own ruling, the same
  kind of call OQ-20's casting-order ambiguity needed): OQ-30's own
  proactive, top-of-retry-loop `INTERCEPT_DECREASE_HOOK` offer is not the
  *only* opportunity to play such a card -- `_duel_stealth_intercept`'s own
  `else` branch (`stealth <= intercept`, where impulse already returns to
  `actor` with a specific candidate fixed) also offers it, merged into the
  same `Decision` as `STEALTH_MODIFIER_HOOK`'s own choices via `_ask_
  stealth_or_decrease` (mirrors `engine/combat.py::_ask_strike`'s own
  two-hooks-into-one-offer precedent). Both opportunities coexist per the
  ruling: the rulebook's generic Action Modifier timing sentence supports
  both a proactive, pre-candidate play and a reactive, per-candidate one.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import hooks
from .combat import run_combat, seed_pre_combat_maneuver_grant
from .decision import Choice, Decision

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

STEALTH_MODIFIER_HOOK = "stealth_modifier"
INTERCEPT_MODIFIER_HOOK = "intercept_modifier"
BLOCK_CANDIDATE_INJECTION_HOOK = "block_candidate_injection"
"""OQ-26 (`docs/OPEN_QUESTIONS.md`, resolved): mirrors `src/vtesbot/cards/
registry.py::Hook.BLOCK_CANDIDATE_INJECTION`'s own string value. See the
module docstring's OQ-26 entry for the mechanism; a provider's
`HookOption.apply(state)` must unlock its chosen (locked) vampire and
return it, for `attempt_block` to return directly as an unconditional
successful blocker."""

INTERCEPT_DECREASE_HOOK = "intercept_decrease"
"""OQ-30 (`docs/OPEN_QUESTIONS.md`, resolved): mirrors `src/vtesbot/cards/
registry.py::Hook.INTERCEPT_DECREASE`'s own string value. See the module
docstring's OQ-30 entry and `ActiveInterceptDecrease` below for the
mechanism. Offered to `actor` at two points (OQ-31, resolved -- Reading B):
proactively, via `hooks.offer_until_pass` at the top of `attempt_block`'s
own retry loop (actor may activate any number of qualifying modifiers in a
row, then passes), and reactively, merged into `_duel_stealth_intercept`'s
own `STEALTH_MODIFIER_HOOK` offer via `_ask_stealth_or_decrease` once a
specific blocking candidate is already fixed. Either way, a provider's
`HookOption.apply(state)` return value is ignored by the caller (the
provider's own `apply` closure must instead append an
`ActiveInterceptDecrease` to `pending[PENDING_INTERCEPT_DECREASE_KEY]`,
since this hook's effect is a persistent, action-scoped record, not a
one-shot delta) -- a provider need not know or care which of the two call
sites invoked it; both share the same core context keys (`actor`/
`defender`/`acting_vampire`/`action`/`directed`/`pending`) and the same
`pending` container, though the reactive offer's context additionally
carries `blocking_vampire` (the specific candidate already fixed) while the
proactive offer's carries `base_stealth` instead (no candidate exists
yet)."""

PENDING_INTERCEPT_DECREASE_KEY = "intercept_decrease_modifiers"
"""`pending[...]` key (OQ-30): holds a `list[ActiveInterceptDecrease]`,
appended to (never replaced) by each activated `INTERCEPT_DECREASE_HOOK`
option's own `apply` closure."""


@dataclass(frozen=True)
class ActiveInterceptDecrease:
    """One acting-side Action Modifier's persistent, action-scoped intercept
    decrease (OQ-30, `docs/OPEN_QUESTIONS.md`, resolved).

    `delta` is the signed `int` contribution (typically negative, e.g. `-1`
    for a printed "-1 intercept" clause) applied to a qualifying candidate's
    intercept baseline for the rest of the action -- the rulebook's own
    "can be used to increase or decrease (even below 0) a minion's stealth
    or intercept" (`data/sources/rulebook/2026-10-09/
    4-detailed-turn-sequence.md:556-557`) means this is deliberately never
    floored at 0. `qualifies` is the printed clause's own blocking-candidate
    predicate (e.g. "is an Ally, or is younger than vampire X") -- a plain
    function over a `VampireInPlay`, re-run fresh by `_duel_stealth_
    intercept` against whichever candidate is currently fixed every time it
    is consulted, only from trusted engine arithmetic. It lives inside
    `pending`, which is also threaded to every hook *provider* as part of
    `context` -- but every call site that turns such a `context` into a
    `Decision.context` must build it via `hooks.sanitize_decision_context`
    (CLAUDE.md "Information hiding"; `rules-auditor` finding on this entry),
    which strips `pending` out, so this `Callable` (and the live object
    graph it may itself close over, e.g. a specific `VampireInPlay`) is
    guaranteed never to reach an agent, not merely true by omission."""

    delta: int
    qualifies: Callable[[VampireInPlay], bool]


ACTION_BLEED = "bleed"
ACTION_HUNT = "hunt"
ACTION_RECRUIT_ALLY = "recruit_ally"
ACTION_POLITICAL = "political_action"
ACTION_ACTION_CARD = "action_card"
"""Action-name discriminator constants (OQ-9, `docs/OPEN_QUESTIONS.md`): the
single source of truth for `action=` values passed to `attempt_block`/
`perform_minion_action`, so a producing call site (`engine/phases/minion.py`,
`engine/politics.py`) and a consuming hook provider cannot silently desync
over a re-typed literal. `ACTION_ACTION_CARD` is the one fixed discriminator
every `"action_card_play"` hook play shares, regardless of which specific
library card of printed `types == ["Action"]` is being played."""


def _active_intercept_decrease(pending: dict[str, Any] | None, blocker: VampireInPlay) -> int:
    """Sum every `ActiveInterceptDecrease` (OQ-30) in `pending[PENDING_
    INTERCEPT_DECREASE_KEY]` whose own `qualifies` predicate matches
    `blocker`, right now -- never cached, so a later call with a different
    `blocker` (a retried block attempt, OQ-11) is independently re-checked
    against the same persistent list of activated modifiers."""
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
    """Resolve the "only when needed" stealth/intercept ping-pong for one
    block attempt against `blocker` (see module docstring).

    `intercept`'s starting baseline folds in every currently-active
    `ActiveInterceptDecrease` (OQ-30) whose `qualifies` predicate matches
    `blocker`, re-evaluated fresh here rather than cached from whenever the
    modifier was activated -- this is what lets a modifier activated before
    any candidate existed, or before a retried attempt (OQ-11) with a
    different candidate, correctly apply to *this* candidate specifically.

    The `else` branch below additionally offers `INTERCEPT_DECREASE_HOOK`
    to `actor` reactively, merged into the same `Decision` as
    `STEALTH_MODIFIER_HOOK`'s own choices (OQ-31, resolved -- Reading B,
    see `_ask_stealth_or_decrease`) -- a second opportunity to activate a
    modifier, alongside OQ-30's own proactive one at `attempt_block`'s own
    retry-loop top. Either way the activated modifier is recorded into the
    same `pending[PENDING_INTERCEPT_DECREASE_KEY]` list, so it composes
    identically with OQ-11's retry case regardless of which call site
    activated it.
    """
    stealth = base_stealth
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
            if delta is None:
                return stealth, intercept
            intercept += delta
        else:
            # Block currently succeeds: stealth may be added, only now
            # needed. OQ-31 (`docs/OPEN_QUESTIONS.md`, resolved -- Reading
            # B, the project owner's own ruling): the acting Methuselah may
            # also, reactively, at this same impulse-return point -- not
            # only proactively at `attempt_block`'s own top-of-retry-loop
            # offer -- decrease this specific, now-known blocker's
            # intercept. See `_ask_stealth_or_decrease` for the merge.
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
            if not stealth_options and not decrease_options:
                return stealth, intercept
            chosen = _ask_stealth_or_decrease(
                state, actor, stealth_options, decrease_options, context
            )
            if chosen is None:
                return stealth, intercept
            option, is_decrease = chosen
            if is_decrease:
                option.apply(state)
                # Re-evaluated fresh, same as the baseline at the top of
                # this function: never cached (OQ-11).
                intercept = _active_intercept_decrease(pending, blocker)
            else:
                stealth += option.apply(state)


def _ask_modifier(
    state: GameState,
    player: str,
    hook_name: str,
    options: list[hooks.HookOption],
    context: dict,
) -> int | None:
    """Offer `options` plus a decline choice; return the applied delta, or
    None if the player declines (the hook's `apply` must return an `int`).

    Builds `Decision.context` via `hooks.sanitize_decision_context` (OQ-30,
    `docs/OPEN_QUESTIONS.md`), not a bare `dict(context)`: `context` here
    always carries `"pending"` (see module docstring), which must never
    reach the agent-visible `Decision.context`."""
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
    return by_value[answer.value].apply(state)


def _ask_stealth_or_decrease(
    state: GameState,
    actor: str,
    stealth_options: list[hooks.HookOption],
    decrease_options: list[hooks.HookOption],
    context: dict,
) -> tuple[hooks.HookOption, bool] | None:
    """Offer `actor` both `STEALTH_MODIFIER_HOOK`'s and `INTERCEPT_DECREASE_
    HOOK`'s own currently-legal options, unioned into one `Decision`, plus a
    decline choice (OQ-31, `docs/OPEN_QUESTIONS.md`, resolved -- Reading B).

    Mirrors the "merge two distinct hooks' own choices into one offer for
    the same player at the same impulse moment" shape `engine/combat.py::
    _ask_strike` already establishes for `COMBAT_STRIKE_OPTION_HOOK`/
    `COMBAT_DODGE_OPTION_HOOK` -- not two sequential asks, since nothing in
    the rules orders one card type ahead of the other at a single impulse
    point (Rulebook SS2 glossary "Impulse": "the acting Methuselah always
    has the impulse... after playing one effect, they may play another").

    Kept under the pre-existing `STEALTH_MODIFIER_HOOK` decision kind, not a
    third name: whenever `decrease_options` is empty (every provider
    registered before this entry, and every call with no `INTERCEPT_
    DECREASE_HOOK` provider registered), this is byte-for-byte the same
    `Decision` `_ask_modifier` would have built for `STEALTH_MODIFIER_HOOK`
    alone, so no already-`implemented` card's own scripted tests observe any
    change. Returns `(chosen_option, is_decrease)`, or `None` if declined;
    interpreting `apply`'s return value (a stealth delta vs. a side-effecting
    `None`, per each hook's own contract -- see `STEALTH_MODIFIER_HOOK`'s and
    `INTERCEPT_DECREASE_HOOK`'s own docstrings) is the caller's job, since
    the two hooks' `apply` contracts differ."""
    decrease_values = {o.choice.value for o in decrease_options}
    by_value = {o.choice.value: o for o in stealth_options}
    by_value.update({o.choice.value: o for o in decrease_options})
    choices = (
        tuple(o.choice for o in stealth_options)
        + tuple(o.choice for o in decrease_options)
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
    return by_value[answer.value], answer.value in decrease_values


def attempt_block(
    state: GameState,
    actor: str,
    defender: str,
    base_stealth: int,
    acting_vampire: VampireInPlay | None = None,
    action: str | None = None,
    directed: bool | None = None,
    pending: dict[str, Any] | None = None,
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

    `action` (OQ-9) and `directed` (OQ-17) are forwarded into the
    `"block_attempt"` decision's own context and the stealth/intercept hook
    context (see module docstring). `pending` (OQ-11) likewise; a caller that
    does not pass one gets a fresh `{}` created once here, so every hook
    offer during this call shares the same mutable object.

    `BLOCK_CANDIDATE_INJECTION_HOOK` (OQ-26, resolved, see module docstring)
    is offered to `defender` every time around the loop, alongside the
    hardcoded `state.ready_unlocked_vampires(defender)` candidates. With no
    provider registered, this adds nothing.

    `INTERCEPT_DECREASE_HOOK` (OQ-30, resolved, see module docstring) is
    offered to `actor` at the very top of the loop, every time around it --
    before `defender`'s own candidate pool is even computed, let alone this
    attempt's "no candidates at all -> return `None` with no decision
    raised" short-circuit -- so `actor` can activate it proactively even
    when no block attempt is otherwise possible yet, matching Perfect
    Paragon's own on-file ruling ("a block attempt is not required"). With
    no provider registered, this adds nothing.
    """
    if pending is None:
        pending = {}
    while True:
        hooks.offer_until_pass(
            state,
            INTERCEPT_DECREASE_HOOK,
            actor,
            {
                "actor": actor,
                "defender": defender,
                "acting_vampire": acting_vampire.instance_id
                if acting_vampire is not None
                else None,
                "action": action,
                "directed": directed,
                "base_stealth": base_stealth,
                "pending": pending,
            },
        )
        candidates = state.ready_unlocked_vampires(defender)
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
            return by_injected_value[choice.value].apply(state)

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
) -> None:
    """Announce (lock) -> block attempt -> resolve-or-combat (Rulebook SS4).

    `resolve` is called only if the action goes unblocked (declined or
    evaded); it must perform the action's own effect (e.g. bleed/hunt).
    `on_blocked`, if provided, is called only if the action is blocked,
    *after* combat resolves (Rulebook SS4 "Resolve the Action": "If the
    action is blocked, then ... the cost of the action is not paid" -- a
    card-specific consequence of a block, e.g. burning a card set aside at
    announce time); a call site that never passes it (e.g. bleed/hunt) sees
    no behaviour change on the blocked branch.

    `action` (OQ-9), `directed` (OQ-17) and the per-attempt `pending:
    dict[str, Any]` scratch container (OQ-11) are threaded through to
    `attempt_block` and then on to `resolve`/`on_blocked`, so a card played
    during the block-attempt phase can stash something for either callback
    to read back (see module docstring; worked example in `engine/phases/
    minion.py`).

    `maneuver_grant` (OQ-25, resolved): a vampire instance id to pre-grant
    one optional maneuver to, for the combat this *blocked* branch's own
    `run_combat` call produces (`None`, the default, changes nothing). This
    is the only way to reach that combat with a pre-seeded grant, since
    unlike the unblocked branch's `resolve()` callback, this function has no
    `ActionCardSpec`-shaped hook of its own to extend it -- see `engine/
    combat.py`'s "Pre-combat grant seeding" section.
    """
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
    )
    if blocker is not None:
        blocker.locked = True
        initial_combat_state = (
            seed_pre_combat_maneuver_grant(maneuver_grant) if maneuver_grant is not None else None
        )
        run_combat(state, actor_player, vampire, defender_player, blocker, initial_combat_state)
        if on_blocked is not None:
            on_blocked(pending)
        return
    resolve(pending)
