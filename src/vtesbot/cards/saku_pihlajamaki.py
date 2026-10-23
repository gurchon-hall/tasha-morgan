"""Saku Pihlajamäki (Vampire). krcg 201658. Snapshot: data/cards/201658.json
His Baron votes come from the generic title table. The used flag lives in
`combat_state`, so the maneuver comes back with each new combat."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire
from vtesbot.engine.hook_contexts import ManeuverContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 201658
_USED_KEY = "saku_pihlajamaki_maneuver_used"

card = Card(KRCG_ID, "Saku Pihlajamäki")


@card.on(Hook.MANEUVER)
def _maneuver(state: GameState, ctx: ManeuverContext) -> list[HookOption]:
    vampire = context_vampire(state, ctx)
    if vampire is None or vampire.card.krcg_id != KRCG_ID:
        return []
    vampire_id = ctx["vampire"]
    used = ctx["combat_state"].setdefault(_USED_KEY, set())
    if vampire_id in used:
        return []

    def _apply(_s: GameState) -> None:
        used.add(vampire_id)

    return [card.option("saku_pihlajamaki_maneuver", "Saku Pihlajamäki's maneuver", _apply)]
