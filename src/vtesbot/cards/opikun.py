"""Opikun (Vampire). krcg 201680. Snapshot: data/cards/201680.json
Offered for combat strike damage only (`combat_state` set). Opikun pays from her
own blood, even from torpor [LSJ 20011022]; once per combat per copy."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire
from vtesbot.engine.hook_contexts import DamagePreventionContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 201680
BLOOD_COST = 1
PREVENT_AMOUNT = 2
IN_PLAY_ZONES = ("ready", "torpor")
USED_KEY = "opikun_used_this_combat"

card = Card(KRCG_ID, "Opikun")


def _prevent_non_aggravated(damage_box: dict[str, int], amount: int) -> None:
    """Never touches aggravated damage [LSJ 20040812-2] [PIB 20130327]."""
    normal = damage_box.get("normal", 0)
    damage_box["normal"] = normal - min(amount, normal)


@card.on(Hook.DAMAGE_PREVENTION)
def _provide_opikun(state: GameState, ctx: DamagePreventionContext) -> list[HookOption]:
    player, combat_state, damage_box = ctx["player"], ctx["combat_state"], ctx["damage"]
    if combat_state is None or damage_box.get("normal", 0) <= 0:
        return []
    damaged = context_vampire(state, ctx)
    damaged_name = damaged.card.name if damaged is not None else "that vampire"
    used = combat_state.setdefault(USED_KEY, set())
    options: list[HookOption] = []
    for opikun in state.players[player].vampires.values():
        if opikun.card.krcg_id != KRCG_ID or opikun.zone not in IN_PLAY_ZONES:
            continue
        if opikun.instance_id in used or opikun.blood < BLOOD_COST:
            continue

        def _apply(_s: GameState, opikun: VampireInPlay = opikun) -> None:
            opikun.blood -= BLOOD_COST
            used.add(opikun.instance_id)
            _prevent_non_aggravated(damage_box, PREVENT_AMOUNT)

        options.append(
            card.option(
                f"opikun:{opikun.instance_id}",
                f"Opikun: burn 1 blood to prevent up to 2 non-aggravated damage to {damaged_name}",
                _apply,
            )
        )
    return options
