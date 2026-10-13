"""Diana Iadanza (crypt vampire ability). krcg id 201694.

Card text (verbatim, krcg, `data/cards/201694.json`, re-verified live
2026-10-13, `https://api.krcg.org/card/201694`): "Camarilla Toreador
Justicar: During a referendum she calls, Diana can burn 1 blood to cancel
a reaction card as it is played (cost is still paid). +1 bleed." Toreador,
Justicar, group 7, capacity 9.

Clause 1: phrased in Rulebook §3's "During X, do Y" wording template --
"only one Y can be done per X with this card" -- so she may cancel at
most **once per referendum she calls** (`docs/OPEN_QUESTIONS.md` OQ-33's
own correction; the generic "cancel as played" rulings on file are
mechanic-generic, not Diana-specific, and do not themselves cap her).
`CANCEL_AS_PLAYED_HOOK`/`played_card_type` (OQ-32, OQ-33, both resolved)
now give a provider everything needed to cancel only a genuine Reaction
card, not Modius'/Oxford University, England's own non-Reaction options in
the same polling-step window. Still not built: a provider plus the
once-per-referendum usage tracking, scoped to the specific referendum
instance -- `card-implementer` scope, no further engine gap.

Clause 2 ("+1 bleed"): flat, unconditional; built against
`BLEED_AMOUNT_FIXED_MODIFIER_HOOK`.

CLAUDE.md §6: status is per whole card -- stays `Status.BLOCKED` until
clause 1 is built too.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.state import GameState

KRCG_ID = 201694
BLEED_AMOUNT_FIXED_MODIFIER_HOOK = "bleed_amount_fixed_modifier"


def _provide_diana_bleed(state: GameState, context: Mapping[str, Any]) -> int:
    player = context["player"]
    vampire = state.players[player].vampires.get(context["vampire"])
    if vampire is None or vampire.card.krcg_id != KRCG_ID:
        return 0
    return 1


hooks.register(BLEED_AMOUNT_FIXED_MODIFIER_HOOK, _provide_diana_bleed)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Diana Iadanza",
        status=Status.BLOCKED,
        hooks=(Hook.CANCEL_AS_PLAYED, Hook.BLEED_AMOUNT_FIXED_MODIFIER),
        source=__name__,
        blocked_reason="OQ-33",
    )
)
