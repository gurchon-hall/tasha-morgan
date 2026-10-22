"""Minion phase: default actions (bleed, hunt, recruit ally, action cards),
Rulebook §4. Mandatory hunt first; lock enforces one action per vampire
per turn. See ENG-003/ENG-005/ENG-006/ENG-011/RUL-007/ENG-017 below.

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
    ACTION_ATTACHMENT_REMOVAL,
    ACTION_BLEED,
    ACTION_DIABLERIE,
    ACTION_HUNT,
    ACTION_RECRUIT_ALLY,
    perform_minion_action,
)
from ..allies import detect_contest_on_recruit, recruit_ally
from ..combat import run_combat
from ..damage import add_blood, send_to_torpor
from ..decision import Choice, Decision
from ..diablerie import resolve_diablerie
from ..hand import draw_replacement_card
from ..hooks import Hook
from ..pool import lose_pool
from ..state import EnterCombatGrant

if TYPE_CHECKING:
    from ..allies import RecruitAllySpec
    from ..cards import CardAttachment
    from ..hooks import HookOption
    from ..state import GameState, VampireInPlay

BLEED_STEALTH = 0
BLEED_AMOUNT = 1
HUNT_STEALTH = 1
HUNT_BLOOD_GAIN = 1
DIABLERIE_STEALTH_SAME_CONTROLLER = 1
"""Rulebook §4 default action list, "Diablerise a Vampire in Torpor":
"+1 stealth, if the acting vampire and the vampire in torpor have the
same controller." """
DIABLERIE_STEALTH_OTHER_CONTROLLER = 0
"""Same source: "0 stealth, if ... different controllers." """
RECRUIT_ALLY_STEALTH = 1
"""Rulebook §4 Recruit Ally: "Default stealth: +1 stealth." """
RECRUIT_ALLY_PLAY_HOOK = Hook.RECRUIT_ALLY_PLAY
ACTION_CARD_PLAY_HOOK = Hook.ACTION_CARD_PLAY
BLEED_AMOUNT_MODIFIER_HOOK = Hook.BLEED_AMOUNT_MODIFIER
BLEED_AMOUNT_FIXED_MODIFIER_HOOK = Hook.BLEED_AMOUNT_FIXED_MODIFIER
PENDING_BLEED_AMOUNT_KEY = "bleed_amount_bonus"
"""Scratch-dict key (ENG-005): an earlier stealth/intercept provider in this
same bleed action stores a running bonus here; `_perform_bleed`'s `resolve`
folds it into `base_amount`."""


@dataclass(frozen=True)
class ActionCardSpec:
    """What an `action_card_play` hook option's `apply(state)` returns
    (ENG-011): base_stealth/directed, `resolve`/`on_blocked` callbacks,
    `action` discriminator (ENG-003), `maneuver_grant` (ENG-017),
    `block_candidate_predicate` (see below)."""

    base_stealth: int
    directed: bool
    resolve: Callable[[dict[str, Any]], None]
    on_blocked: Callable[[dict[str, Any]], None] | None = None
    action: str = ACTION_ACTION_CARD
    maneuver_grant: str | None = None
    block_candidate_predicate: Callable[[VampireInPlay], bool] | None = None
    """Forwarded unchanged to `engine/action.py::perform_minion_action`/
    `attempt_block` -- an unconditional, property-based block-candidate
    filter tied to *this action card's own printed text* (e.g.
    `cards/propaganda.py` krcg 101495, "Titled vampires cannot block this
    action"), seeded here because this is the one point an `ACTION_CARD_
    PLAY_HOOK` provider's `apply()` can hand a predicate to `perform_
    minion_action` before its own per-action `pending` dict even exists.
    Distinct from, and composes with, `BLOCK_CANDIDATE_EXCLUSION_HOOK`
    (an actor-chosen, per-vampire exclusion seeded reactively from inside
    `attempt_block`'s own retry loop) -- see `attempt_block`'s own
    docstring for how both are applied together."""
    name: str | None = None
    """The printed name of the library card this spec plays from hand, or
    `None` when nothing was actually played from hand (e.g.
    `build_enter_combat_action_spec`'s own default, used both by
    `cards/line_brawl.py`'s `[pot]` clause -- itself a real card play, which
    sets this explicitly -- and by `cards/lucinde_alastor.py`'s crypt-text
    grant consumer, which never plays a card at all and leaves it `None`).
    `_perform_action_card` uses this to drive two ENG-037 mechanisms, both
    gated on `name is not None`: the replacement-card draw (Finding 1) and the
    generic "same named action card at most once per turn" cap (Finding 2,
    `action_card_already_played_this_turn`/`mark_action_card_played_this_turn`
    below)."""


def build_enter_combat_action_spec(
    state: GameState,
    player: str,
    acting_vampire: VampireInPlay,
    opponent: str,
    target_vampire_id: str,
    *,
    name: str | None = None,
) -> ActionCardSpec:
    """Shared "Ⓓ Enter combat with a minion" resolution shape: the target is
    bound now (at `apply()` time, not deferred to `resolve()`), and
    `run_combat` runs against it only if the action goes unblocked -- see
    `cards/line_brawl.py`'s own `[pot]` clause docstring (RUL-007, resolved)
    for the full reasoning, worked out there first. `resolve()` treats a
    target that has left `zone == "ready"` between binding and resolve as
    "nothing to do" (fizzles), the same convention RUL-007 settled.

    Reused by any `ACTION_CARD_PLAY_HOOK` provider offering an equivalent
    "enter combat with this specific, already-bound target" option,
    regardless of what makes the option available: playing a card
    (`cards/line_brawl.py`'s `[pot]` clause, its first consumer, refactored
    onto this shared helper -- passes its own card's printed `name`) or a
    crypt text's own ability grant (`EnterCombatGrant`/`active_enter_combat_
    grants` below, e.g. `cards/lucinde_alastor.py`'s own consumer, which
    plays no card and leaves `name` at its default `None` -- ENG-037's
    `ActionCardSpec.name` contract). Callers
    remain responsible for their own eligibility gate on which vampire may
    use the option at all (mirrors `line_brawl.py`'s "Requires an Anarch"
    gate) -- this helper only builds the `ActionCardSpec` for a target
    already decided to be legal."""

    def resolve(pending: dict[str, Any]) -> None:
        del pending  # no later hook window of its own to feed.
        target = state.players[opponent].vampires.get(target_vampire_id)
        if target is None or target.zone != "ready":
            return  # fizzles (RUL-007); the target left "ready" since binding.
        run_combat(state, player, acting_vampire, opponent, target)

    return ActionCardSpec(base_stealth=0, directed=True, resolve=resolve, name=name)


ATTACHMENT_REMOVAL_ACTION_HOOK = Hook.ATTACHMENT_REMOVAL_ACTION_PLAY

ATTACHMENT_REMOVAL_STEALTH = 1
""""+1 stealth action" bare (no "Ⓓ" marker): undirected, baseline 0 (same
reading `RECRUIT_ALLY_STEALTH`'s own docstring gives for the Rulebook's
default-action-list "+1 stealth" bare phrasing, e.g. Recruit Ally/Employ
Retainer)."""


def build_attachment_removal_action_spec(
    attachment: CardAttachment, *, contributions_required: int
) -> ActionCardSpec:
    """Shared "+1 stealth action, cumulative across either side's vampires,
    removes a named attachment once `contributions_required` total
    contributions have been made" resolution shape. Sourced from Pulled
    Fangs (krcg 101515): "Any vampire(s) can burn this card with two +1
    stealth actions."; ruling "A total of two actions must be performed
    (by whomever) to remove it. Vampires A and B can both take the action,
    then it is removed." [ANK 20170202-2] -- confirming a contribution only
    counts once the action actually resolves unblocked (an action blocked
    this action-card-playing step never reaches `resolve()` at all, so it
    never contributes), and that either side's vampire may contribute, not
    only the attachment's own controller's.

    Reuses `CardAttachment.counters` (already a generic attachment-level
    running-count field, e.g. Weighted Walking Stick's own 5-ammo count) as
    the contribution tally instead of inventing a second one -- callers must
    not otherwise mutate `counters` on an attachment built against this
    helper. Distinct from a vampire's own `VampireInPlay.corruption_counters`
    (`engine/corruption.py`) -- corruption counters live on the minion
    itself, never on an attachment (see that field's own docstring); nothing
    using *that* keyword ever reuses this helper.
    `contributions_required` is caller-supplied (Pulled Fangs' own text
    names exactly two; this helper does not hardcode that number, since it
    is the calling card's own fact, not a rule of this mechanism).

    `resolve()` fizzles (no-op) if `attachment.zone != "attached"` by
    resolve time (RUL-007 convention: the attachment may have already been
    removed by a different, earlier-resolving contribution this same
    action-choice round)."""

    def resolve(pending: dict[str, Any]) -> None:
        del pending  # no later hook window of its own to feed.
        if attachment.zone != "attached":
            return  # fizzles (RUL-007 convention): already removed since binding.
        attachment.counters = (attachment.counters or 0) + 1
        if attachment.counters >= contributions_required:
            attachment.zone = "burned"

    return ActionCardSpec(
        base_stealth=ATTACHMENT_REMOVAL_STEALTH,
        directed=False,
        resolve=resolve,
        action=ACTION_ATTACHMENT_REMOVAL,
    )


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


CANNOT_HUNT_HOOK = Hook.CANNOT_HUNT


def minion_phase(state: GameState, player: str) -> None:
    other = state.other_player(player)

    # Mandatory actions first: a ready, unlocked vampire with no blood must hunt,
    # unless an attachment substitutes a forced torpor instead (CANNOT_HUNT_HOOK).
    for vampire in list(state.ready_unlocked_vampires(player)):
        if state.game_over:
            return
        if vampire.blood == 0 and vampire.is_ready_unlocked:
            if hooks.any_true(CANNOT_HUNT_HOOK, state, player=player, vampire=vampire.instance_id):
                send_to_torpor(state, player, vampire)
            else:
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


def _eligible_diablerie_targets(state: GameState, player: str, other: str) -> list[VampireInPlay]:
    """Rulebook §4 default action list, "Diablerise a Vampire in Torpor":
    "Default target: A vampire in torpor." -- both the acting player's own
    torpid vampires (undirected) and the opponent's (directed) are
    eligible by default; CLAUDE.md §3's 2P structural fact (the sole
    opponent is both prey and predator) means there is no third pool to
    consider."""
    return [
        v
        for v in (*state.players[player].vampires.values(), *state.players[other].vampires.values())
        if v.zone == "torpor"
    ]


def _choose_and_perform_action(
    state: GameState, player: str, other: str, vampire: VampireInPlay
) -> None:
    """Rulebook §4: offers default actions plus one choice per
    `recruit_ally_play` (ENG-006)/`action_card_play` (ENG-011) option; degrades
    to bleed/hunt alone when none offered (ENG-007 context). "Diablerise a
    Vampire in Torpor" is only offered while at least one legal target
    exists (never offer a play that cannot resolve -- `cards/line_brawl.py`'s
    `_eligible_combat_targets` precedent)."""
    recruit_options = hooks.offer(
        RECRUIT_ALLY_PLAY_HOOK, state, player=player, vampire=vampire.instance_id
    )
    action_card_options = hooks.offer(
        ACTION_CARD_PLAY_HOOK, state, player=player, vampire=vampire.instance_id
    )
    attachment_removal_options = hooks.offer(
        ATTACHMENT_REMOVAL_ACTION_HOOK, state, player=player, vampire=vampire.instance_id
    )
    recruit_by_value: dict[str, HookOption] = {o.choice.value: o for o in recruit_options}
    action_card_by_value: dict[str, HookOption] = {o.choice.value: o for o in action_card_options}
    attachment_removal_by_value: dict[str, HookOption] = {
        o.choice.value: o for o in attachment_removal_options
    }
    diablerie_choice = (
        (Choice(ACTION_DIABLERIE, "Diablerise a vampire in torpor"),)
        if _eligible_diablerie_targets(state, player, other)
        else ()
    )
    choices = (
        (Choice(ACTION_BLEED, "Bleed"), Choice(ACTION_HUNT, "Hunt"))
        + diablerie_choice
        + tuple(o.choice for o in recruit_options)
        + tuple(o.choice for o in action_card_options)
        + tuple(o.choice for o in attachment_removal_options)
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
    elif action == ACTION_DIABLERIE:
        _perform_diablerise(state, player, other, vampire)
    elif action in recruit_by_value:
        _perform_recruit_ally(state, player, other, vampire, recruit_by_value[action])
    elif action in attachment_removal_by_value:
        _perform_attachment_removal_action(
            state, player, other, vampire, attachment_removal_by_value[action]
        )
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
        # provider to feed (ENG-005 is specific to bleed's later
        # "bleed_amount_modifier" window); `pending` is accepted only to
        # match `perform_minion_action`'s shared `resolve` call-site
        # signature, and is otherwise unused here.
        del pending
        add_blood(state, vampire, HUNT_BLOOD_GAIN)

    perform_minion_action(
        state, player, other, vampire, HUNT_STEALTH, resolve, action=ACTION_HUNT, directed=False
    )


def _perform_diablerise(state: GameState, player: str, other: str, vampire: VampireInPlay) -> None:
    """Rulebook §4 default "Diablerise a Vampire in Torpor" (lines 380-404,
    `data/sources/rulebook/2026-10-09/4-detailed-turn-sequence.md`):
    undirected +1 stealth against the acting player's own torpid vampire,
    directed 0 stealth against the opponent's. The target is bound now, at
    announce time -- same "all terms fixed now" convention RUL-007 settled
    for `cards/line_brawl.py`'s `[pot]` clause -- so `resolve` below
    fizzles if the bound target has somehow left torpor by resolve time
    (no path to do so exists in this project yet, but the check is free
    and matches the project's own established convention for a bound
    target). Unblocked resolution calls `engine/diablerie.py::
    resolve_diablerie`; the blocked branch needs no special handling
    here -- `perform_minion_action`'s own internal `run_combat` call
    already is "the acting vampire and the blocking minion enter combat
    as normal" for free."""
    targets = _eligible_diablerie_targets(state, player, other)
    if len(targets) == 1:
        target = targets[0]
    else:
        choices = tuple(
            Choice(f"diablerise_target:{v.instance_id}", f"Diablerise {v.card.name}")
            for v in targets
        )
        decision = Decision(player=player, kind="diablerise_target", choices=choices)
        chosen_value = state.ask(decision).value
        chosen_id = chosen_value.split(":", 1)[1]
        target = next(v for v in targets if v.instance_id == chosen_id)

    target_player = target.controller
    target_id = target.instance_id
    same_controller = target_player == player
    stealth = (
        DIABLERIE_STEALTH_SAME_CONTROLLER if same_controller else DIABLERIE_STEALTH_OTHER_CONTROLLER
    )
    directed = not same_controller

    def resolve(pending: dict[str, Any]) -> None:
        del pending  # no later hook window of its own to feed.
        victim = state.players[target_player].vampires.get(target_id)
        if victim is None or victim.zone != "torpor":
            return  # fizzles (RUL-007 convention): target left torpor since binding.
        resolve_diablerie(state, player, vampire, target_player, victim)

    perform_minion_action(
        state, player, other, vampire, stealth, resolve, action=ACTION_DIABLERIE, directed=directed
    )


def _perform_recruit_ally(
    state: GameState,
    player: str,
    other: str,
    vampire: VampireInPlay,
    option: HookOption,
) -> None:
    """Rulebook §4 Recruit Ally: undirected, +1 stealth, ally's cost paid
    only on success, can't act this turn (ENG-006). Chosen hook option's ally
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
        # ENG-004 (resolved): a unique ally (printed
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


def action_card_already_played_this_turn(
    state: GameState, vampire: VampireInPlay, name: str
) -> bool:
    """ENG-037 Finding 2: Rulebook §4 Detailed Turn
    Sequence (`data/sources/rulebook/2026-10-09/4-detailed-turn-sequence.md:
    188-191`), "A minion cannot play (unless cancelled) the same named
    action card more than once each turn, even if they unlock." -- scoped
    to this one `vampire` ("a minion"), not every vampire its controller
    owns (a different vampire with its own physical copy may still play it
    this same turn). Called by an `ACTION_CARD_PLAY_HOOK` provider as a
    guard, alongside its own other eligibility checks (hand possession,
    blood cost, legal target, ...), so a second physical copy of an
    already-played-this-turn card is never even offered to the same
    vampire. See `VampireInPlay.action_card_played_turn`'s own docstring
    for the "why `name`, not `krcg_id`" reasoning."""
    return vampire.action_card_played_turn.get(name) == state.turn_number


def mark_action_card_played_this_turn(state: GameState, vampire: VampireInPlay, name: str) -> None:
    """Records `name` as played this turn for `vampire` -- call only once a
    play is confirmed *not* canceled (ENG-037 Finding 2: "unless cancelled",
    a canceled attempt must not count against the cap). The sole caller is
    `_perform_action_card`, after its own cancel-as-played window closes
    with no cancellation."""
    vampire.action_card_played_turn[name] = state.turn_number


def _perform_action_card(
    state: GameState,
    player: str,
    other: str,
    vampire: VampireInPlay,
    option: HookOption,
) -> None:
    """Rulebook §2+§4 (ENG-011): a printed Action-type card is itself the
    vampire's whole minion action. `option.apply(state)` removes the
    physical card from hand to the ash heap (`engine/hand.py::
    remove_from_hand`, re-exported from `cards/_shared.py` for card-module
    callers -- every real `ACTION_CARD_PLAY_HOOK` provider's own
    convention, ENG-037 Finding 1 below) and returns the `ActionCardSpec`
    forwarded to `perform_minion_action` unchanged, unless canceled first.

    ENG-037 Finding 1: between `option.apply`
    returning and `perform_minion_action` running -- i.e. strictly before
    `vampire.locked` is ever set for this action, the only "announce"
    commitment this action makes -- `other` is offered `hooks.CANCEL_
    AS_PLAYED_HOOK` via `hooks.offer_cancel_as_played` (Rulebook Advanced
    Rules "Reflex cards", `data/sources/rulebook/2026-10-09/
    2-card-types.md:323-326`). Only *after* that window closes --
    regardless of whether it resulted in a cancellation -- is the
    replacement card drawn (`engine/hand.py::draw_replacement_card`),
    per Rulebook §2 Card Types, "Library Cards" Advanced Rules
    (`2-card-types.md:124-126`):
    "Even drawing to replace cards, comes after this time period"; and per
    "Cancel a Card" (`3-playing-the-game.md:103`): "A cancelled card has no
    effect, but it is still considered played" -- being played, not
    succeeding, is what triggers the replacement draw, so it always runs
    for a real card play (`spec.name is not None`; `None` means nothing
    was played from hand at all, e.g. `cards/lucinde_alastor.py`'s own
    grant-consumption option, which must not draw a card it never removed).

    If canceled, `perform_minion_action` is skipped entirely:
    `3-playing-the-game.md:103-108`, "If an action card is cancelled, the
    minion does not lock (they do not pay for the action card), and they
    can play the same action card again." -- `vampire.locked` is never
    set (the only call site that sets it for this action is skipped), and
    the action card's own printed cost, which every `ActionCardSpec`-
    producing module pays only inside its own `resolve()` on the unblocked
    branch, is simply never reached.

    ENG-037 Finding 2: the per-turn-per-named-action-card cap above
    (`mark_action_card_played_this_turn`) is marked here, centrally, only
    once the cancel window has closed *without* a cancellation -- "unless
    cancelled" means a canceled attempt must not count against it, matching
    the rule's own carve-out and this function's own "they can play the
    same action card again" branch just above.

    This is a distinct mechanism from `hooks.apply_chosen_option` (ENG-022,
    built for a Reaction/Action-Modifier/political-referendum `HookOption`,
    whose own `cost` is paid unconditionally even if canceled): an Action
    card's `HookOption` has no `cost` field in play at all (`option.cost` is
    never set by any `ACTION_CARD_PLAY_HOOK` provider in this pool), so
    force-fitting that model here would have nothing to pay unconditionally
    and would instead have had to invent a meaning for "cost" this
    mechanism does not need."""
    spec: ActionCardSpec = option.apply(state)
    if state.game_over:
        return
    canceled = hooks.offer_cancel_as_played(state, option, player, other)
    if state.game_over:
        return
    if spec.name is not None:
        draw_replacement_card(state, player)
    if canceled:
        return
    if spec.name is not None:
        mark_action_card_played_this_turn(state, vampire, spec.name)
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
        block_candidate_predicate=spec.block_candidate_predicate,
    )


def _perform_attachment_removal_action(
    state: GameState,
    player: str,
    other: str,
    vampire: VampireInPlay,
    option: HookOption,
) -> None:
    """`ATTACHMENT_REMOVAL_ACTION_HOOK`'s own `ActionCardSpec` (built via
    `build_attachment_removal_action_spec`) is forwarded to `perform_
    minion_action` unchanged -- kept as its own function, not reusing
    `_perform_action_card`, so a future reader is never misled into
    thinking this mechanism plays a card from hand (see
    `ACTION_ATTACHMENT_REMOVAL`'s own docstring)."""
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
        block_candidate_predicate=spec.block_candidate_predicate,
    )
