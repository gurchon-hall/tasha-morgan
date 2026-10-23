"""Soak (Combat). krcg 101817. Snapshot: data/cards/101817.json
Both levels are offered when eligible (Rulebook §3). The once-per-round cap is
a per-vampire flag in `round_state` (ENG-036)."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire, discipline_level, has_discipline
from vtesbot.engine.hook_contexts import DamagePreventionContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 101817
BASIC_PREVENT = 2
SUPERIOR_PREVENT = 4
_SOAK_USED_KEY = "soak_used"

card = Card(KRCG_ID, "Soak", "Combat")


def _prevent_non_aggravated(damage_box: dict[str, int], amount: int) -> None:
    """Never touches aggravated damage [LSJ 20040812-2] [PIB 20130327]."""
    normal = damage_box.get("normal", 0)
    damage_box["normal"] = normal - min(amount, normal)


@card.on(Hook.DAMAGE_PREVENTION)
def _provide_soak(state: GameState, ctx: DamagePreventionContext) -> list[HookOption]:
    """Not offered without normal damage to prevent [LSJ 20001114]."""
    player, vampire_id, vampire = ctx["player"], ctx["vampire"], context_vampire(state, ctx)
    round_state, damage_box = ctx["round_state"], ctx["damage"]
    if vampire is None or not card.in_hand(state, player):
        return []
    if round_state is not None and round_state.get(_SOAK_USED_KEY, {}).get(vampire_id):
        return []  # "A vampire can play only one Soak each round."
    if damage_box.get("normal", 0) <= 0:
        return []

    def _option(value: str, label: str, amount: int) -> HookOption:
        def _apply(s: GameState) -> None:
            card.play_from_hand(s, player)
            if round_state is not None:
                round_state.setdefault(_SOAK_USED_KEY, {})[vampire_id] = True
            _prevent_non_aggravated(damage_box, amount)

        return card.option(value, label, _apply)

    options: list[HookOption] = []
    if has_discipline(state, vampire, "for"):
        options.append(
            _option("soak:basic", "Soak [for]: prevent 2 non-aggravated damage", BASIC_PREVENT)
        )
    if discipline_level(state, vampire, "for") == 2:
        options.append(
            _option(
                "soak:superior", "Soak [FOR]: prevent 4 non-aggravated damage", SUPERIOR_PREVENT
            )
        )
    return options
