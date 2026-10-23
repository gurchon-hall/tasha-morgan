"""Rolling with the Punches (Combat). krcg 101649. Snapshot: data/cards/101649.json
[FOR]'s blood burn is an effect, not a cost: never reduced, and the card is
unplayable without the blood [ANK 20210226]. Rest of the round: ENG-036."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire, discipline_level, has_discipline
from vtesbot.engine.damage import mark_mandatory_full_prevention_active
from vtesbot.engine.hook_contexts import DamagePreventionContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState

KRCG_ID = 101649

card = Card(KRCG_ID, "Rolling with the Punches", "Combat")


def _prevent_one_point(damage_box: dict[str, int]) -> None:
    """Any damage type. `apply_damage` passes one type per call, so both being
    positive is an engine bug, not a game state."""
    normal = damage_box.get("normal", 0)
    aggravated = damage_box.get("aggravated", 0)
    if normal > 0 and aggravated > 0:
        raise AssertionError(
            "rolling_with_the_punches: damage_box has both normal and aggravated "
            "damage at once, which no production call site produces today "
            "(engine invariant violation, not a legal game state)"
        )
    if aggravated > 0:
        damage_box["aggravated"] = aggravated - 1
    elif normal > 0:
        damage_box["normal"] = normal - 1


@card.on(Hook.DAMAGE_PREVENTION)
def _provide_prevent(state: GameState, ctx: DamagePreventionContext) -> list[HookOption]:
    """Not offered without damage to prevent [LSJ 20001114]. [FOR] also clears
    the current strike, then prevents the rest of the round unasked."""
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or not has_discipline(state, vampire, "for"):
        return []
    if not card.in_hand(state, player):
        return []
    damage_box = ctx["damage"]
    if damage_box.get("normal", 0) <= 0 and damage_box.get("aggravated", 0) <= 0:
        return []

    def _apply_basic(s: GameState) -> None:
        card.play_from_hand(s, player)
        _prevent_one_point(damage_box)

    options = [
        card.option(
            "rolling_with_the_punches:basic",
            "Rolling with the Punches [for]: prevent 1 damage",
            _apply_basic,
        )
    ]
    if discipline_level(state, vampire, "for") == 2 and vampire.blood >= 1:
        round_state = ctx["round_state"]

        def _apply_superior(s: GameState) -> None:
            card.play_from_hand(s, player)
            vampire.blood -= 1
            damage_box["normal"] = 0
            damage_box["aggravated"] = 0
            mark_mandatory_full_prevention_active(round_state, vampire.instance_id)

        options.append(
            card.option(
                "rolling_with_the_punches:superior",
                "Rolling with the Punches [FOR]: burn 1 blood, prevent all damage this round",
                _apply_superior,
            )
        )
    return options
