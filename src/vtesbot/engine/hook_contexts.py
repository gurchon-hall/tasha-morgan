"""The context each wired `Hook` passes its providers, one `TypedDict` per hook
(or per phase). Each docstring is that hook's contract: how it is dispatched,
who is asked, what `apply` or a provider returns."""

from collections.abc import Mapping
from types import UnionType
from typing import TYPE_CHECKING, Any, Literal, TypedDict, get_args

from .hooks import Hook

if TYPE_CHECKING:
    from .state import VampireInPlay

type Pending = dict[str, Any]
"""Scratch dict shared by the hooks of one action (ENG-005), or of one
referendum for `POLLING_STEP`; never copied into a `Decision`."""
type RoundState = dict[str, Any]
type CombatState = dict[str, Any]
type VoteCast = tuple[str, str, int, str]
"""One cast vote source: `(caster, source_id, votes, direction)`."""


# --- master, influence, unlock phases ---


class MasterPhasePlayContext(TypedDict):
    """`offer` to the acting player on each master phase step, while a master
    phase action remains. `apply` returns truthy for a trifle."""

    player: str


class MasterPhaseAbilityContext(TypedDict):
    """`offer` with `MASTER_PHASE_PLAY`: a crypt card's printed master-phase
    ability, costing no master phase action. `apply` return ignored."""

    player: str


class InfluencePhaseActionContext(TypedDict):
    """`offer` to the acting player on each influence step, beside the three
    transfer kinds. `apply` returns the `int` transfers consumed. See ENG-016."""

    player: str
    transfers_remaining: int


class UnlockPhaseMandatoryEffectContext(TypedDict):
    """`offer` in the unlock phase's ordering loop, which cannot end while one
    remains. `apply` pays the effect (Fame)."""

    player: str


# --- minion phase: choosing and resolving an action ---


class _PlayerVampireContext(TypedDict):
    player: str
    vampire: str


class RecruitAllyPlayContext(_PlayerVampireContext):
    """`offer` among the acting vampire's action choices. `apply` returns a
    `RecruitAllySpec`. See ENG-006, ENG-007."""


class ActionCardPlayContext(_PlayerVampireContext):
    """`offer` among the acting vampire's action choices. `apply` returns an
    `ActionCardSpec`. See ENG-011, ENG-037."""


class AttachmentRemovalActionPlayContext(_PlayerVampireContext):
    """`offer` with `ACTION_CARD_PLAY`, one option per removable attachment;
    plays no card. `apply` returns an `ActionCardSpec` (Pulled Fangs)."""


class CannotHuntContext(_PlayerVampireContext):
    """`any_true` in the mandatory-hunt loop: a truthy provider sends the
    vampire to torpor instead of hunting."""


class BleedAmountFixedModifierContext(_PlayerVampireContext):
    """`sum_modifiers` before the `BLEED_AMOUNT_MODIFIER` window: a printed,
    unconditional bleed bonus. A provider returns an `int`."""


class BleedAmountModifierContext(_PlayerVampireContext):
    """`resolve_impulse_window`, acting player first, as a bleed resolves.
    `apply` changes `amount[0]` in place."""

    amount: list[int]
    pending: Pending


class ActionSucceededContext(TypedDict):
    """`run_effects` once an unblocked action has resolved; `vampire` is the
    live object, safe since only card code reads it. See ENG-024."""

    actor_player: str
    vampire: VampireInPlay
    action: str | None
    pending: Pending


# --- block attempts ---


class _BlockAttemptContext(TypedDict):
    player: str
    actor: str
    defender: str
    acting_vampire: str | None
    action: str | None
    directed: bool | None


class _ProactiveBlockContext(_BlockAttemptContext):
    base_stealth: int
    pending: Pending


class _StealthInterceptContext(_BlockAttemptContext):
    blocking_vampire: str
    stealth: int
    intercept: int
    pending: Pending


class BlockCandidateExclusionContext(_ProactiveBlockContext):
    """`offer_until_pass` to `actor` before each block attempt. `apply` adds a
    vampire id to `pending[PENDING_BLOCK_CANDIDATE_EXCLUSION_KEY]`."""


class WakeLockedMinionContext(_ProactiveBlockContext):
    """`offer_until_pass` to `defender` before each block attempt.
    `apply` sets `woken` on a locked vampire (`skip_next_unlock` on an ally).
    See ENG-030."""


class BlockCandidateInjectionContext(_ProactiveBlockContext):
    """`offer` to `defender` beside the ready candidates; each option sets
    `block_candidate_instance_id`. `apply` returns the blocker. See ENG-018."""


class BlockAttemptCostContext(_BlockAttemptContext):
    """`collect` once per block candidate, before it is offered. A provider
    returns a `BlockAttemptCost` or `None`. See ENG-044."""

    candidate: str


class InterceptDecreaseProactiveContext(_ProactiveBlockContext):
    """`offer_until_pass` to `actor` before each block attempt. `apply`
    appends an `ActiveInterceptDecrease` to `pending`. See ENG-021, RUL-009."""


class InterceptDecreaseDuringBlockContext(_StealthInterceptContext):
    """`offer` to `actor` while the block would succeed, beside
    `STEALTH_MODIFIER`; same `apply` as the proactive phase. See RUL-009."""


InterceptDecreaseContext = InterceptDecreaseProactiveContext | InterceptDecreaseDuringBlockContext


class StealthIncreaseProactiveContext(_ProactiveBlockContext):
    """`offer_until_pass` to `actor` before each block attempt. `apply`
    appends an `ActiveStealthIncrease` to `pending`. See RUL-011."""


class StealthIncreaseDuringBlockContext(_StealthInterceptContext):
    """`offer` to `actor` while the block would succeed, beside
    `STEALTH_MODIFIER`; same `apply` as the proactive phase. See RUL-011."""


StealthIncreaseContext = StealthIncreaseProactiveContext | StealthIncreaseDuringBlockContext


class StealthModifierContext(_StealthInterceptContext):
    """`offer` to `actor` while the block would succeed. `apply` returns the
    `int` stealth added. See ENG-003, RUL-009."""


class InterceptModifierContext(_StealthInterceptContext):
    """`offer` to `defender` while the block would fail. `apply` returns the
    `int` intercept added."""


class ForceBlockAttemptFailureContext(_StealthInterceptContext):
    """`offer` to `actor` once a blocker is fixed, whichever side the numbers
    favour; choosing one fails the attempt. See ENG-045."""


# --- combat and damage ---


class _CombatantContext(TypedDict):
    player: str
    vampire: str
    opponent: str


class CombatStrikeOptionContext(_CombatantContext):
    """`offer` at each combatant's strike choice. `apply` returns a
    `StrikeDamage` (an `int` is plain normal damage). See ENG-046, ENG-048."""

    combat_state: CombatState


class CombatStrengthModifierContext(_CombatantContext):
    """`sum_modifiers` on every hand-strike strength read; `combat_state` is
    `None` outside `run_combat`. A provider returns an `int`. See ENG-046."""

    combat_state: CombatState | None


class CombatDodgeOptionContext(_CombatantContext):
    """`offer` beside `COMBAT_STRIKE_OPTION`; a chosen dodge deals no damage and
    voids the opposing strike unless it ignores dodge. See ENG-012, ENG-048."""

    round_state: RoundState


class CombatAdditionalStrikeContext(_CombatantContext):
    """`offer` after the strike pair; using one gives that combatant another
    strike choice this round. See ENG-012, ENG-013."""

    round_state: RoundState


class ManeuverContext(_CombatantContext):
    """`offer` in Determine Range, acting side first, until two declines. A
    bundled strike calls `commit_strike_for_round`. See ENG-019, RUL-008."""

    combat_state: CombatState
    round_state: RoundState


class _CombatWindowContext(TypedDict):
    player: str
    acting_player: str
    acting_vampire: str
    blocking_player: str
    blocking_vampire: str


class BeforeRangeContext(_CombatWindowContext):
    """`resolve_impulse_window`, acting side first, once per combat before
    round 1. `apply` return ignored. See ENG-029, RUL-002."""

    combat_state: CombatState


class EndOfRoundContext(_CombatWindowContext):
    """`resolve_impulse_window`, acting side first, once per round on every
    exit path. `apply` return ignored. See ENG-020, RUL-002."""

    round_state: RoundState


class DamagePreventionContext(TypedDict):
    """`offer_until_pass` to the damaged vampire's controller. `apply` lowers
    `damage["normal"]`/`damage["aggravated"]` in place. See ENG-036, ENG-040."""

    player: str
    vampire: str
    damage: dict[str, int]
    round_state: RoundState | None
    combat_state: CombatState | None


class VampireEntersTorporContext(TypedDict):
    """`run_effects` the instant a vampire goes to torpor; `vampire` is the
    live object, safe since only card code reads it (Fame)."""

    player: str
    vampire: VampireInPlay


class DiablerieContext(TypedDict):
    """`resolve_impulse_window`, the diablerist's controller first, after
    diablerie and before the Blood Hunt. `apply` return ignored."""

    player: str
    diablerist: str
    victim: str
    victim_player: str


# --- passive vampire and player values ---


class CapacityModifierContext(TypedDict):
    """`sum_modifiers`: an always-on capacity bonus. A provider returns an
    `int`."""

    vampire: str


class DisciplineLevelModifierContext(TypedDict):
    """`union_modifiers`, read by `effective_disciplines`. A provider returns
    discipline codes (`"cel"` basic, `"CEL"` superior). See ENG-002, ENG-047."""

    vampire: str


class HandSizeModifierContext(TypedDict):
    """`sum_modifiers`, read by `effective_hand_size` on every call. A provider
    returns a signed `int`."""

    player: str


# --- politics ---


class PollingStepBeforeCastContext(TypedDict):
    """`resolve_impulse_window`, caller first, before any vote is cast. `apply`
    records vote changes in `pending`. See RUL-005."""

    player: str
    phase: Literal["before_cast"]
    caller: str
    caller_vampire_id: str
    pending: Pending


class PollingStepMidCastContext(TypedDict):
    """`offer` on each casting turn, beside the vote sources. `apply` returns
    the `source_id` of the cast it cancels. See ENG-027."""

    player: str
    phase: Literal["mid_cast"]
    caller: str
    caller_vampire_id: str
    other: str
    votes_for: int
    votes_against: int
    casts: list[VoteCast]
    pending: Pending


PollingStepContext = PollingStepBeforeCastContext | PollingStepMidCastContext


class VoteSourceCastBonusContext(TypedDict):
    """`sum_modifiers` as one vote source is cast. A provider returns an `int`
    added to that cast. See ENG-031."""

    caster: str
    burns_edge: bool
    burns_pac_from_hand: bool
    direction: str


class VoteAgainstPoolCostContext(TypedDict):
    """`sum_modifiers` before `player` may cast against. A provider returns the
    pool they would lose later; it gates the choice only. See DES-009."""

    player: str
    caller_vampire: VampireInPlay
    casts: list[VoteCast]


class ReferendumTalliedContext(TypedDict):
    """`run_effects` once votes are tallied, before pass/fail effects.
    Providers mutate `state`. See RUL-005."""

    caller: str
    other: str
    caller_vampire: VampireInPlay
    votes_for: int
    votes_against: int
    casts: list[VoteCast]


class ReferendumResolvedContext(TypedDict):
    """`resolve_impulse_window`, caller first, after a passed political
    action's referendum fully resolves, combat included. See ENG-026."""

    player: str
    caller: str
    other: str
    caller_vampire_id: str
    margin: int
    pending: Pending


# --- cancel as played ---


class CancelAsPlayedContext(TypedDict):
    """`offer` to the other side by `apply_chosen_option` (before `apply`) and
    after an action card's `apply` (ENG-037); also carries the origin window's
    keys (open context). See ENG-022, ENG-023."""

    player: str
    canceled_by: str
    canceled_choice: str
    canceled_card_type: str | None


HOOK_CONTEXTS: dict[Hook, type | UnionType] = {
    Hook.MASTER_PHASE_PLAY: MasterPhasePlayContext,
    Hook.MASTER_PHASE_ABILITY: MasterPhaseAbilityContext,
    Hook.INFLUENCE_PHASE_ACTION: InfluencePhaseActionContext,
    Hook.UNLOCK_PHASE_MANDATORY_EFFECT: UnlockPhaseMandatoryEffectContext,
    Hook.RECRUIT_ALLY_PLAY: RecruitAllyPlayContext,
    Hook.ACTION_CARD_PLAY: ActionCardPlayContext,
    Hook.ATTACHMENT_REMOVAL_ACTION_PLAY: AttachmentRemovalActionPlayContext,
    Hook.CANNOT_HUNT: CannotHuntContext,
    Hook.BLEED_AMOUNT_FIXED_MODIFIER: BleedAmountFixedModifierContext,
    Hook.BLEED_AMOUNT_MODIFIER: BleedAmountModifierContext,
    Hook.ACTION_SUCCEEDED: ActionSucceededContext,
    Hook.BLOCK_CANDIDATE_EXCLUSION: BlockCandidateExclusionContext,
    Hook.WAKE_LOCKED_MINION: WakeLockedMinionContext,
    Hook.BLOCK_CANDIDATE_INJECTION: BlockCandidateInjectionContext,
    Hook.BLOCK_ATTEMPT_COST: BlockAttemptCostContext,
    Hook.INTERCEPT_DECREASE: InterceptDecreaseContext,
    Hook.STEALTH_INCREASE: StealthIncreaseContext,
    Hook.STEALTH_MODIFIER: StealthModifierContext,
    Hook.INTERCEPT_MODIFIER: InterceptModifierContext,
    Hook.FORCE_BLOCK_ATTEMPT_FAILURE: ForceBlockAttemptFailureContext,
    Hook.COMBAT_STRIKE_OPTION: CombatStrikeOptionContext,
    Hook.COMBAT_STRENGTH_MODIFIER: CombatStrengthModifierContext,
    Hook.COMBAT_DODGE_OPTION: CombatDodgeOptionContext,
    Hook.COMBAT_ADDITIONAL_STRIKE: CombatAdditionalStrikeContext,
    Hook.MANEUVER: ManeuverContext,
    Hook.BEFORE_RANGE: BeforeRangeContext,
    Hook.END_OF_ROUND: EndOfRoundContext,
    Hook.DAMAGE_PREVENTION: DamagePreventionContext,
    Hook.VAMPIRE_ENTERS_TORPOR: VampireEntersTorporContext,
    Hook.DIABLERIE: DiablerieContext,
    Hook.CAPACITY_MODIFIER: CapacityModifierContext,
    Hook.DISCIPLINE_LEVEL_MODIFIER: DisciplineLevelModifierContext,
    Hook.HAND_SIZE_MODIFIER: HandSizeModifierContext,
    Hook.POLLING_STEP: PollingStepContext,
    Hook.VOTE_SOURCE_CAST_BONUS: VoteSourceCastBonusContext,
    Hook.VOTE_AGAINST_POOL_COST: VoteAgainstPoolCostContext,
    Hook.REFERENDUM_TALLIED: ReferendumTalliedContext,
    Hook.REFERENDUM_RESOLVED: ReferendumResolvedContext,
    Hook.CANCEL_AS_PLAYED: CancelAsPlayedContext,
}

OPEN_CONTEXTS: frozenset[Hook] = frozenset({Hook.CANCEL_AS_PLAYED})
"""Hooks whose context may carry undeclared keys (PEP 728 `extra_items` is not
in Python 3.14's `typing`)."""


def context_phases(hook: Hook) -> tuple[Any, ...]:
    """The `TypedDict` classes a context of `hook` may match, one per phase."""
    declared = HOOK_CONTEXTS[hook]
    return get_args(declared) or (declared,)


def _key_specs(hook: Hook) -> tuple[tuple[frozenset[str], frozenset[str] | None], ...]:
    open_ = hook in OPEN_CONTEXTS
    return tuple(
        (
            frozenset(phase.__required_keys__),
            None if open_ else phase.__required_keys__ | phase.__optional_keys__,
        )
        for phase in context_phases(hook)
    )


_KEY_SPECS = {hook: _key_specs(hook) for hook in HOOK_CONTEXTS}
_HOOK_VALUES = frozenset(Hook)
_CHECKED: set[tuple[str, ...]] = set()  # (hook, *keys) signatures already accepted


def check_context(hook: Hook, context: Mapping[str, Any]) -> None:
    """Raise `TypeError` unless `context`'s keys fit one phase of `hook`'s
    declared context: every required key, no undeclared one."""
    signature = (hook, *context)
    if signature in _CHECKED:
        return
    specs = _KEY_SPECS.get(hook)
    if specs is None:
        if hook in _HOOK_VALUES:
            raise TypeError(f"hook {hook!r} has no declared context (UNWIRED_HOOKS?)")
        return  # not a `Hook` member: a test-local hook name
    keys = context.keys()
    for required, allowed in specs:
        if required <= keys and (allowed is None or keys <= allowed):
            _CHECKED.add(signature)
            return
    raise TypeError(
        f"{hook!r} context keys {sorted(keys)} fit none of "
        f"{[phase.__name__ for phase in context_phases(hook)]}"
    )
