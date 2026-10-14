"""The card implementation registry.

CLAUDE.md SS6: "A card is implemented only when: effect code + test(s)
covering its text and each known ruling + registry entry + listed in the
active 2P list." The `implement-card` skill's step 6 ("Register") and the
`card-implementer` agent's output contract both name exactly two statuses,
`"implemented"` and `"blocked"` -- a card with neither is simply not yet
attempted (no registry entry at all; that is the normal, unremarkable state
for most of the pool after this scaffolding pass, not an error).

A card module (`src/vtesbot/cards/<snake_case_name>.py`) registers itself
once, at import time, by calling `register(CardRegistration(...))`;
`src/vtesbot/cards/__init__.py` imports every such module so the
registration side effect always runs before any code queries this registry
or `engine/hooks.py` (see `docs/DECISIONS.md` D-5 for why this is a static,
process-wide catalogue and not `GameState`).

`krcg_id` is the registry key (crypt vampire abilities and library cards
share the same krcg id space and the same registry -- a printed vampire
ability is exactly as much "a card" for this purpose as a library card,
CLAUDE.md SS5/SS6).
"""

from dataclasses import dataclass
from enum import StrEnum


class Status(StrEnum):
    IMPLEMENTED = "implemented"
    BLOCKED = "blocked"


class Hook(StrEnum):
    """Engine hook points a card's effect module may register against.

    Mirrors the hook names actually wired in `engine/hooks.py` call sites,
    plus a few named-but-not-yet-wired categories kept here purely for
    classification (CLAUDE.md milestone-3 scaffolding pass report) until a
    future rules-engineer pass builds their engine-side wiring.
    """

    # Wired this pass (engine/hooks.py has a real call site):
    MASTER_PHASE_PLAY = "master_phase_play"
    INFLUENCE_PHASE_ACTION = "influence_phase_action"
    """A card-sourced, transfer-costed option offered during the Influence
    phase (`engine/phases/influence.py::influence_phase`), alongside the
    three hardcoded transfer types (add blood, remove blood, bring a crypt
    card to the uncontrolled region) -- resolves `docs/OPEN_QUESTIONS.md`
    OQ-24. A provider's `HookOption.apply(state)` must return the `int`
    number of transfers consumed."""
    STEALTH_MODIFIER = "stealth_modifier"
    INTERCEPT_MODIFIER = "intercept_modifier"
    INTERCEPT_DECREASE = "intercept_decrease"
    """Acting-side Action Modifier reducing a blocking candidate's
    intercept, offered to `actor` both proactively (top of `engine/
    action.py::attempt_block`'s retry loop) and reactively (merged into
    `_duel_stealth_intercept`'s `STEALTH_MODIFIER` decision) --
    `docs/OPEN_QUESTIONS.md` OQ-30/OQ-31 (both resolved; OQ-31 needed the
    project owner's own ruling on the reactive point). A provider appends
    an `ActiveInterceptDecrease(delta, qualifies)` to `pending[engine/
    action.py::PENDING_INTERCEPT_DECREASE_KEY]`, re-evaluated against
    whichever candidate is fixed on every call; `apply()`'s return value is
    ignored."""
    STEALTH_INCREASE = "stealth_increase"
    """`INTERCEPT_DECREASE`'s sibling for the acting side's own stealth,
    offered at the same two points (`docs/OPEN_QUESTIONS.md` OQ-39,
    resolved -- built for Loup, krcg id 102273, whose on-file ruling "[c]an
    be used even if the stealth is not currently needed" the old
    `STEALTH_MODIFIER`-only wiring could not reach without a block attempt
    in progress). A provider appends an `ActiveStealthIncrease(delta)` to
    `pending[engine/action.py::PENDING_STEALTH_INCREASE_KEY]`; no
    `qualifies` predicate, since stealth is a per-action value, never
    candidate-dependent the way intercept is; `apply()`'s return value is
    ignored."""
    WAKE_LOCKED_MINION = "wake_locked_minion"
    """Defender-side sibling of `INTERCEPT_DECREASE`/`STEALTH_INCREASE` above --
    offered to `defender` (never `actor`), at the same top-of-retry-loop
    moment in `engine/action.py::attempt_block`, strictly before
    `state.ready_unlocked_vampires(defender)` is computed each time around
    (`docs/OPEN_QUESTIONS.md` OQ-48, resolved). Built for On the Qui Vive
    (krcg id 101321, Reaction): "Only usable by a locked minion ... This
    minion wakes (they ignore the requirement to be unlocked for ... attempting
    to block ... until the end of the action)" -- the primary clause, distinct
    from the "playing reaction cards" eligibility half OQ-46's own
    `VampireInPlay.woken` already covers everywhere else (every existing
    reaction-card provider's own hardcoded `is_ready_unlocked` check). A
    provider's `HookOption.apply(state)` return value is ignored by the
    caller, the same "no return value needed, `apply` just mutates state"
    contract as its two acting-side siblings -- it need only set `woken =
    True` (`engine/state.py::VampireInPlay`) on one of `defender`'s own
    locked vampires, which `ready_unlocked_vampires`/`attempt_block` then
    pick up for free, with no injection or unconditional-success shortcut
    (unlike `BLOCK_CANDIDATE_INJECTION`, rejected for this card -- OQ-48's own
    write-up) -- the woken vampire is a fully ordinary candidate, still
    subject to the normal stealth/intercept ping-pong. A provider waking an
    *ally* instead (On the Qui Vive's own ally footnote: "If this minion is
    an ally, they do not unlock as normal during their next unlock phase")
    sets `AllyInPlay.skip_next_unlock = True` (OQ-46's own field, reused, not
    duplicated) from the same `apply` -- allies are never offered as block
    candidates in this engine (out of scope, OQ-46's own solution note), so
    that branch matters only for a future ally-side use of this same hook
    outside the block-attempt path, not for `attempt_block` itself."""
    BLEED_AMOUNT_MODIFIER = "bleed_amount_modifier"
    BLEED_AMOUNT_FIXED_MODIFIER = "bleed_amount_fixed_modifier"
    DAMAGE_PREVENTION = "damage_prevention"
    COMBAT_STRIKE_OPTION = "combat_strike_option"
    COMBAT_STRENGTH_MODIFIER = "combat_strength_modifier"
    COMBAT_DODGE_OPTION = "combat_dodge_option"
    """A card/ability-granted dodge, offered alongside `COMBAT_STRIKE_OPTION`
    at the strike step (`engine/combat.py::_ask_strike`). Choosing it always
    deals 0 damage and zeroes whatever damage the opponent's simultaneous
    strike this round would otherwise deal to the dodging combatant
    (`engine/combat.py::_resolve_one_strike`/`_resolve_strike_pair`) --
    resolves `docs/OPEN_QUESTIONS.md` OQ-18 Gap 2."""
    COMBAT_ADDITIONAL_STRIKE = "combat_additional_strike"
    """A card/ability-granted extra strike this round, offered after the
    normal strike pair (and after each additional-strike pair) via
    `engine/combat.py::_ask_additional_strike`; using one re-enters the full
    strike-choice machinery (`COMBAT_STRIKE_OPTION`/`COMBAT_DODGE_OPTION`
    included) for that combatant's additional strike -- resolves
    `docs/OPEN_QUESTIONS.md` OQ-18 Gap 2."""
    CAPACITY_MODIFIER = "capacity_modifier"
    DISCIPLINE_LEVEL_MODIFIER = "discipline_level_modifier"
    HAND_SIZE_MODIFIER = "hand_size_modifier"
    """Passive, mandatory numeric hook (`hooks.sum_modifiers` contract, same
    shape as `CAPACITY_MODIFIER` above) wired by `engine/hand.py::
    effective_hand_size`, called from `reconcile_hand_size`'s own call sites
    (`vtesbot.cards._shared.play_from_hand_pending`, `engine/phases/
    discard.py::discard_phase`). A provider contributes a signed `int` delta
    to the base `FormatConfig.hand_size` (default 7) and must re-check its
    own triggering condition every call rather than caching a prior answer,
    since the motivating case -- Carmelita Neillson, krcg id 201625,
    "Camarilla: While Carmelita is ready, you get +1 hand size" -- is a
    continuously re-evaluated condition (her own `zone`/`locked`), not a
    one-shot effect. Not a ruling gap: plain milestone-2 engine-skeleton
    work (Rulebook SS2 Card Types > Drawing Cards), no Open Question
    attached. Carmelita's own effect module (registering a provider here)
    is a separate, later `card-implementer` pass."""
    RECRUIT_ALLY_PLAY = "recruit_ally_play"
    ACTION_CARD_PLAY = "action_card_play"
    """A library card of type "Action" (not "Action Modifier") that itself
    constitutes the acting minion's one action for the turn, distinct from
    `RECRUIT_ALLY_PLAY` (Ally-specific). Wired by `engine/phases/minion.py::
    ACTION_CARD_PLAY_HOOK` / `_perform_action_card`, generalizing the
    `RECRUIT_ALLY_PLAY` pattern beyond Allies -- see `docs/OPEN_QUESTIONS.md`
    OQ-17 (resolved)."""
    REFERENDUM_TALLIED = "referendum_tallied"
    """A mandatory, non-chosen per-provider reaction fired once a
    referendum's votes are tallied (`engine/politics.py::resolve_referendum`,
    dispatched via `hooks.run_effects` -- no `Decision`, since there is
    nothing for a player to choose), *before* the referendum's own pass/fail
    effects take place -- distinct from, and earlier than,
    `REFERENDUM_RESOLVED` below. This is the hook site Marcos Belegrad's
    "burn 1 pool once results are tallied" (`docs/OPEN_QUESTIONS.md` OQ-6)
    needs; no provider is registered against it yet, so this call site
    changes no behaviour today."""
    VAMPIRE_ENTERS_TORPOR = "vampire_enters_torpor"
    """A mandatory, non-chosen per-provider reaction fired the instant any
    vampire's `zone` flips to `"torpor"` (`engine/damage.py::send_to_torpor`,
    the single call site every vampire's zone transitions through),
    dispatched via `hooks.run_effects` -- no `Decision`, since there is
    nothing for a player to choose. Added resolving `docs/OPEN_QUESTIONS.md`
    OQ-22's own remaining "still needed" clause 2 for Fame (100698, "After
    this vampire goes to torpor, their controller burns 3 pool"), the first
    production user of this hook."""
    UNLOCK_PHASE_MANDATORY_EFFECT = "unlock_phase_mandatory_effect"
    """A mandatory, non-chosen per-provider reaction fired once per
    `engine/phases/unlock.py::unlock_phase` call, for the unlocking player
    (not necessarily the reacting card's own controller) -- dispatched via
    `hooks.run_effects` -- no `Decision`, since there is nothing to choose.
    Distinct from the optional pay-or-yield pending-effect loop in the same
    phase (`"contest:"`/`"contest_ally:"`/`"contest_attachment:"`, each of
    which *does* offer a real choice): this hook is for an effect with no
    legal alternative at all. Added resolving `docs/OPEN_QUESTIONS.md` OQ-22's
    own remaining "still needed" clause 3 for Fame (100698, "During each
    Methuselah's unlock phase, if this vampire is in torpor, that Methuselah
    burns 1 pool"), the first production user of this hook."""
    MANEUVER = "maneuver"
    """A card/printed-ability-granted maneuver, offered during the Determine
    Range step (`engine/combat.py::_ask_maneuver`/`_determine_range`, before
    the strike step each round) -- acting combatant's controller offered
    first, strictly alternating turn by turn (Rulebook SS4 Combat >
    Determine Range's "A minion cannot play two maneuvers in a row" is
    enforced by this alternation, not a provider-side check), closing once
    two consecutive turns both decline/have nothing. Covers both a plain
    ability-granted maneuver not bundled with choosing a strike (Saku
    Pihlajamäki, Pursuit's basic clause -- OQ-27, resolved) and a maneuver
    genuinely "from a strike" (Slam, .44 Magnum -- OQ-28, resolved): a
    provider of the latter shape must also call `engine/combat.py::
    commit_strike_for_round` from its grant's `apply`-time closure, fixing
    that combatant's initial strike of the round to the same bundled strike
    effect (Rulebook SS4 Combat > Strike > Choose Strike: "If a minion has
    used a maneuver from a strike ... this round, then they cannot choose
    any other strike for their initial strike of the round") -- see
    `engine/combat.py` module docstring's "Maneuver bundled with a strike"
    section for the mechanism; a plain-maneuver provider never calls it.
    `context["combat_state"]` carries the shared, combat-scoped scratch
    dict for a once-per-combat grant like Saku's; `context["round_state"]`
    carries the round-scoped scratch dict `commit_strike_for_round` writes
    into."""
    END_OF_ROUND = "end_of_round"
    """Rulebook SS4 Combat > Combat Sequence, step 7, "End of Round: End of
    round cards and effects are played here" -- dispatched once per round by
    `engine/combat.py::run_combat` (via `_ask_end_of_round`), on every path
    out of a round's own processing: a normal end (nobody pressed), a
    premature end (a combatant went not-ready before the Press step was even
    reached), and the "someone pressed, another round follows" case alike.
    Modeled as the engine's standard two-sided impulse window (CLAUDE.md rule
    4 / Rulebook SS2 Sequencing, `hooks.resolve_impulse_window`) -- acting
    combatant's controller offered first, same ordering precedent as Press
    (`engine/combat.py` module docstring, OQ-3) -- not `_ask_press`'s own
    narrower "ask once, first yes wins" shape, since an end-of-round card
    effect is a real window where either side may act (and re-act) an
    arbitrary number of times, not a single binary decision. Added resolving
    `docs/OPEN_QUESTIONS.md` OQ-29's mechanism 1 (Taste of Vitae, krcg id
    101945, "Only usable at the end of a round of combat"). `context["round_
    state"]` (`engine/combat.py::ROUND_STATE_CONTEXT_KEY`) carries the same
    round-scoped scratch dict threaded into every other combat hook this
    round -- including, as of the same pass, `engine/damage.py::apply_damage`'s
    own "blood lost to damage this round" record (`engine/damage.py::
    blood_lost_to_damage_this_round`, OQ-29 mechanism 2)."""
    BEFORE_RANGE = "before_range"
    """Rulebook SS4 Combat > Combat Sequence, step 1, "Before Range: Play
    cards before range is chosen" -- offered exactly once per combat, by
    `engine/combat.py::run_combat` (via `_ask_before_range`), immediately
    before round 1's own Determine Range step, never again on a later round
    of the same combat. Modeled as the engine's standard two-sided impulse
    window (`hooks.resolve_impulse_window`), acting combatant's controller
    offered first (same ordering precedent as Press/End of Round/Determine
    Range, `engine/combat.py` module docstring, OQ-3) -- resolves `docs/
    OPEN_QUESTIONS.md` OQ-47 (Weighted Walking Stick, krcg id 102169, "Only
    usable before range is determined during the first round"). A
    provider's own `apply(state)` attaches a card directly (e.g. via
    `engine/attachments.py::attach_card` or a direct `engine/cards.py::
    CardAttachment` construction, mirroring `cards/celerity.py`'s own
    non-unique-attachment pattern) -- no new contract for the strike half
    of such a card: `COMBAT_STRIKE_OPTION`'s existing provider contract
    (pre-prevention, post-reduction damage) already supplies everything "for
    each damage inflicted ... even if prevented" needs."""
    ACTION_SUCCEEDED = "action_succeeded"
    """A mandatory, non-chosen per-provider reaction fired once a minion
    action goes unblocked and its own `resolve()` returns (`engine/
    action.py::perform_minion_action`, dispatched via `hooks.run_effects` --
    no `Decision`), independent of whether the action's own effect did
    anything (Rulebook SS4 "Resolve the Action": "successful" means purely
    "not blocked") -- resolves `docs/OPEN_QUESTIONS.md` OQ-34, built for
    Loup (krcg id 102273, "Burn this card ... after a Toreador performs a
    successful action"). Context carries `actor_player`, the acting
    `vampire` (the live object, not merely its id -- this is trusted
    engine-internal code, the same tier `VAMPIRE_ENTERS_TORPOR`'s own
    `vampire` context entry already established) and `action` (the OQ-9
    discriminator)."""
    CANCEL_AS_PLAYED = "cancel_as_played"
    """Generic "cancel a card as it is played" interception point (`docs/
    OPEN_QUESTIONS.md` OQ-32, resolved): offered to the side *not* making a
    choice, right after any `HookOption` is chosen through either generic
    decision-loop helper (`engine/hooks.py::offer_until_pass`/
    `resolve_impulse_window`, via the new `apply_chosen_option`), before
    that option's own `apply` runs. A provider's own chosen `HookOption.
    apply(state)` pays its own cost (e.g. Diana Iadanza's "burn 1 blood")
    and suppresses the original option's `apply` entirely; the original
    option's own `HookOption.cost` (if it sets one) has already run by
    then, independent of cancellation, so "cost is still paid" holds
    generically. No provider is registered against this hook yet (zero
    behaviour change today, true of every hook before its first
    provider -- see `engine/hooks.py` module docstring); Diana Iadanza's
    own clause 1 (`src/vtesbot/cards/diana_iadanza.py`, still `blocked`)
    still needs a `card-implementer` pass to register against it."""
    # Named for classification; no engine wiring exists yet (see the
    # rules-engineer milestone-3 scaffolding report for what each needs):
    POLITICAL_ACTION = "political_action"
    POLLING_STEP = "polling_step"
    """Wired in `engine/politics.py` (OQ-6): a `"before_cast"`-phase window
    before casting begins (Perfect Paragon/Queen Anne/Oxford University,
    England's own shapes), and -- since OQ-37 (`docs/OPEN_QUESTIONS.md`,
    resolved) -- also a `"mid_cast"`-phase window merged into each player's
    own per-turn vote-casting `Decision` inside `_cast_votes`, for a card
    like Scalpel Tongue (krcg id 101686) that retroactively cancels an
    already-cast source. The two phases share one hook name but differ in
    what `HookOption.apply(state)` must return -- see `_cast_votes`'s own
    docstring."""
    REFERENDUM_RESOLVED = "referendum_resolved"
    """A moment strictly *after* a political action's referendum has fully
    resolved -- including any pass effects and any combat from a blocked
    attempt -- distinct from, and later than, the pre-cast `POLLING_STEP`
    and the during-tally `REFERENDUM_TALLIED` above. Dispatch call site
    (OQ-36, `docs/OPEN_QUESTIONS.md`, resolved): `engine/action.py::
    perform_minion_action`, right after its own `resolve(pending)` call
    returns, offered as a real two-sided `Decision`-raising window
    (`hooks.resolve_impulse_window`), only when `action ==
    ACTION_POLITICAL` and the referendum passed. This is Voter
    Captivation's own trigger moment ("[o]nly usable after resolution of a
    political action whose referendum passed" -- `docs/OPEN_QUESTIONS.md`
    OQ-6); do not wire a future provider for it against `POLLING_STEP` or
    `REFERENDUM_TALLIED` instead, since neither has a vote margin or final
    pass/fail state available at the moment it fires. Voter Captivation's
    own card module (`src/vtesbot/cards/voter_captivation.py`) is now
    implemented against this dispatch; see its own docstring for the
    per-vampire once-per-action cap added there (`rules-auditor`
    finding)."""
    VOTE_SOURCE_CAST_BONUS = "vote_source_cast_bonus"
    """Passive, mandatory numeric hook (`hooks.sum_modifiers` contract, same
    shape as `CAPACITY_MODIFIER`/`HAND_SIZE_MODIFIER` above), dispatched by
    `engine/politics.py::_cast_votes` the instant a specific `VoteSource` is
    actually cast -- after that source's own cast-time side effects
    (`burns_edge`/`burns_pac_from_hand`) run, before its votes are added to
    `votes_for`/`votes_against` and logged into `casts`. Resolves `docs/
    OPEN_QUESTIONS.md` OQ-49 (Fiorenza Savona, krcg id 201616: "If you burn
    the Edge for a vote, you get +1 vote. If you burn a political action
    card for a vote, you get +1 vote."), the first production user -- a
    conditional bonus *of* a specific other source's own cast, which neither
    `POLLING_STEP_HOOK` phase can express (`"before_cast"` only adds an
    independent new source; `"mid_cast"` only cancels one) and which
    `REFERENDUM_TALLIED_HOOK` fires too late to feed back into the tally
    that already decided pass/fail. Context: `caster` (`source.player`,
    whoever is casting -- never the live vampire, information hiding),
    `burns_edge`/`burns_pac_from_hand` (the cast source's own flags, so a
    provider can tell which of the two printed clauses applies without
    needing the `source_id` string format), and `direction` (`"for"`/
    `"against"`, for a future provider that cares -- Fiorenza's own does
    not, since the bonus is added to whichever direction the source itself
    was cast in, uniformly, by the call site). A provider's returned `int`
    is folded directly into that one cast's own total (which is also what
    gets logged into `casts` and what a later OQ-37 mid-cast cancellation of
    the *same* source retroactively subtracts back out) -- never a separate
    side-channel, so cancellation bookkeeping stays correct with no special
    case."""
    RANGED_STRIKE = "ranged_strike"
    ALLY_ENTITY = "ally_entity"
    LOCATION_ENTITY = "location_entity"
    """A generic "location" entity concept Disputed Territory (krcg id
    100557, "Successful referendum means the chosen Methuselah takes
    control of the chosen location") needs -- resolved (OQ-35, `docs/
    OPEN_QUESTIONS.md`) not by a new entity (OQ-23 already found "location"
    is free text on an ordinary standalone Master card or an attached
    Equipment, not a distinct krcg type) but by two generic control-transfer
    primitives over the two existing shapes that can carry one:
    `engine/attachments.py::transfer_attachment_control` (always re-hosts,
    per the "on another controlled card" ruling) and `engine/master_cards.py
    ::transfer_master_card_control` (never re-hosts: a standalone card is
    never "on" anything). Disputed Territory (`cards/disputed_territory.py`)
    is now implemented against the latter primitive only -- no "equipment
    representing a location" card is on the active 2P list -- so its own
    registration does not cite this value, mirroring Oxford University,
    England's own choice not to cite it either (that module's docstring)."""
    DIABLERIE = "diablerie"
    BLOCK_CANDIDATE_INJECTION = "block_candidate_injection"
    EQUIPMENT_ATTACHMENT = "equipment_attachment"


@dataclass(frozen=True)
class CardRegistration:
    krcg_id: int
    name: str
    status: Status
    hooks: tuple[Hook, ...]
    source: str
    """Short provenance note: the module path, or (for a card not yet
    implemented) a one-line description of what blocks it."""
    blocked_reason: str | None = None
    """An `OQ-<n>` id (`docs/OPEN_QUESTIONS.md`) when `status is Status.BLOCKED`."""


_REGISTRY: dict[int, CardRegistration] = {}


def register(reg: CardRegistration) -> CardRegistration:
    if reg.krcg_id in _REGISTRY:
        raise ValueError(f"card {reg.krcg_id} ({reg.name!r}) is already registered")
    if reg.status is Status.BLOCKED and not reg.blocked_reason:
        raise ValueError(f"card {reg.krcg_id} ({reg.name!r}) is blocked but has no blocked_reason")
    _REGISTRY[reg.krcg_id] = reg
    return reg


def get(krcg_id: int) -> CardRegistration | None:
    return _REGISTRY.get(krcg_id)


def all_registrations() -> tuple[CardRegistration, ...]:
    return tuple(_REGISTRY.values())


def implemented_ids() -> frozenset[int]:
    return frozenset(r.krcg_id for r in _REGISTRY.values() if r.status is Status.IMPLEMENTED)


def blocked_ids() -> frozenset[int]:
    return frozenset(r.krcg_id for r in _REGISTRY.values() if r.status is Status.BLOCKED)


def remove(krcg_id: int) -> None:
    """Test isolation helper only; production code never calls this."""
    _REGISTRY.pop(krcg_id, None)


def clear() -> None:
    """Test isolation helper only; production code never calls this."""
    _REGISTRY.clear()
