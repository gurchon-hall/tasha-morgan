"""Fame (Master). krcg id 100698.

Card text (verified live via `krcg.vtes.VTES.load()["Fame"].to_json()`,
2026-10-11, and independently cross-checked against the live
`https://api.krcg.org/card/100698` endpoint, raw snapshot
`data/cards/100698.json` -- both agree verbatim):
    "Unique.
    Put this card on a ready vampire. After this vampire goes to torpor,
    their controller burns 3 pool. During each Methuselah's unlock phase,
    if this vampire is in torpor, that Methuselah burns 1 pool."

Card type: Master (`types == ["Master"]`). `discipline_requirement.
disciplines == []`, `clan_requirement == []`, `cost is None`, `trifle is
False` -- an ordinary master-phase action, same shape as Celerity
(100312, `src/vtesbot/cards/celerity.py`): no clan/discipline gate, free to
play, one ordinary master-phase action (not a trifle).

Rulings (one on file): "Paying a pool during the unlock phase can be
ordered with other unlock effects by the acting Methuselah, but must be
handled before another Methuselah has the opportunity to use an unlock
effect." [LSJ 20010121] (reference URL
<https://boardgamegeek.com/thread/609699/article/6142361#6142361>). The
installed krcg package's date is cited here; the raw API snapshot
`data/cards/100698.json` attributes the same ruling text to "[LSJ
20110121]" with a different URL for the same BGG thread 609699 --
substance identical in both, so the discrepancy is cosmetic (CLAUDE.md
"never invent... a ruling" concerns substance, not which of two matching
dates is used), with the installed package's date preferred going forward.

This confirms the unlock-phase pool burn is an *orderable* mandatory
effect: the acting Methuselah may interleave it with their other
unlock-phase effects, but must finish before passing the impulse. Fame's
own clause 4 has no legal alternative (a flat, unconditional "burn 1
pool"), so ordering has no effect on its own outcome either way (see
`engine/phases/unlock.py::UNLOCK_PHASE_MANDATORY_EFFECT_HOOK`'s own
docstring for dispatch).

Clauses:
1. "Unique." -- governs contest, not initial legality to play (resolved by
   OQ-22 below): nothing stops either Methuselah from independently playing
   their own separately-decked copy of Fame while another copy is already
   attached and uncontested -- that is exactly the situation that triggers
   a contest between the two copies.
2. "Put this card on a ready vampire." -- a `CardAttachment`
   (`engine/attachments.py::attach_card`) on a vampire whose `zone ==
   "ready"` *at the moment of play*, either player's (no clan/discipline
   restriction, no "you control" qualifier, mirroring Celerity's own
   targeting precedent, OQ-8; Rulebook §2 Card Types: "A master card in
   play is controlled by the Methuselah who played it, even if it is played
   on a card controlled by another Methuselah"). Unlike Celerity (whose
   plain "a vampire" also allows a torpid target per Rulebook §8 glossary
   "Target"), Fame's text explicitly narrows this to "a ready vampire": a
   torpid vampire is not a legal target.
3. "After this vampire goes to torpor, their controller burns 3 pool." --
   "their" is the host vampire's own controller, not necessarily Fame's own
   controller (`CardAttachment.controller`, "whoever played it") -- the two
   can differ since clause 2 allows Fame on either player's vampire. A
   mandatory, no-choice reaction at the torpor transition, dispatched by
   `engine/damage.py::send_to_torpor` via the new
   `VAMPIRE_ENTERS_TORPOR_HOOK`. Only fires while Fame's attachment is
   `zone == "attached"`: a contested copy is "turned face down and out of
   play" (Rulebook §4 Advanced Rules > Contested Cards) and cannot react
   (OQ-22's addendum note (c): a future numeric/effect-granting attachment
   must gate its own contribution on `zone == "attached"`).
4. "During each Methuselah's unlock phase, if this vampire is in torpor,
   that Methuselah burns 1 pool." -- a second mandatory, no-choice
   reaction, checked during *every* Methuselah's own unlock phase ("that
   Methuselah" refers to "each Methuselah": both players, independently,
   for as long as the host vampire stays in torpor), gated on the host's
   current zone and Fame's own `zone == "attached"` (same contest-aware
   gating as clause 3). Dispatched by `engine/phases/unlock.py::unlock_phase`
   via the new `UNLOCK_PHASE_MANDATORY_EFFECT_HOOK`.

Status: IMPLEMENTED. OQ-22 built the Contested Cards machinery for a
`CardAttachment` (`engine/attachments.py::attach_card`/
`detect_contest_on_attach`/`resolve_one_attachment_contest`,
`engine/phases/unlock.py::_unlock_own_attachments`'s extended pay-or-yield
loop) -- clause 1 is fully enforced with no special-casing here: this
module's `"master_phase_play"` provider only needs to call `attach_card` +
`detect_contest_on_attach` (confirmed against
`tests/rules/test_attachment_contests.py`/
`test_attachment_contest_resolution.py`, which already use Fame's krcg id
as their stand-in). Clauses 3 and 4 add two new mandatory-effect hook
dispatch sites (`VAMPIRE_ENTERS_TORPOR_HOOK`,
`UNLOCK_PHASE_MANDATORY_EFFECT_HOOK`); both call sites had access to
everything Fame's text needs, so no Open Question was needed for either.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.attachments import attach_card, detect_contest_on_attach, iter_attachments
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.pool import lose_pool
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 100698
MASTER_PHASE_PLAY_HOOK = "master_phase_play"
VAMPIRE_ENTERS_TORPOR_HOOK = "vampire_enters_torpor"
UNLOCK_PHASE_MANDATORY_EFFECT_HOOK = "unlock_phase_mandatory_effect"
CARD_TYPE = "Master"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): matches
this module's own "Card type: Master" docstring fact above."""


def _active_fame_attachment(vampire: VampireInPlay) -> CardAttachment | None:
    """Fame's own attachment on `vampire`, only while actually in play
    (`zone == "attached"`) -- a contested or burned copy is "turned face
    down and out of play" and must not react (OQ-22's own addendum note on
    a future numeric/effect-granting attachment's own gating
    responsibility)."""
    for attachment in vampire.attachments:
        if attachment.krcg_id == KRCG_ID and attachment.zone == "attached":
            return attachment
    return None


def _eligible_targets(state: GameState) -> list[VampireInPlay]:
    """ "Put this card on a ready vampire" -- either player's, `zone ==
    "ready"` only (stricter than Celerity's own `_eligible_targets`, which
    also allows a torpid vampire: Fame's own text explicitly narrows to
    "ready")."""
    targets: list[VampireInPlay] = []
    for player_state in state.players.values():
        for vampire in player_state.vampires.values():
            if vampire.zone == "ready":
                targets.append(vampire)
    return targets


def _provide_fame_master_phase_play(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    player = context["player"]
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    targets = _eligible_targets(state)
    if not targets:
        return []

    options: list[HookOption] = []
    for vampire in targets:

        def _apply(s: GameState, vampire: VampireInPlay = vampire) -> bool:
            play_from_hand(s, player, KRCG_ID)
            # Rulebook §2 Card Types, "Master Cards": controlled by whoever
            # played it, which may differ from `vampire.controller` -- the
            # only case `attach_card` has a real caller for today (OQ-22).
            attachment = attach_card(s, vampire, controller=player, krcg_id=KRCG_ID, name="Fame")
            detect_contest_on_attach(s, attachment)
            return False  # not a trifle: no extra master phase action.

        options.append(
            HookOption(
                choice=Choice(
                    f"fame:{vampire.instance_id}",
                    f"Fame: attach to {vampire.card.name} ({vampire.controller})",
                ),
                apply=_apply,
                played_card_type=CARD_TYPE,
            )
        )
    return options


def _provide_vampire_enters_torpor(state: GameState, context: Mapping[str, Any]) -> None:
    """Clause 3: "After this vampire goes to torpor, their controller burns
    3 pool." "Their" is the host vampire's own controller, not necessarily
    Fame's own controller (`CardAttachment.controller`, "whoever played
    it") -- the two may differ (clause 2 allows either player's vampire as
    a target)."""
    vampire = context["vampire"]
    if _active_fame_attachment(vampire) is None:
        return
    lose_pool(state, vampire.controller, 3)


def _provide_unlock_phase_pool_burn(state: GameState, context: Mapping[str, Any]) -> None:
    """Clause 4: "During each Methuselah's unlock phase, if this vampire is
    in torpor, that Methuselah burns 1 pool." "That Methuselah" is whoever's
    unlock phase is currently running (`context["player"]`), independent of
    both Fame's own controller and the host vampire's own controller -- both
    Methuselahs burn 1 pool on their own respective unlock phases for as
    long as the host vampire remains in torpor."""
    player = context["player"]
    for vampire, attachment in iter_attachments(state):
        if (
            attachment.krcg_id == KRCG_ID
            and attachment.zone == "attached"
            and vampire.zone == "torpor"
        ):
            lose_pool(state, player, 1)


hooks.register(MASTER_PHASE_PLAY_HOOK, _provide_fame_master_phase_play)
hooks.register(VAMPIRE_ENTERS_TORPOR_HOOK, _provide_vampire_enters_torpor)
hooks.register(UNLOCK_PHASE_MANDATORY_EFFECT_HOOK, _provide_unlock_phase_pool_burn)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Fame",
        status=Status.IMPLEMENTED,
        hooks=(
            Hook.MASTER_PHASE_PLAY,
            Hook.VAMPIRE_ENTERS_TORPOR,
            Hook.UNLOCK_PHASE_MANDATORY_EFFECT,
        ),
        source=__name__,
    )
)
