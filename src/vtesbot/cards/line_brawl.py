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
discipline clause is used (Rulebook SS6 Vampire Sects), same shape as
`dust_up.py`'s gate (OQ-18, resolved). Every provider below checks
`vampire.card.sect is Sect.ANARCH` on the acting vampire and offers nothing
otherwise, including when `sect is None` (`CryptCard`'s own docstring:
`None` means "does not qualify", never a guessed default sect).

Engine wiring (shared by all three clauses): a library card of printed
`types == ["Action"]` is itself the acting minion's entire minion action for
the turn, via `engine/phases/minion.py::ACTION_CARD_PLAY_HOOK`/
`ActionCardSpec` (first used by `enchant_kindred.py`). Each clause is its
own `HookOption` against that hook, so a vampire holding two or three of
`cel`/`pot`/`pre` sees one option per discipline it has -- a *choice* among
three basic-level clauses on one card, per the multi-Disciplines ruling
above (in hand/library/ash heap the card requires any/all three; in play,
only the discipline used applies). All three clauses carry the "Ⓓ"
directed-action marker (Rulebook SS2 glossary "Directed Action"), so
`ActionCardSpec.directed=True` throughout; none prints a stealth bonus, so
`base_stealth=0` throughout. Each clause plays the card to the ash heap
(`vtesbot.cards._shared.play_from_hand`) at announce time: none of the
three has any other printed destination.

"[cel] Ⓓ Steal 1 pool from another Methuselah.": in a 2P duel "another
Methuselah" is the sole opponent (`state.other_player`; settled structural
fact of the format, CLAUDE.md SS3, not a card-text ambiguity). `lose_pool`
already floors a pool loss at the target's current pool and returns the
amount actually lost, so stealing from a Methuselah with 0 pool steals 0;
the stolen amount is credited via `gain_pool`. This is a pool transfer, not
a bleed, and sets no Edge (Rulebook SS2 "2P Variant" Edge rules tie Edge to
a successful *bleed* specifically). `ActionCardSpec.action` is left at the
generic `ACTION_ACTION_CARD` default (OQ-9): this clause is textually
neither a Bleed nor any other existing default action.

"[pot] Ⓓ Enter combat with a minion.": this clause's resolution *is*
initiating combat, with no pool/blood payload of its own.
  - If the opponent blocks, the generic `engine/action.py::
    perform_minion_action` already runs `engine/combat.py::run_combat`
    between the acting vampire and the blocker instead of calling this
    clause's `resolve()` -- that already *is* "enter combat with a minion,"
    for free from the existing block-attempt plumbing (Rulebook SS4 "Who
    May Attempt to Block" ties eligibility to the targeted *Methuselah*,
    not to the minion this clause names, so any of the opponent's ready
    minions may block).
  - If unblocked, `resolve()` picks one of the opponent's `zone == "ready"`
    vampires (lock state irrelevant: only torpor restricts a combat target,
    Rulebook SS4 "Leave Torpor"; confirmed against crypt-text precedent,
    e.g. Theo Bell) and calls `run_combat` directly. The target is never
    locked by this clause -- contrast Brujah Frenzy, which locks its target
    explicitly; Line Brawl's silence on locking means it doesn't (Golden
    Rule for Cards, CLAUDE.md SS2). "a minion" means opposing vampires only:
    allies are out of this project's combat scope (`engine/allies.py`,
    `engine/combat.py` milestone-2 scope), so never offered. The Ⓓ marker
    (Rulebook SS2 glossary) itself settles that the target must be
    opponent-controlled.

  The target vampire is chosen inside `apply()`, at announce time, before
  the block-attempt window opens -- not deferred to `resolve()` (OQ-21,
  resolved: Rulebook SS4 "Announce the Action" plus this engine's own
  `ActionCardSpec` contract both fix every detail, including the target,
  at announce; a krcg ruling survey further confirms an unblocked action
  whose target stops qualifying by resolve time "fizzles" rather than
  re-targets). With exactly one eligible target at `apply()` time it is
  bound directly with no decision raised; with none, the hook itself is not
  offered (see the `_eligible_combat_targets` guard below); with more than
  one, a `Decision` offers one choice per target (no decline -- the card is
  already being played, only *which* target remains open). `resolve()`
  looks up the chosen target by instance id, treating a target that left
  `"ready"` between announce and resolve as "nothing to do" per OQ-21's
  fizzle convention (not reachable today, but correct either way).

"[pre] Ⓓ Bleed with +1 bleed.": identical clause text and `resolve()` shape
to `enchant_kindred.py`'s basic `[pre]` clause (same
`BLEED_AMOUNT_FIXED_MODIFIER_HOOK`/`BLEED_AMOUNT_MODIFIER_HOOK`/
`PENDING_BLEED_AMOUNT_KEY` composition), with the base amount hardcoded to 2
(default bleed 1 + this card's printed "+1 bleed", not a separately offered
modifier). `ActionCardSpec.action` is declared `ACTION_BLEED` (not the
generic default) so an existing bleed-gated provider sharing the same hook
windows (e.g. `bonding.py`'s superior clause, gated on
`context.get("action") == ACTION_BLEED`) isn't silently suppressed when
both cards are in the same hand (OQ-17 follow-up).
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
CARD_TYPE = "Action"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): matches
this module's own "Card type: Action" docstring fact above."""


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
            played_card_type=CARD_TYPE,
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

        # Target fixed at announce time, not deferred to resolve() -- OQ-21,
        # see module docstring.
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
            played_card_type=CARD_TYPE,
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
            played_card_type=CARD_TYPE,
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
