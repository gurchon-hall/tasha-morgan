"""Precognition (Reaction). krcg 101475. Snapshot: data/cards/101475.json
[AUS] leaves a grant that only the successful blocker can claim, in round 1 of
the resulting combat [LSJ 20010813] [LSJ 20010819-2]. See ENG-040."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import discipline_level, has_discipline
from vtesbot.engine.action import grant_block_time_combat_effect
from vtesbot.engine.combat import block_time_combat_grant_available, consume_block_time_combat_grant
from vtesbot.engine.damage import is_round_one
from vtesbot.engine.hook_contexts import DamagePreventionContext, InterceptModifierContext, Pending
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101475
NAME = "Precognition"
INTERCEPT_BONUS = 1
GRANT_NAME = "precognition_round_one_prevention"
USED_BY_KEY = "precognition_used_by"

card = Card(KRCG_ID, NAME, "Reaction")


@card.on(Hook.INTERCEPT_MODIFIER)
def _provide_precognition_intercept(
    state: GameState, ctx: InterceptModifierContext
) -> list[HookOption]:
    player = ctx["player"]
    if not card.in_hand(state, player):
        return []
    pending: Pending | None = ctx["pending"]
    used_by: set[str] = set() if pending is None else pending.setdefault(USED_BY_KEY, set())
    eligible = [
        v
        for v in state.players[player].vampires.values()
        if v.is_ready_unlocked and v.instance_id not in used_by and has_discipline(state, v, "aus")
    ]
    options: list[HookOption] = []
    for vampire in eligible:

        def _apply_basic(s: GameState, v: VampireInPlay = vampire) -> int:
            card.play_from_hand(s, player)
            used_by.add(v.instance_id)
            return INTERCEPT_BONUS

        def _apply_superior(s: GameState, v: VampireInPlay = vampire) -> int:
            card.play_from_hand(s, player)
            used_by.add(v.instance_id)
            grant_block_time_combat_effect(pending, v.instance_id, GRANT_NAME)
            return INTERCEPT_BONUS

        options.append(
            card.option(
                f"precognition:basic:{vampire.instance_id}",
                f"Precognition [aus]: +{INTERCEPT_BONUS} intercept ({vampire.card.name})",
                _apply_basic,
            )
        )
        if discipline_level(state, vampire, "aus") == 2:
            options.append(
                card.option(
                    f"precognition:superior:{vampire.instance_id}",
                    f"Precognition [AUS]: +{INTERCEPT_BONUS} intercept, prevent 1 damage in "
                    f"round 1 if they block ({vampire.card.name})",
                    _apply_superior,
                )
            )
    return options


@card.on(Hook.DAMAGE_PREVENTION)
def _provide_precognition_prevention(
    state: GameState, ctx: DamagePreventionContext
) -> list[HookOption]:
    """Any damage type, as for Rolling with the Punches [for]: one type per
    `apply_damage` call, so both being positive is an engine bug."""
    if not is_round_one(ctx["round_state"]):
        return []
    if not block_time_combat_grant_available(ctx, GRANT_NAME):
        return []
    damage_box = ctx["damage"]
    normal = damage_box.get("normal", 0)
    aggravated = damage_box.get("aggravated", 0)
    if normal <= 0 and aggravated <= 0:
        return []
    if normal > 0 and aggravated > 0:
        raise AssertionError(
            "precognition: damage_box has both normal and aggravated damage at once, "
            "which no production call site produces today (engine invariant violation, "
            "not a legal game state)"
        )

    def _apply(_s: GameState) -> None:
        consume_block_time_combat_grant(ctx, GRANT_NAME)
        if aggravated > 0:
            damage_box["aggravated"] = aggravated - 1
        else:
            damage_box["normal"] = normal - 1

    return [
        card.option(
            "precognition:prevent",
            "Precognition: prevent 1 damage",
            _apply,
            played_card_type=None,  # claims the grant; the card was played at the block
        )
    ]
