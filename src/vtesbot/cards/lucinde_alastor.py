"""Lucinde, Alastor (Vampire). krcg 201700. Snapshot: data/cards/201700.json
Usable from torpor [LSJ 20011022]; once per master phase (Rulebook §3 "During
X, do Y"). Any in-play opposing vampire may be chosen; the grant needs it ready."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire
from vtesbot.engine.cards import Sect
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hook_contexts import (
    ActionCardPlayContext,
    BleedAmountFixedModifierContext,
    MasterPhaseAbilityContext,
)
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.phases.minion import (
    ActionCardSpec,
    active_enter_combat_grants,
    build_enter_combat_action_spec,
    grant_enter_combat_this_turn,
)
from vtesbot.engine.state import EnterCombatGrant, GameState, VampireInPlay

KRCG_ID = 201700
BLOOD_COST = 1
ABILITY_USED_KEY = "lucinde_alastor_choose_vampire"
IN_PLAY_ZONES = ("ready", "torpor")

card = Card(KRCG_ID, "Lucinde, Alastor")


def _eligible_choose_targets(state: GameState, opponent: str) -> list[VampireInPlay]:
    """In play means ready or torpor (Rulebook §8 Target)."""
    return [v for v in state.players[opponent].vampires.values() if v.zone in IN_PLAY_ZONES]


@card.on(Hook.MASTER_PHASE_ABILITY)
def _provide_lucinde_master_ability(
    state: GameState, ctx: MasterPhaseAbilityContext
) -> list[HookOption]:
    player = ctx["player"]
    opponent = state.other_player(player)
    options: list[HookOption] = []
    for lucinde in state.players[player].vampires.values():
        if lucinde.card.krcg_id != KRCG_ID or lucinde.zone not in IN_PLAY_ZONES:
            continue
        if lucinde.blood < BLOOD_COST:
            continue
        if lucinde.ability_used_turn.get(ABILITY_USED_KEY) == state.turn_number:
            continue
        if not _eligible_choose_targets(state, opponent):
            continue

        def _apply(s: GameState, lucinde: VampireInPlay = lucinde) -> None:
            lucinde.blood -= BLOOD_COST
            lucinde.ability_used_turn[ABILITY_USED_KEY] = s.turn_number
            targets = _eligible_choose_targets(s, opponent)
            if len(targets) == 1:
                target_id = targets[0].instance_id
            else:
                choices = tuple(
                    Choice(f"lucinde_alastor_target:{v.instance_id}", f"Choose {v.card.name}")
                    for v in targets
                )
                decision = Decision(player=player, kind="lucinde_alastor_target", choices=choices)
                target_id = s.ask(decision).value.split(":", 1)[1]
            grant_enter_combat_this_turn(
                s, player, target_player=opponent, target_vampire_id=target_id
            )

        options.append(
            card.option(
                f"lucinde_alastor_ability:{lucinde.instance_id}",
                "Lucinde, Alastor: burn 1 blood to choose a vampire",
                _apply,
            )
        )
    return options


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_lucinde_enter_combat_grant(
    state: GameState, ctx: ActionCardPlayContext
) -> list[HookOption]:
    """Any Camarilla vampire of the player, Lucinde included; no card is played."""
    player, vampire = ctx["player"], context_vampire(state, ctx)
    if vampire is None or vampire.card.sect is not Sect.CAMARILLA:
        return []
    options: list[HookOption] = []
    for grant in active_enter_combat_grants(state, player):
        target = state.players[grant.target_player].vampires.get(grant.target_vampire_id)
        if target is None or target.zone != "ready":
            continue

        def _apply(
            s: GameState, grant: EnterCombatGrant = grant, vampire: VampireInPlay = vampire
        ) -> ActionCardSpec:
            return build_enter_combat_action_spec(
                s, player, vampire, grant.target_player, grant.target_vampire_id
            )

        options.append(
            card.option(
                f"lucinde_alastor_enter_combat:{vampire.instance_id}:{grant.target_vampire_id}",
                f"Enter combat with {target.card.name} (Lucinde, Alastor)",
                _apply,
            )
        )
    return options


@card.on(Hook.BLEED_AMOUNT_FIXED_MODIFIER)
def _provide_lucinde_bleed(state: GameState, ctx: BleedAmountFixedModifierContext) -> int:
    vampire = context_vampire(state, ctx)
    return 1 if vampire is not None and vampire.card.krcg_id == KRCG_ID else 0
