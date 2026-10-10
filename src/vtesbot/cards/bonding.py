"""Bonding (Action Modifier). krcg id 100236.

Card text (verified live via `krcg.load()[100236]`, 2026-10-09, matching the
raw snapshot `data/cards/100236.json`):
    "Only usable during a bleed action.
    [dom] +1 bleed (limited).
    [DOM] +1 stealth and +1 bleed (limited)."

Rulings (verbatim, via krcg):
    - "[DOM] Cannot be used if you do not need the stealth at the time you
      play it." [TOM 19951109]
    - "[DOM] Cannot be used to increase the stealth of a non-bleed action."
      [LSJ 19980824] [RTR 19941109]

Card type: Action Modifier. `discipline_requirement.disciplines == ["dom"]`
(basic Dominate required to play the card at all; superior Dominate,
printed uppercase `"DOM"` on a `CryptCard`, additionally unlocks the
bold-text effect -- Rulebook SS3 "Discipline symbol within a diamond ... may
opt to use either the basic (plain text) or the superior (bold) effect ...
but not both"). `cost is None` (free).

Status: implemented (OQ-11, `docs/OPEN_QUESTIONS.md`, now resolved -- the
engine's `pending: dict[str, Any]` per-minion-action scratch container,
`engine/action.py::perform_minion_action`, closed the gap this card was
previously blocked on).

Two clauses, two different hooks (one physical card, choose a level when you
play it, exactly the "basic vs superior" shape already used by
`threats.py`/`telepathic_counter.py`/`celerity.py`):

"[dom] +1 bleed (limited)" (the basic clause): a clean `"bleed_amount_modifier"`
provider, byte-for-byte the same pattern as `threats.py` -- offered only to
the acting (bleeding) player (checked by looking the acting vampire up in
`context["player"]`'s own `vampires` dict, same as Threats), requiring at
least basic Dominate (`"dom"` or `"DOM"` in the vampire's disciplines). "Only
usable during a bleed action": *not* re-checked via `context.get("action")`
here, unlike the superior clause below -- verified directly against
`engine/phases/minion.py::_perform_bleed`'s `resolve()` closure, the
`"bleed_amount_modifier"` hook's context is `{"vampire": ..., "amount":
amount_box, "pending": pending}`, with no `"action"` key at all (unlike the
`"stealth_modifier"`/`"intercept_modifier"` hooks' context, which does carry
one per OQ-9). Gating on `context.get("action") == ACTION_BLEED` here would
therefore always read `None != "bleed"` and silently suppress this clause
entirely -- exactly the "silent mis-resolution" CLAUDE.md forbids. The
restriction is instead "trivially satisfied by which hook this card
registers against" (`threats.py`'s own words): `"bleed_amount_modifier"` is
only ever offered from `_perform_bleed`, never from `_perform_hunt`, so no
extra check is needed or correct here.

"[DOM] +1 stealth and +1 bleed (limited)" (the superior clause): a
`"stealth_modifier"` provider, requiring superior Dominate (`"DOM"`). Unlike
the basic clause's hook, `"stealth_modifier"`'s context *does* carry
`context["action"]` (OQ-9), so the "[DOM] Cannot be used to increase the
stealth of a non-bleed action" ruling is enforced with an explicit
`context.get("action") != ACTION_BLEED: return []` gate -- this hook is
shared with hunt and political-action's own stealth ping-pong
(`engine/phases/minion.py::_perform_hunt`, `engine/politics.py::
political_action`), so hook selection alone does not suffice here the way it
does for the basic clause. The other ruling, "[DOM] Cannot be used if you do
not need the stealth at the time you play it", needs no extra code at all:
`engine/action.py::_duel_stealth_intercept`'s own "only when needed"
ping-pong (module docstring) only ever calls `hooks.offer(STEALTH_MODIFIER_
HOOK, ...)` on the half of the loop where `intercept >= stealth` ("block
currently succeeds" = stealth is needed to escape it); the other half
(`stealth > intercept`, stealth not needed) offers `INTERCEPT_MODIFIER_HOOK`
to the defender instead, so this provider -- registered only against
`"stealth_modifier"` -- is simply never invoked at all while stealth is not
needed. This single play must also deliver the clause's own "+1 bleed" from
the very same provider call, read much later by `_perform_bleed`'s
`resolve()` (OQ-11): `apply()` both returns `1` (the `"stealth_modifier"`
hook's own `int`-delta contract, consumed immediately by `_duel_stealth_
intercept`) *and* stashes `pending[PENDING_BLEED_AMOUNT_KEY] =
pending.get(PENDING_BLEED_AMOUNT_KEY, 0) + 1` (accumulating with `+=` rather
than overwriting, in case a future different source also stashes into the
same key), which `_perform_bleed`'s `resolve()` folds into `base_amount`
*before* the separately-clamped `"bleed_amount_modifier"` window runs,
exactly the mechanism OQ-11's resolution built and
`tests/rules/test_pending_modifier.py` proves end-to-end with a fake
stand-in provider; this module wires the real card against it.

Rulebook SS3 "may opt to use either the basic or the superior effect ... but
not both": a superior-Dominate vampire is eligible for *both* providers above,
but the two fire in different hook windows at different times within the
same minion action -- the superior clause can only ever be legally offered
while a block attempt is in progress and stealth is currently needed (see
above); if the defender never attempts a block at all this action, "you do
not need the stealth" for the entire remainder of the action (there is
nothing to escape), so the superior clause is never offered, and the
*basic* clause (requiring only `"dom"`/`"DOM"`, i.e. always satisfied by a
superior-Dominate vampire too) remains available in the later
`"bleed_amount_modifier"` window -- the vampire ends up using "only" the
basic effect this time, exactly SS3's "may opt to use either effect"
(`tests/cards/test_bonding.py::test_superior_vampire_may_opt_to_use_the_
basic_effect_instead_when_no_block_is_attempted`). Conversely, if a block
*is* attempted, declining the superior clause's own offer does not lead to
"use the basic effect instead": declining ends the stealth/intercept
ping-pong immediately with the block still succeeding at the current
intercept (bleed's own base stealth is 0, so `intercept(0) >= stealth(0)` is
trivially already true the instant any blocker is chosen), so the action is
*blocked* (combat follows) and the later bleed-amount window is never
reached at all -- not a second, independent chance to fall back to the
basic effect. Both branches are tested.

"(limited)" (SS8 glossary: "an action modifier card cannot be played to
increase the bleed if the bleed amount is already being increased by
another action modifier card"; SS2: "A minion cannot play the same action
modifier card more than once during a single action (even if using a
different Discipline level)"): tracked via the per-*action* (not merely
per-window) `bleed_bookkeeping` scratch space now keyed off `pending`
(`vtesbot.cards._shared`, refactored this pass from its previous `amount_box`
-- which only existed during the later window and could not see a "(limited)"
increase played earlier, from the stealth window, in the same action --  to
`pending`, which spans the whole action; see `_shared.py`'s own updated
docstring). `LIMITED_USED_KEY` is imported directly from `threats.py` (the
same shared flag) rather than redefined, so Bonding's basic clause,
Bonding's superior clause, and Threats correctly exclude one another for the
rest of one action regardless of which hook window each fires in or which
one goes first.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import bleed_bookkeeping, play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.cards.threats import LIMITED_USED_KEY
from vtesbot.engine import hooks
from vtesbot.engine.action import ACTION_BLEED
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import PENDING_BLEED_AMOUNT_KEY
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 100236
BLEED_AMOUNT_MODIFIER_HOOK = "bleed_amount_modifier"
STEALTH_MODIFIER_HOOK = "stealth_modifier"
BASIC = "dom"
SUPERIOR = "DOM"


def _find_vampire(state: GameState, player: str, vampire_id: str | None) -> VampireInPlay | None:
    if vampire_id is None:
        return None
    return state.players[player].vampires.get(vampire_id)


def _provide_bonding_basic(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[dom] +1 bleed (limited)" -- see module docstring for why this clause
    needs no `context["action"]` check: the hook it registers against is
    only ever offered from a bleed action's own resolution step."""
    player = context["player"]
    acting_vampire_id = context["vampire"]
    acting_vampire = state.players[player].vampires.get(acting_vampire_id)
    if acting_vampire is None:
        return []  # `player` is the defender this turn of the impulse window, not the bleeder.

    disciplines = acting_vampire.card.disciplines
    if BASIC not in disciplines and SUPERIOR not in disciplines:
        return []
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    pending = context["pending"]
    book = bleed_bookkeeping(pending)
    if book.get(LIMITED_USED_KEY):
        return []

    amount_box = context["amount"]

    def _apply(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)
        amount_box[0] += 1
        book[LIMITED_USED_KEY] = True

    return [
        HookOption(
            choice=Choice("bonding:basic", "Bonding [dom]: +1 bleed (limited)"),
            apply=_apply,
        )
    ]


def _provide_bonding_superior(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """ "[DOM] +1 stealth and +1 bleed (limited)" -- see module docstring for
    the `context["action"]` gate (ruling: "[DOM] Cannot be used to increase
    the stealth of a non-bleed action") and the `pending`-stash mechanism
    (OQ-11) that carries the "+1 bleed" half forward to `_perform_bleed`'s
    later `resolve()`. The "cannot be used if you do not need the stealth"
    ruling needs no code here at all: `_duel_stealth_intercept` only ever
    calls `hooks.offer("stealth_modifier", ...)` on the half of its ping-pong
    where stealth is currently needed (module docstring)."""
    if context.get("action") != ACTION_BLEED:
        return []

    player = context["player"]  # this hook is only ever offered to the acting player.
    acting_vampire = _find_vampire(state, player, context.get("acting_vampire"))
    if acting_vampire is None:
        return []

    if SUPERIOR not in acting_vampire.card.disciplines:
        return []
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    pending = context["pending"]
    book = bleed_bookkeeping(pending)
    if book.get(LIMITED_USED_KEY):
        return []

    def _apply(s: GameState) -> int:
        play_from_hand(s, player, KRCG_ID)
        book[LIMITED_USED_KEY] = True
        pending[PENDING_BLEED_AMOUNT_KEY] = pending.get(PENDING_BLEED_AMOUNT_KEY, 0) + 1
        return 1  # +1 stealth, delivered from the very same play as the stashed +1 bleed.

    return [
        HookOption(
            choice=Choice("bonding:superior", "Bonding [DOM]: +1 stealth and +1 bleed (limited)"),
            apply=_apply,
        )
    ]


hooks.register(BLEED_AMOUNT_MODIFIER_HOOK, _provide_bonding_basic)
hooks.register(STEALTH_MODIFIER_HOOK, _provide_bonding_superior)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Bonding",
        status=Status.IMPLEMENTED,
        hooks=(Hook.BLEED_AMOUNT_MODIFIER, Hook.STEALTH_MODIFIER),
        source=__name__,
    )
)
