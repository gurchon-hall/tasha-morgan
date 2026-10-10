"""Minion phase: default actions (bleed, hunt, recruit ally).

Source: Rulebook SS4 Minion Phase (per the `vtes-rules-reference` skill
condensed mapping): "actions by ready unlocked minions; mandatory actions
first (a ready vampire with no blood must hunt). Each action fully resolves
before the next." "Default actions: bleed (directed, 0 stealth, bleed 1,
one bleed per minion per turn, successful bleed >=1 takes the Edge; ...),
hunt (undirected, +1 stealth, +1 blood), ... recruit ally (undirected, +1
stealth; recruited ally cannot act this turn)."

CLAUDE.md milestone-2/3 scope: bleed, hunt and recruit ally are implemented;
all other minion actions (equip, political action, leave torpor, diablerie,
become Anarch, etc.) are still out of scope and are never offered. "One
bleed per minion per turn" is enforced implicitly: acting locks the vampire
(Rulebook SS4 step 1), and a locked vampire cannot act again until it next
unlocks.

Recruit ally (OQ-12, `docs/OPEN_QUESTIONS.md`, resolved): built on top of
OQ-7's `AllyInPlay`/`recruit_ally` (`engine/state.py`, `engine/allies.py`),
which gave an ally a representation in play but no real entry point a
player's agent could ever reach in a game. `_perform_recruit_ally` below is
that entry point, parameterized entirely by what `src/vtesbot/cards/`
registers against the `"recruit_ally_play"` hook (`RECRUIT_ALLY_PLAY_HOOK`),
mirroring `engine/phases/master.py`'s `"master_phase_play"` pattern (CLAUDE.md
SS6 "the engine exposes hooks/events; card-specific behaviour lives in
`src/vtesbot/cards/`. Do not special-case card names in the engine."). With
no Ally card module registered yet (47th Street Royals stays `blocked`/OQ-12
in the registry -- unblocking it against this capability is
`card-implementer`'s job), every call to `hooks.offer(RECRUIT_ALLY_PLAY_HOOK,
...)` returns an empty list, so "recruit ally" is never offered as a choice
at all (the "only when needed"/"never a vacuous Decision" invariant) and
`_choose_and_perform_action` behaves exactly as the pre-OQ-12 bleed/hunt-only
version until a card actually registers.

Who may attempt to recruit (Rulebook SS4 Recruit Ally: "Who can recruit an
ally: Any ready minion"): read literally this includes a ready unlocked
ally, not only a vampire. `_choose_and_perform_action` is only ever called
for a ready unlocked *vampire* (see `minion_phase`'s own loop below, and
`engine/allies.py`'s module docstring for why extending this to allies is a
deliberately deferred, sourced-but-unneeded scope boundary, not a guess).

Bleed-amount hook wiring (`engine/hooks.py`, CLAUDE.md milestone-3 scaffolding
pass): once a bleed goes unblocked, the "pay cost, resolve" step (Rulebook
SS4 Minion Phase) is where bleed-amount-modifying cards apply (e.g. Bonding/
Threats/Enchant Kindred add bleed; Telepathic Counter/47th Street Royals
reduce it). This is the general two-sided impulse window (CLAUDE.md rule 4 /
Rulebook SS2 Sequencing), not the block attempt's narrower "only when
needed" ping-pong, so `_perform_bleed` uses `hooks.resolve_impulse_window`
directly. With no providers registered against the `"bleed_amount_modifier"`
hook (no such library cards implemented yet), the window offers nothing and
closes immediately, leaving the bleed at its base amount -- byte-for-byte
the milestone-2 result. A separate, mandatory, non-optional
`"bleed_amount_fixed_modifier"` hook (`hooks.sum_modifiers`) is applied
*before* that window opens, for an unconditional printed bonus such as a
vampire's flat "+1 bleed" ability text (CLAUDE.md rule 3's "mandatory
effects" exception -- not a card the player chooses to play, so it must not
be offered as a declinable choice).

Action-discriminator constants (rules-auditor finding, OQ-9): `ACTION_BLEED`/
`ACTION_HUNT` (`engine/action.py`) are forwarded as `perform_minion_action`'s
`action=` argument instead of re-typing `"bleed"`/`"hunt"` here, so a typo
cannot silently desync this module's two producing call sites from a future
hook provider's own `context["action"] == ...` check.

Action-card entry point (OQ-17, `docs/OPEN_QUESTIONS.md`, resolved by this
pass): a library card of printed `types == ["Action"]` (Rulebook SS2 Card
Types; e.g. Enchant Kindred, krcg 100640) is itself the acting vampire's
entire minion action for the turn, distinct from an "Action Modifier" card
(which only ever decorates an already-chosen default action, the shape
`BLEED_AMOUNT_MODIFIER_HOOK` above already covers). `ACTION_CARD_PLAY_HOOK`
("action_card_play") generalizes `RECRUIT_ALLY_PLAY_HOOK`'s own pattern
beyond Allies: a provider offers one option per playable Action card of its
own it finds in `player`'s hand, and `apply(state)` must return an
`ActionCardSpec` (below) instead of a `RecruitAllySpec`. `_perform_action_
card` runs it through `perform_minion_action` exactly like `_perform_bleed`/
`_perform_hunt`/`_perform_recruit_ally` already do, under
`ActionCardSpec.action` (`engine/action.py`, OQ-9): this defaults to
`ACTION_ACTION_CARD` (every Action-card play that is genuinely sui generis
shares that one fallback action *type*, mirroring `ACTION_RECRUIT_ALLY`),
but a provider whose own clause is textually a Bleed/Hunt/etc. (rules-
auditor finding, OQ-17 follow-up -- e.g. Enchant Kindred's basic clause,
"[pre] Ⓓ Bleed with +1 bleed") must override it to the matching constant,
so an existing action-gated provider sharing the same hook window (e.g.
`cards/bonding.py`'s superior clause) is not silently and wrongly
suppressed. With no provider registered against this hook yet (Enchant
Kindred's own card module is a separate, `card-implementer` pass), every
call to `hooks.offer(ACTION_CARD_PLAY_HOOK, ...)` returns an empty list, so
this is pure scaffolding -- byte-for-byte the pre-OQ-17 result -- until a
card registers.

Pending-modifier scratch container (OQ-11, `docs/OPEN_QUESTIONS.md`):
`perform_minion_action` (`engine/action.py`) now calls `resolve` with one
`pending: dict[str, Any]` argument -- the same object threaded into the
block-attempt phase's `"stealth_modifier"`/`"intercept_modifier"` hook
context (see that module's docstring) -- so a card play offered during that
earlier phase can stash something for a later hook window of this *same*
minion action to read back. `_perform_bleed`'s `resolve` closure below folds
`pending.get(PENDING_BLEED_AMOUNT_KEY, 0)` into `base_amount` before
building `amount_box` and opening the (separately declinable)
`"bleed_amount_modifier"` window, and also threads `pending` itself into
that window's own context, so a provider registered there can inspect it
too. `_perform_hunt`'s `resolve` closure accepts the same argument (the
shared call-site signature `perform_minion_action` requires) but has no
later window to feed, so it simply ignores it. With no provider ever
stashing anything under `PENDING_BLEED_AMOUNT_KEY` yet (no card registers
against it), this is pure scaffolding -- byte-for-byte the pre-OQ-11
result -- until a card uses it.
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
from ..damage import add_blood
from ..decision import Choice, Decision
from ..pool import lose_pool

if TYPE_CHECKING:
    from ..allies import RecruitAllySpec
    from ..hooks import HookOption
    from ..state import GameState, VampireInPlay

BLEED_STEALTH = 0
BLEED_AMOUNT = 1
HUNT_STEALTH = 1
HUNT_BLOOD_GAIN = 1
RECRUIT_ALLY_STEALTH = 1
"""Rulebook SS4 Recruit Ally: "Default stealth: +1 stealth." """
RECRUIT_ALLY_PLAY_HOOK = "recruit_ally_play"
"""`HookOption`-based hook (mirrors `engine/phases/master.py`'s
`"master_phase_play"`): a provider inspects `context["player"]`'s hand for
its own Ally library card(s) and offers one option per playable card it
finds; `apply(state)` must return an `engine/allies.py::RecruitAllySpec`
(OQ-12, `docs/OPEN_QUESTIONS.md`)."""
ACTION_CARD_PLAY_HOOK = "action_card_play"
"""`HookOption`-based hook (OQ-17, `docs/OPEN_QUESTIONS.md`, resolved by this
pass): generalizes `RECRUIT_ALLY_PLAY_HOOK` above beyond Allies -- a
provider inspects `context["player"]`'s hand for its own library card(s) of
printed `types == ["Action"]` (Rulebook SS2 Card Types; distinct from an
"Action Modifier," which only ever decorates an already-chosen default
action) and offers one option per playable card it finds; `apply(state)`
must return an `ActionCardSpec` below."""
BLEED_AMOUNT_MODIFIER_HOOK = "bleed_amount_modifier"
BLEED_AMOUNT_FIXED_MODIFIER_HOOK = "bleed_amount_fixed_modifier"
"""Passive, mandatory numeric hook (`hooks.sum_modifiers`, CLAUDE.md rule 3's
"mandatory effects" exception) for an unconditional printed bonus (e.g. a
vampire's flat "+1 bleed" text), applied before the optional
`"bleed_amount_modifier"` impulse window opens, so an always-on bonus is
never mistakenly offered as a player choice with a "decline" option."""
PENDING_BLEED_AMOUNT_KEY = "bleed_amount_bonus"
"""Scratch-dict key convention (OQ-11, `docs/OPEN_QUESTIONS.md`): a
`"stealth_modifier"`/`"intercept_modifier"` hook provider (offered during
the earlier block-attempt phase of *this same* bleed action -- see
`engine/action.py`) that also owes an amount to this action's bleed, as part
of the very same card play, stores a running total under this key in the
shared `pending` dict (e.g. `pending[PENDING_BLEED_AMOUNT_KEY] =
pending.get(PENDING_BLEED_AMOUNT_KEY, 0) + 1`). `_perform_bleed`'s `resolve`
closure folds it into `base_amount` before building `amount_box`, so it
participates in that computation's single clamp-at-0/Edge-holder logic
instead of bypassing it (OQ-11's rejected "immediate separate pool loss"
alternative would desynchronize from that same logic -- see OQ-11's worked
example)."""


@dataclass(frozen=True)
class ActionCardSpec:
    """What an `"action_card_play"` hook option's `apply(state)` must return
    (OQ-17, `docs/OPEN_QUESTIONS.md`, resolved by this pass).

    Generalizes `engine/allies.py::RecruitAllySpec`'s own shape beyond
    Allies: a library card of printed `types == ["Action"]` (Rulebook SS2
    Card Types) is itself the acting vampire's entire minion action for the
    turn, rather than merely decorating an already-chosen default Bleed/Hunt
    (contrast `BLEED_AMOUNT_MODIFIER_HOOK`/`BLEED_AMOUNT_FIXED_MODIFIER_HOOK`
    above, which only ever layer onto a separately-chosen, already-free
    default bleed).

    A registered provider's `apply(state)` is invoked immediately when the
    acting player chooses this option, at announce time, before the
    block-attempt window opens (Rulebook SS4 "Announce the Action"), and is
    entirely responsible for its own card's removal from `player`'s hand
    (and, per Rulebook SS2 "replace from library after play", drawing its
    replacement) -- the hook's own contract deliberately does not dictate
    *how*: a plain one-shot Action card whose own placement does not depend
    on the later block outcome (e.g. Enchant Kindred -- Rulebook SS4
    "Resolve the Action" either resolves the card's own text when unblocked
    or burns it when blocked, both of which end the same way, in the ash
    heap, for a card with no other printed destination) consumes it
    immediately via `vtesbot.cards._shared.play_from_hand`. A future Action
    card whose own placement *does* depend on the later block outcome
    (mirroring Recruit Ally's Ally card: set aside at announce time via
    `vtesbot.cards._shared.play_from_hand_pending`, placed in a destination
    that differs between the unblocked and blocked branches) would instead
    use that two-destination dance and supply its own `on_blocked` below --
    this slot exists so the hook's own contract does not hard-code the
    immediate-consumption assumption, without building anything further for
    a card that does not exist yet.

    `base_stealth`/`directed`: this action's own printed baseline (Rulebook
    SS4 Minion Phase; the rulebook glossary's "Directed Action"/"Undirected
    Action" pair -- see `engine/action.py`'s own module docstring, OQ-17).
    2P structurally collapses both to the same single-opponent block-attempt
    call (`engine/action.py`'s own module docstring), so `directed` changes
    no mechanics here; it is threaded through to `perform_minion_action`
    purely as accurate context for a future hook/decision consumer and for
    the replay log, not because this module branches on it itself.

    `resolve`: called by `perform_minion_action`, only once the action goes
    unblocked, exactly like `_perform_bleed`/`_perform_hunt`'s own closures
    -- must perform the card's own printed effect.

    `on_blocked`: called by `perform_minion_action`, only if the action is
    blocked, *after* combat resolves -- forwarded unchanged to
    `perform_minion_action`'s own `on_blocked=` parameter (see
    `_perform_recruit_ally`'s use of the same mechanism, below). `None` (the
    default) means nothing card-specific happens on top of the block itself
    -- correct for the immediate-consumption case, whose card's fate was
    already decided at `apply()` time.

    `action`: the OQ-9 discriminator (`engine/action.py`) threaded into the
    block-attempt phase's own hook context in place of this module's fixed
    `ACTION_ACTION_CARD`, for a clause whose card text *is* mechanically one
    of the existing default actions (rules-auditor finding, OQ-17 follow-up:
    Enchant Kindred's own basic clause, "[pre] Ⓓ Bleed with +1 bleed", prints
    the word "Bleed" -- CLAUDE.md SS2's card-text precedence settles this
    directly, no ruling or judgment call needed). Left unset, this defaults
    to `ACTION_ACTION_CARD`, correct for a clause that is genuinely sui
    generis and textually matches none of the existing default actions (e.g.
    Enchant Kindred's own superior clause, "Add 2 blood to a younger
    vampire," which is not a bleed/hunt/recruit-ally by its own text). A
    provider that declares `action=ACTION_BLEED` here must make its own
    `resolve` behave like a real bleed (lose the target's pool, set
    `state.edge_holder`, fold in `PENDING_BLEED_AMOUNT_KEY`, etc. --
    `engine/phases/minion.py::_perform_bleed`'s own `resolve` closure is the
    model to mirror) so an existing bleed-gated provider (e.g. `cards/
    bonding.py`'s superior clause, gated on `context.get("action") ==
    ACTION_BLEED`) that fires during this window is not misled about what
    is actually happening.
    """

    base_stealth: int
    directed: bool
    resolve: Callable[[dict[str, Any]], None]
    on_blocked: Callable[[dict[str, Any]], None] | None = None
    action: str = ACTION_ACTION_CARD


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
    """Rulebook SS4: offer every default action a ready unlocked *vampire*
    may attempt.

    "Recruit ally" (OQ-12) is folded into this same top-level decision,
    one choice per `"recruit_ally_play"` hook option currently on offer (one
    per recruitable Ally card found in `player`'s hand by a registered card
    module) -- rather than a separate "pick an action type, then pick which
    ally" two-step -- since each such option is already its own fully
    identified, named action (the specific Ally card being recruited), the
    same granularity bleed/hunt already have. Per the "only when needed"
    invariant, with no options on offer (no Ally card module registered, or
    none of its cards currently in hand) nothing is added here, so the
    decision degrades to exactly the pre-OQ-12 bleed/hunt choice.

    `vampire=vampire.instance_id` is threaded into the `"recruit_ally_play"`
    hook context (OQ-13, `docs/OPEN_QUESTIONS.md`, resolved): Rulebook SS2
    "Card Types" > "Requirements for Playing Cards" binds a minion card's
    requirement (e.g. an Ally's clan requirement) to the specific acting
    minion playing it, not merely to "the Methuselah controls one somewhere"
    -- the same distinction the rulebook draws against master cards. A
    provider must be able to look up *this* vampire (`vampire` is already in
    scope here, the one the player committed to via the earlier
    `"act_with:<id>"` choice in `minion_phase`) and check its own `card.clan`
    before deciding whether to offer anything, mirroring how `_perform_bleed`
    below already threads `"vampire": vampire.instance_id` into
    `BLEED_AMOUNT_MODIFIER_HOOK`'s own context.

    "Action card play" (OQ-17, `docs/OPEN_QUESTIONS.md`, resolved by this
    pass) is folded in exactly the same way, one choice per
    `"action_card_play"` hook option currently on offer (one per playable
    Action-type library card found in `player`'s hand by a registered card
    module) -- the same granularity and the same "only when needed"
    degrade-to-bleed/hunt behaviour as recruit ally above, generalized
    beyond Allies.
    """
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
    """Rulebook SS4 default bleed action; 2P variant Edge mechanic.

    Directed at the acting Methuselah's prey -- in 2P there is only one
    possible target (the opponent), so no target decision is offered
    (nothing to choose among, Rulebook SS4 "only when needed" principle).
    """

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
    """Rulebook SS4 default hunt action: undirected, +1 stealth baseline, +1 blood on success."""

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
    """Rulebook SS4 "Recruit Ally": undirected, +1 stealth, cost as listed on
    the ally card (paid only on success), "recruited ally cannot act this
    turn" (OQ-12, `docs/OPEN_QUESTIONS.md`).

    `option` is the `"recruit_ally_play"` hook option the acting player chose
    at `_choose_and_perform_action`'s top-level `action_choice` decision.
    Rulebook SS4 "Announce the Action": "Any card required for the action is
    played (face up) at this time, but is temporarily set aside (out of
    play) until the action resolves" -- `option.apply(state)` is invoked
    right away, *before* the block-attempt window opens (removing the
    specific Ally card from `player`'s hand and drawing its replacement --
    Rulebook SS2 "replace from library after play" -- via
    `vtesbot.cards._shared.play_from_hand_pending`, not `play_from_hand`,
    since where the card ends up is not yet known) and returns a
    `RecruitAllySpec` identifying the removed card and the ally's own
    printed life/strength/bleed/cost. That spec is then threaded into
    `perform_minion_action`'s `resolve`/`on_blocked` callbacks to decide the
    card's destination once the block-attempt outcome is known: unblocked ->
    pay the cost (if any) and place the ally in play (`recruit_ally`, which
    already enters it `locked=True` -- "recruited ally cannot act this
    turn"); blocked -> Rulebook SS4 "Resolve the Action": "any card played to
    perform the action is burned", so the already-removed card goes to the
    ash heap and no cost is paid.
    """
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
    """Rulebook SS2 Card Types + SS4 Minion Phase (OQ-17, `docs/
    OPEN_QUESTIONS.md`, resolved by this pass): a library card of printed
    `types == ["Action"]` is itself the acting vampire's entire minion
    action for the turn, not a decoration of an already-chosen default
    Bleed/Hunt.

    `option` is the `"action_card_play"` hook option the acting player chose
    at `_choose_and_perform_action`'s top-level `action_choice` decision.
    `option.apply(state)` is invoked right away, *before* the block-attempt
    window opens (Rulebook SS4 "Announce the Action", mirroring
    `_perform_recruit_ally`'s own timing above) and must return an
    `ActionCardSpec` describing the action's own base stealth, whether it is
    directed or undirected, its own `resolve`/`on_blocked` callbacks, and
    (rules-auditor finding, OQ-17 follow-up) the actual mechanical `action`
    discriminator its own clause's card text matches -- forwarded unchanged
    to `perform_minion_action` below, exactly like every other minion
    action's own closures. `ActionCardSpec.action` defaults to
    `ACTION_ACTION_CARD` (every Action-card play that is genuinely sui
    generis shares that one fallback action *type*, mirroring how every
    Ally recruited shares `ACTION_RECRUIT_ALLY`), but a provider whose
    clause's own text is textually a Bleed/Hunt/etc. (e.g. Enchant Kindred's
    basic clause, "[pre] Ⓓ Bleed with +1 bleed") must override it to the
    matching constant (e.g. `ACTION_BLEED`) so an existing action-gated
    provider registered against the same hook window (e.g. `cards/
    bonding.py`'s superior clause) resolves correctly instead of being
    silently and wrongly suppressed -- see `ActionCardSpec`'s own docstring,
    and `tests/rules/test_action_card_play.py::test_action_card_play_can_
    declare_itself_a_real_bleed_so_bonding_still_fires` for the worked proof.

    Unlike `_perform_recruit_ally`, this function has no card-specific
    knowledge of its own -- the provider's `ActionCardSpec` already carries
    everything `perform_minion_action` needs (including, optionally, its own
    `on_blocked`), since a plain one-shot Action card's hand-consumption is
    already finished by the time `apply(state)` returns (see
    `ActionCardSpec`'s own docstring for the future two-destination-dance
    case this still accommodates).
    """
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
    )
