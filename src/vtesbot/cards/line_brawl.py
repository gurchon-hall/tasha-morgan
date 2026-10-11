"""Line Brawl (Action). krcg id 102229.

Card text (verbatim, via the installed `krcg` 5.14 package's own
`krcg.load()["line brawl"]`, 2026-10-11, matching the raw snapshot saved to
`data/cards/102229.json` byte-for-byte):
    "Requires an Anarch.
    [cel] Ⓓ Steal 1 pool from another Methuselah.
    [pot] Ⓓ Enter combat with a minion.
    [pre] Ⓓ Bleed with +1 bleed."

Rulings (verbatim, via krcg; matches the raw snapshot):
    - "When played, a multi-Disciplines card counts as requiring the
      Discipline(s) being used. In the hand, library, or ash heap, the card
      is considered to require any and/or all Disciplines listed on it."
      [LSJ 20011204-3] [PIB 20130704]

Card type: Action (`types == ["Action"]`, *not* "Action Modifier").
`discipline_requirement == {"type": "Choice", "disciplines": ["cel", "pot",
"pre"]}` -- a choice among the three, all lowercase/basic only (no superior
variant printed on this card; confirmed by the installed package's own
`discipline_requirement`, no uppercase entry). `clan_requirement == []`,
`path_requirement == []`, `cost is None`, `burn_option is False`,
`trifle is False`. Legal since 2021-12-31; confirmed on the active 2P
allowed list (`data/formats/2p/2026-10-03.json`) and in the suggested 2P
decklist `data/decks/vekn-2p/brujah.json`.

Status: implemented.

"Requires an Anarch": a card-level legality gate independent of which
discipline clause is used (Rulebook SS6 Vampire Sects), identical in shape
to `cards/dust_up.py`'s own gate (OQ-18, `docs/OPEN_QUESTIONS.md`, resolved):
every provider below first checks `vampire.card.sect is Sect.ANARCH` on the
*acting* vampire (the one that would play this card) and offers nothing at
all otherwise -- including when `sect is None` ("not modeled for this
instance", `CryptCard`'s own docstring: a card gating on sect must treat
`None` as "does not qualify," never guess a default sect).

Engine wiring (shared by all three clauses): a library card of printed
`types == ["Action"]` is itself the acting minion's entire minion action for
the turn, the exact shape `engine/phases/minion.py::ACTION_CARD_PLAY_HOOK` /
`ActionCardSpec` already generalizes (see `enchant_kindred.py`, the first
card built on this hook, for the identical pattern mirrored here). Each
clause is offered as its own independent `HookOption` against that one
hook, mirroring `dust_up.py`'s three independent, mutually-exclusive-per-
offer clauses: a vampire holding two or three of `cel`/`pot`/`pre` sees one
option per discipline it has (this is a *choice* among three basic-level
clauses on one physical card, not a basic-vs-superior pair, per the "a
multi-Disciplines card counts as requiring the Discipline(s) being used"
ruling above -- in hand/library/ash heap the card requires any/all three; in
play, only the discipline(s) actually used by that play apply). All three
clauses carry the "Ⓓ" directed-action marker (Rulebook SS2 glossary
"Directed Action"), so `ActionCardSpec.directed=True` for all three; none
prints an inherent stealth bonus, so `base_stealth=0` for all three (mirrors
the plain default-bleed baseline, `engine/phases/minion.py::BLEED_STEALTH`).
Each clause plays the card immediately to the ash heap
(`vtesbot.cards._shared.play_from_hand`) at announce time: whether the play
ends up blocked or resolves, none of the three clauses has any other
printed destination for the card (mirrors `enchant_kindred.py`'s/
`kine_resources_contested.py`'s one-shot immediate-consumption cards, not
Recruit Ally's two-destination dance).

"[cel] Ⓓ Steal 1 pool from another Methuselah.": in a 2P duel "another
Methuselah" is the sole opponent (`state.other_player`, the same reading
already applied, without raising OQ-1, by `enchant_kindred.py`'s own bleed
clause and `kine_resources_contested.py`'s referendum target -- the
collapse is a settled structural fact of the format, CLAUDE.md SS3, not a
card-text ambiguity needing a fresh Open Question). "Steal" moves only what
is actually there: `engine.pool.lose_pool` already floors a pool loss at
the target's current pool and returns the amount *actually* lost (used the
same way by `kine_resources_contested.py`'s own "can allocate more points
than a Methuselah has pool" ruling), so stealing from a Methuselah with 0
pool steals 0 -- no separate rule needed, and nothing in the card's own
text or any ruling on file says otherwise (no guess: a plain reading of
"steal" as "move what exists", not "move a fixed amount regardless of
availability"). The stolen amount is then credited to the acting player via
`engine.pool.gain_pool`. This is a pool transfer, not a bleed (the printed
text says "Steal", never "Bleed") and sets no Edge (the 2P variant's Edge
mechanic is tied specifically to a successful *bleed*, Rulebook SS2
"2P Variant" Edge rules; this clause never touches `state.edge_holder`).
No existing hook/provider gates on a "steal pool" action type, so
`ActionCardSpec.action` is left at its generic `ACTION_ACTION_CARD` default
(OQ-9, `engine/action.py`) -- correct, since this clause is textually
neither a Bleed nor any other existing default action, and nothing in the
current pool needs to distinguish "a steal" from any other sui generis
Action-card play during the block-attempt phase's stealth/intercept hook
windows.

"[pot] Ⓓ Enter combat with a minion.": this clause's entire resolution *is*
initiating combat -- unlike a bleed/hunt, it has no pool/blood payload of
its own. Mapped directly onto the existing block-attempt model:
  - If the opponent blocks (with any of their own ready unlocked minions,
    their choice, exactly like blocking any other directed action -- the
    specific minion *named* by this clause's own target choice below does
    not restrict which of the opponent's minions may attempt to block,
    since Rulebook SS4 "Who May Attempt to Block" ties block eligibility to
    which *Methuselah* is targeted, not to a specific minion), the generic
    engine's own `engine/action.py::perform_minion_action` already runs
    `engine/combat.py::run_combat` between the acting vampire and the
    blocker, *instead of* calling this clause's own `resolve()` -- this
    already *is* "enter combat with a minion" (the blocking one), achieved
    for free by the existing block-attempt plumbing, with no card-specific
    code needed for that branch.
  - If unblocked, `resolve()` must itself initiate combat (nothing else
    will): it picks one of the opponent's `zone == "ready"` vampires (any
    lock state -- locking only prevents a minion from acting, not from
    being forced into combat; Rulebook SS4 Leave Torpor's own aside,
    "vampires in torpor cannot enter combat", is the *only* readiness
    restriction on a combat target anywhere in the detailed turn sequence,
    confirmed by grepping every "enter combat" crypt-text precedent via
    krcg, e.g. Theo Bell "can enter combat with a minion as a Ⓓ action", no
    further qualifier) and calls `engine/combat.py::run_combat` directly
    with the acting vampire and that target. The target is never locked by
    this clause: a card-text precedent survey (via krcg, 2026-10-11) of
    every other "enter combat with a minion"-shaped card found exactly one
    that explicitly locks its target as part of the effect (Brujah Frenzy:
    "The Brujah enters combat with that minion, locking him or her.") --
    the fact that *that* card has to say so explicitly, and Line Brawl's
    own text does not, confirms (Golden Rule for Cards, CLAUDE.md SS2) that
    forcing combat does not lock the target by itself; only the generic
    block-attempt path's own blocker-locking step (`engine/action.py::
    attempt_block`) ever locks a vampire that way, and this branch bypasses
    that path entirely. "a minion" is restricted here to opposing
    *vampires*: allies are deliberately out of this project's combat scope
    altogether (`engine/allies.py`'s own module docstring, "ally bleed/
    block/combat participation" deliberately out of scope;
    `engine/combat.py`'s own CLAUDE.md milestone-2 scope restriction, "no
    equipment/retainers/allies in combat") -- `run_combat` has no support
    for an `AllyInPlay` combatant and nothing in the current pool needs
    that capability yet, so this clause simply never offers an ally as a
    target, a pre-existing, documented scope boundary rather than a fresh
    guess about this card's own wording. The "Ⓓ" marker on this clause
    (Rulebook SS2 glossary "Directed Action": targets another Methuselah or
    something they control) is itself what settles that the target vampire
    must be controlled by the opponent, not the acting player's own side --
    no separate "controlled by your prey or predator" qualifier is printed
    on this card (contrast several crypt-text precedents, e.g. Gustaphe
    Brunnelle, which spell it out explicitly), but the Ⓓ marker already
    carries that restriction by its own rulebook definition.

  "Which specific minion to enter combat with" is a new per-card `Decision`
  (kind `"line_brawl_combat_target"`), raised inside `apply()`, at announce
  time, before the block-attempt window opens -- *not* deferred to
  `resolve()` (`rules-auditor` finding, 2026-10-11, MAJOR: an earlier
  landing of this clause raised the choice inside `resolve()`, which
  `engine/action.py::perform_minion_action` only calls *after*
  `attempt_block` has already run to completion. That silently contradicted
  two sources at once: Rulebook SS4 "1. Announce the Action" -- "All details
  of the action are defined when the action is announced, including the
  target(s), the cost, the effects, and so on" -- and this very engine's own
  documented contract for `ActionCardSpec`/`_perform_action_card`
  (`engine/phases/minion.py`): "`option.apply(state)` is invoked right away,
  *before* the block-attempt window opens." Deferring the target pick past
  `apply()` meant the defending Methuselah was asked "do you block?" without
  the specific minion that would be forced into combat ever having been
  fixed -- information the rulebook says must already be set by that point.
  `enchant_kindred.py`'s own superior clause has the identical latent defect
  (lower stakes there -- its target is the acting player's own uncontrolled
  vampire, so no opposing block decision is ever shaped by it -- but the
  same contract violation); OQ-17's resolution, cited by the earlier,
  now-corrected docstring here, only ever examined that undirected,
  own-side case, not this clause's directed, opponent-side one, so citing it
  as having already settled this clause's timing was an unexamined
  extrapolation past what OQ-17 actually decided -- see `docs/
  OPEN_QUESTIONS.md` OQ-21, fully resolved: beyond the two sources above, a
  live krcg ruling search turned up the general ruling (cross-referenced
  against well over 100 unrelated library/crypt cards) that an unblocked
  action whose target no longer meets the printed condition at resolve time
  "fizzles (resolves successfully for no effect)" rather than re-targeting
  -- i.e. VTES never re-chooses a card's target at resolve time anywhere in
  the game, it only ever re-validates the one fixed at announce. `resolve()`
  below's own "target no longer `\"ready\"`" branch already matches that
  fizzle convention exactly (silently doing nothing), confirming it as
  correct rules modeling, not merely a defensive fallback for an otherwise
  unreachable case). "Only when needed" still applies, just one step earlier: with
  exactly one eligible target at `apply()` time, bound directly with no
  decision raised at all; with none (the hook itself, below, is not even
  offered when the opponent controls no ready vampire, so the whole play is
  never offered as a vacuous choice -- mirrors `enchant_kindred.py`'s own
  superior clause, "no eligible target: do not offer a card play that
  cannot resolve"); with more than one, a `Decision` offers one choice per
  eligible target (no "decline" alternative -- the card is already being
  played by this point, the effect is mandatory, only *which* target remains
  to be chosen). `resolve()` then simply looks up the already-chosen target
  by the instance id `apply()` bound into its closure (defensively treating
  a target that somehow left `"ready"` between announce and resolve -- not
  reachable today, nothing in this engine's current scope mutates an
  opposing vampire's zone during a block-attempt window -- as "no longer
  available," rather than crashing).

"[pre] Ⓓ Bleed with +1 bleed.": word-for-word identical clause text to
`enchant_kindred.py`'s own basic `[pre]` clause. Mirrors that clause's
`resolve()` closure byte-for-byte (same fixed/impulse-window/clamp/
edge-holder computation, `BLEED_AMOUNT_FIXED_MODIFIER_HOOK` +
`BLEED_AMOUNT_MODIFIER_HOOK` composition, `PENDING_BLEED_AMOUNT_KEY` fold-in)
rather than reinventing the pattern, with the base amount hardcoded to 2
(default bleed 1 + this card's own printed "+1 bleed", baked into the
baseline the same way `_perform_bleed`'s own `BLEED_AMOUNT` constant is --
not a separately offered, declinable modifier). `ActionCardSpec.action` is
declared `ACTION_BLEED` (not left at the generic `ACTION_ACTION_CARD`
default), required -- not merely cosmetic -- so an existing bleed-gated
provider sharing the same block-attempt/bleed-amount hook windows (e.g.
`bonding.py`'s superior clause, gated on `context.get("action") ==
ACTION_BLEED`) is not silently and wrongly suppressed when both cards are
in the same hand, exactly per `enchant_kindred.py`'s own basic clause and
the rules-auditor finding (OQ-17 follow-up) that motivated it.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import ACTION_BLEED
from vtesbot.engine.cards import Sect
from vtesbot.engine.combat import run_combat
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import (
    ACTION_CARD_PLAY_HOOK,
    BLEED_AMOUNT_FIXED_MODIFIER_HOOK,
    BLEED_AMOUNT_MODIFIER_HOOK,
    PENDING_BLEED_AMOUNT_KEY,
    ActionCardSpec,
)
from vtesbot.engine.pool import gain_pool, lose_pool
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 102229
CEL = "cel"
POT = "pot"
PRE = "pre"
STEAL_AMOUNT = 1
"""Printed "Steal 1 pool from another Methuselah."."""
PRE_BLEED_BASE_AMOUNT = 2
"""Default bleed amount (1) + this card's own printed "+1 bleed", baked into
the baseline the same way `enchant_kindred.py`'s own `BASIC_BLEED_BASE_AMOUNT`
is -- not a separately-offered, declinable modifier."""


def _controllers_vampire(state: GameState, context: Mapping[str, Any]) -> VampireInPlay | None:
    """The acting vampire for this `"action_card_play"` offer, or `None` if
    `context["player"]` is the defender for this particular hook call (the
    same hook is offered to both sides over the course of a game; a provider
    must only answer for its own player's acting-vampire context)."""
    return state.players[context["player"]].vampires.get(context["vampire"])


def _requires_an_anarch(vampire: VampireInPlay | None) -> bool:
    return vampire is not None and vampire.card.sect is Sect.ANARCH


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _eligible_combat_targets(state: GameState, player: str) -> list[VampireInPlay]:
    """Opposing vampires this player's `[pot]` clause could force into
    combat: any `zone == "ready"` vampire (lock state irrelevant -- see
    module docstring; torpor is the only readiness restriction the rules
    place on an "enter combat" target). Allies are out of this project's
    combat scope (module docstring) and are never offered."""
    opponent = state.other_player(player)
    return [v for v in state.players[opponent].vampires.values() if v.zone == "ready"]


def _provide_line_brawl_cel(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[cel] Ⓓ Steal 1 pool from another Methuselah." """
    player = context["player"]
    acting_vampire = _controllers_vampire(state, context)
    if not _requires_an_anarch(acting_vampire):
        return []
    disciplines = acting_vampire.card.disciplines  # type: ignore[union-attr]
    if CEL not in disciplines and CEL.upper() not in disciplines:
        return []
    if not _has_card_in_hand(state, player):
        return []

    def _apply(s: GameState) -> ActionCardSpec:
        play_from_hand(s, player, KRCG_ID)

        def resolve(pending: dict[str, Any]) -> None:
            del pending  # no later hook window of its own to feed.
            other = s.other_player(player)
            stolen = lose_pool(s, other, STEAL_AMOUNT)
            gain_pool(s, player, stolen)

        return ActionCardSpec(base_stealth=0, directed=True, resolve=resolve)

    return [
        HookOption(
            choice=Choice(
                "line_brawl:cel", "Line Brawl [cel]: Steal 1 pool from another Methuselah"
            ),
            apply=_apply,
        )
    ]


def _provide_line_brawl_pot(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[pot] Ⓓ Enter combat with a minion." -- see module docstring for the
    block/unblocked split and the target-choice decision."""
    player = context["player"]
    acting_vampire = _controllers_vampire(state, context)
    if not _requires_an_anarch(acting_vampire):
        return []
    disciplines = acting_vampire.card.disciplines  # type: ignore[union-attr]
    if POT not in disciplines and POT.upper() not in disciplines:
        return []
    if not _has_card_in_hand(state, player):
        return []
    if not _eligible_combat_targets(state, player):
        return []  # no legal target at all: never offer a play that cannot resolve.

    def _apply(s: GameState) -> ActionCardSpec:
        play_from_hand(s, player, KRCG_ID)

        # Target fixed now, at announce time (module docstring, rules-auditor
        # finding): Rulebook SS4 "Announce the Action" + this engine's own
        # `ActionCardSpec` contract both require every detail of the action,
        # including the target, to be set before the block-attempt window
        # opens -- not deferred to `resolve()`.
        targets = _eligible_combat_targets(s, player)
        if len(targets) == 1:
            target_id = targets[0].instance_id
        else:
            choices = tuple(
                Choice(
                    f"line_brawl_combat_target:{v.instance_id}",
                    f"Enter combat with {v.card.name}",
                )
                for v in targets
            )
            decision = Decision(player=player, kind="line_brawl_combat_target", choices=choices)
            chosen_value = s.ask(decision).value
            target_id = chosen_value.split(":", 1)[1]

        def resolve(pending: dict[str, Any]) -> None:
            del pending  # no later hook window of its own to feed.
            opponent = s.other_player(player)
            target = s.players[opponent].vampires.get(target_id)
            if target is None or target.zone != "ready":
                return  # fizzles (OQ-21); not reachable today, but correct either way.
            run_combat(s, player, acting_vampire, opponent, target)

        return ActionCardSpec(base_stealth=0, directed=True, resolve=resolve)

    return [
        HookOption(
            choice=Choice("line_brawl:pot", "Line Brawl [pot]: Enter combat with a minion"),
            apply=_apply,
        )
    ]


def _provide_line_brawl_pre(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[pre] Ⓓ Bleed with +1 bleed." -- mirrors `enchant_kindred.py`'s own
    basic `[pre]` clause byte-for-byte; see module docstring."""
    player = context["player"]
    acting_vampire = _controllers_vampire(state, context)
    if not _requires_an_anarch(acting_vampire):
        return []
    disciplines = acting_vampire.card.disciplines  # type: ignore[union-attr]
    if PRE not in disciplines and PRE.upper() not in disciplines:
        return []
    if not _has_card_in_hand(state, player):
        return []

    def _apply(s: GameState) -> ActionCardSpec:
        play_from_hand(s, player, KRCG_ID)

        def resolve(pending: dict[str, Any]) -> None:
            other = s.other_player(player)
            base_amount = (
                PRE_BLEED_BASE_AMOUNT
                + hooks.sum_modifiers(
                    BLEED_AMOUNT_FIXED_MODIFIER_HOOK,
                    s,
                    player=player,
                    vampire=acting_vampire.instance_id,
                )
                + pending.get(PENDING_BLEED_AMOUNT_KEY, 0)
            )
            amount_box = [base_amount]
            hooks.resolve_impulse_window(
                s,
                BLEED_AMOUNT_MODIFIER_HOOK,
                player,
                other,
                context={
                    "vampire": acting_vampire.instance_id,
                    "amount": amount_box,
                    "pending": pending,
                },
            )
            amount = max(0, amount_box[0])
            lose_pool(s, other, amount)
            if amount >= 1:
                s.edge_holder = player

        return ActionCardSpec(
            base_stealth=0,
            directed=True,
            resolve=resolve,
            action=ACTION_BLEED,
        )

    return [
        HookOption(
            choice=Choice("line_brawl:pre", "Line Brawl [pre]: Bleed with +1 bleed"),
            apply=_apply,
        )
    ]


hooks.register(ACTION_CARD_PLAY_HOOK, _provide_line_brawl_cel)
hooks.register(ACTION_CARD_PLAY_HOOK, _provide_line_brawl_pot)
hooks.register(ACTION_CARD_PLAY_HOOK, _provide_line_brawl_pre)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Line Brawl",
        status=Status.IMPLEMENTED,
        hooks=(Hook.ACTION_CARD_PLAY,),
        source=__name__,
    )
)
