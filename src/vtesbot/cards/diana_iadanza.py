"""Diana Iadanza (crypt vampire ability). krcg id 201694.

Card text (verbatim, krcg, `data/cards/201694.json`, re-verified live
2026-10-13, `https://api.krcg.org/card/201694`): "Camarilla Toreador
Justicar: During a referendum she calls, Diana can burn 1 blood to cancel
a reaction card as it is played (cost is still paid). +1 bleed." Toreador,
Justicar, group 7, capacity 9.

Clause 1: built against `CANCEL_AS_PLAYED_HOOK`/`played_card_type`
(`docs/OPEN_QUESTIONS.md` OQ-32/OQ-33, both resolved), gated to the side
holding a Diana her controller actually called the referendum with
(`context["caller_vampire_id"]` resolved against `context["player"]`'s own
vampires, `card.krcg_id == KRCG_ID`) and to a canceled option whose
`played_card_type == "Reaction"` -- never Modius'/Oxford University,
England's own non-Reaction options reachable in the same polling-step
window. Capped at once per referendum: Rulebook §3 "Wording templates" >
"During X, do Y", verbatim, "only one Y can be done per X with this card"
(`data/sources/rulebook/2026-10-09/3-playing-the-game.md` lines 86-91) --
a separate fact from OQ-33's own "ruling check," which found the 5
on-file rulings for the generic "cancel as played" mechanic say nothing
about a referendum-level cap (they govern the mechanic itself: cost still
paid, immediate, no other effects -- already proven generically by
`tests/rules/test_hooks.py`/OQ-32). Tracked in `context["pending"]
["diana_iadanza_canceled"]`, naturally scoped to one `resolve_referendum`
call (a fresh `pending` dict per call, `engine/politics.py`).

Clause 2 ("+1 bleed"): flat, unconditional; built against
`BLEED_AMOUNT_FIXED_MODIFIER_HOOK`.

No `POLLING_STEP_HOOK` provider in the pool offers a
`played_card_type="Reaction"` option today, so clause 1 is dormant in real
games (CLAUDE.md "only when needed"); tests exercise it with a temporary
fake provider, mirroring `tests/rules/test_hooks.py`'s own OQ-33 proof.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 201694
BLEED_AMOUNT_FIXED_MODIFIER_HOOK = "bleed_amount_fixed_modifier"
CANCELED_REACTION_CARD_TYPE = "Reaction"
PENDING_CANCELED_KEY = "diana_iadanza_canceled"
BLOOD_COST = 1


def _provide_diana_bleed(state: GameState, context: Mapping[str, Any]) -> int:
    player = context["player"]
    vampire = state.players[player].vampires.get(context["vampire"])
    if vampire is None or vampire.card.krcg_id != KRCG_ID:
        return 0
    return 1


def _provide_diana_cancel(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    """Clause 1: see module docstring for the gating/once-per-referendum
    cap sourcing."""
    if context.get("canceled_card_type") != CANCELED_REACTION_CARD_TYPE:
        return []
    player = context["player"]
    caller_vampire_id = context.get("caller_vampire_id")
    if caller_vampire_id is None:
        return []
    diana = state.players[player].vampires.get(caller_vampire_id)
    if diana is None or diana.card.krcg_id != KRCG_ID:
        return []
    if diana.blood < BLOOD_COST:
        return []
    pending = context.get("pending")
    if pending is None or pending.get(PENDING_CANCELED_KEY, False):
        return []

    def _apply(s: GameState) -> None:
        diana.blood -= BLOOD_COST
        pending[PENDING_CANCELED_KEY] = True

    return [
        HookOption(
            choice=Choice(
                f"diana_iadanza_cancel:{diana.instance_id}",
                "Diana Iadanza: burn 1 blood to cancel a reaction card as it is played",
            ),
            apply=_apply,
            # `played_card_type` stays at its default `None`: this option is
            # Diana's own printed ability being activated, not a card being
            # played.
        )
    ]


hooks.register(BLEED_AMOUNT_FIXED_MODIFIER_HOOK, _provide_diana_bleed)
hooks.register(hooks.CANCEL_AS_PLAYED_HOOK, _provide_diana_cancel)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Diana Iadanza",
        status=Status.IMPLEMENTED,
        hooks=(Hook.CANCEL_AS_PLAYED, Hook.BLEED_AMOUNT_FIXED_MODIFIER),
        source=__name__,
    )
)
