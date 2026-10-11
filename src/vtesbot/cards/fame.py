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
effect." Re-verified 2026-10-11 directly against the *installed* krcg
package (`krcg.vtes.VTES.load()[100698].rulings`), which attributes this
ruling to "[LSJ 20010121]" (reference URL
<https://boardgamegeek.com/thread/609699/article/6142361#6142361>). This
resolves a date-format discrepancy the original BLOCKED-status docstring
flagged but did not settle: the raw snapshot `data/cards/100698.json` (a
cache of what the *live* `https://api.krcg.org/card/100698` endpoint
returned when it was fetched) attributes the identical ruling text to
"[LSJ 20110121]" instead, with a different reference URL
(<https://usenet.krcg.org/t/bgg-609699/#m1>) -- both plainly point at the
same underlying 2001-era LSJ ruling (the BGG thread itself is numbered
609699, matching both references' own URLs), so "20110121" is the stray
one; the installed package's own value, "[LSJ 20010121]", is cited here as
the correct date. Cosmetic either way (CLAUDE.md "never invent... a
ruling" is about substance, and the substance -- the ruling's own text --
is identical in both sources), but the installed package is the one cited
going forward.

This ruling confirms the unlock-phase pool burn is an *orderable* mandatory
effect: the acting Methuselah may interleave it with their own other
unlock-phase effects (contested-card pay-or-yield, Edge pool gain) in
whatever order they like, but must finish before passing the impulse. In
practice, because Fame's own unlock-phase effect (clause 4 below) has *no
legal alternative* -- it is a flat, unconditional "burn 1 pool", never a
choice between two options the way a contested card's pay-or-yield is --
"ordering" it relative to the player's other, genuinely optional
unlock-phase effects cannot change its own outcome either way (see
`engine/phases/unlock.py::UNLOCK_PHASE_MANDATORY_EFFECT_HOOK`'s own
docstring for where this is dispatched and why resolving it first is
faithful to the ruling rather than a shortcut around it).

Clauses:
1. "Unique." -- governs contest, not initial legality to play (resolved by
   OQ-22 below): nothing stops either Methuselah from independently playing
   their own separately-decked copy of Fame while another copy is already
   attached and uncontested -- that is exactly the situation that triggers
   a contest between the two copies.
2. "Put this card on a ready vampire." -- a `CardAttachment`
   (`engine/attachments.py::attach_card`) on a vampire whose `zone ==
   "ready"` *at the moment of play*, either player's (the text carries no
   clan/discipline restriction and no "you control" qualifier, mirroring
   Celerity's own "Discipline" targeting precedent, OQ-8 -- Rulebook SS2
   Card Types, "A master card in play is controlled by the Methuselah who
   played it, even if it is played on a card controlled by another
   Methuselah"). Unlike Celerity's own targeting (which also allows a
   *torpid* vampire, since Celerity's text says merely "a vampire" and the
   Rulebook SS8 glossary "Target" rule makes torpor-region vampires
   eligible targets by default), Fame's own printed text explicitly narrows
   this to "a ready vampire" -- a torpid vampire is not a legal target,
   a stricter filter than Celerity's own `_eligible_targets` applies.
3. "After this vampire goes to torpor, their controller burns 3 pool." --
   "their" is the host vampire's own controller (`VampireInPlay.controller`),
   *not* necessarily Fame's own controller (`CardAttachment.controller`,
   "whoever played it") -- the two can differ, since clause 2 allows Fame
   to be played onto either player's vampire. A mandatory, no-choice
   reaction at the moment of the torpor transition, dispatched by
   `engine/damage.py::send_to_torpor` (the single call site every vampire's
   zone flips to `"torpor"` through) via the new `VAMPIRE_ENTERS_TORPOR_HOOK`
   (`hooks.run_effects`; `cards/registry.py::Hook.VAMPIRE_ENTERS_TORPOR`).
   Only fires while Fame's own attachment is `zone == "attached"` (not
   `"contested"`/`"burned"`): a contested copy is "turned face down and out
   of play" (Rulebook SS4 Advanced Rules > Contested Cards) and so cannot be
   reacting to anything, mirroring OQ-22's own addendum note (c) that any
   future numeric/effect-granting attachment must gate its own contribution
   on `zone == "attached"` itself.
4. "During each Methuselah's unlock phase, if this vampire is in torpor,
   that Methuselah burns 1 pool." -- a second mandatory, no-choice
   reaction, checked during *every* Methuselah's own unlock phase (not just
   Fame's own controller's, and not just the host vampire's own
   controller's -- "that Methuselah" refers back to "each Methuselah" in the
   sentence, i.e. both Methuselahs independently, each during their own
   unlock phase, for as long as the host vampire stays in torpor), gated
   only on the attached vampire's current zone and Fame's own `zone ==
   "attached"` (same contest-aware gating as clause 3). Dispatched by
   `engine/phases/unlock.py::unlock_phase` via the new
   `UNLOCK_PHASE_MANDATORY_EFFECT_HOOK` (`hooks.run_effects`;
   `cards/registry.py::Hook.UNLOCK_PHASE_MANDATORY_EFFECT`).

Status: IMPLEMENTED. `docs/OPEN_QUESTIONS.md` OQ-22 (resolved by a
`rules-engineer` pass, independently reviewed by `rules-auditor`) built the
missing Contested Cards machinery for a `CardAttachment`
(`engine/attachments.py::attach_card`/`detect_contest_on_attach`/
`resolve_one_attachment_contest`, `engine/phases/unlock.py::
_unlock_own_attachments` and its extended pay-or-yield loop) -- clause 1 is
now fully enforced with no special-casing in this module: `attach_card` +
`detect_contest_on_attach`, called from this module's own
`"master_phase_play"` provider, is all that is needed, and the existing
`"contest_attachment:"`-prefixed unlock-phase machinery resolves a contested
Fame with no Fame-specific code required there at all (confirmed directly
against `tests/rules/test_attachment_contests.py`/
`test_attachment_contest_resolution.py`, which already use Fame's own krcg
id as their stand-in). This pass (`card-implementer`) wires clauses 3 and
4, adding the two new mandatory-effect hook dispatch sites named above
(neither existed before this pass; `cards/registry.py::Hook` had no member
reserved for either, unlike `REFERENDUM_TALLIED`, which OQ-6's own pass had
already reserved ahead of Marcos Belegrad's build) -- both call sites
cleanly had access to everything Fame's own text needs (which vampire went
to torpor and its controller; which attachments are in play and their own
host vampire's current zone), so no fresh Open Question was needed for
either.
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
            # Rulebook SS2 Card Types, "Master Cards": controlled by whoever
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
