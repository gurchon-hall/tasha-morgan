"""Aniel (Vampire). krcg 201666. Snapshot: data/cards/201666.json
Ⓓ, so "another ready minion" is the opponent's (Rulebook §8 Directed Action). Any
placer's counter; Aniel pays 1 blood on success only. See ENG-042."""

from typing import Any

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.corruption import burn_corruption_counters
from vtesbot.engine.hook_contexts import ActionCardPlayContext
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.phases.minion import ActionCardSpec
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 201666
ANIEL_STEALTH = 1
BLOOD_COST = 1

card = Card(KRCG_ID, "Aniel")


def _counter_burn_option(aniel: VampireInPlay, vampire: VampireInPlay, placer: str) -> HookOption:
    def _apply(s: GameState) -> ActionCardSpec:
        def resolve(_pending: dict[str, Any]) -> None:
            if burn_corruption_counters(vampire, placer, 1) <= 0:
                return  # fizzles (RUL-007)
            aniel.blood -= BLOOD_COST
            s.log.record_event(f"Aniel burns 1 corruption counter on {vampire.card.name}")

        return ActionCardSpec(base_stealth=ANIEL_STEALTH, directed=True, resolve=resolve)

    return card.option(
        f"aniel:counter:{aniel.instance_id}:{vampire.instance_id}:{placer}",
        f"Aniel: burn 1 corruption counter ({placer}'s) on {vampire.card.name}",
        _apply,
    )


def _discipline_card_burn_option(
    aniel: VampireInPlay, vampire: VampireInPlay, attachment: CardAttachment
) -> HookOption:
    def _apply(s: GameState) -> ActionCardSpec:
        def resolve(_pending: dict[str, Any]) -> None:
            if attachment.zone != "attached":
                return  # fizzles (RUL-007)
            aniel.blood -= BLOOD_COST
            attachment.zone = "burned"
            s.log.record_event(f"Aniel burns {attachment.name} from {vampire.card.name}")

        return ActionCardSpec(base_stealth=ANIEL_STEALTH, directed=True, resolve=resolve)

    return card.option(
        f"aniel:discipline:{aniel.instance_id}:{vampire.instance_id}:{attachment.instance_id}",
        f"Aniel: burn {attachment.name} (requires a Discipline) from {vampire.card.name}",
        _apply,
    )


@card.on(Hook.ACTION_CARD_PLAY)
def _provide_aniel(state: GameState, ctx: ActionCardPlayContext) -> list[HookOption]:
    """One option per placer with a counter, and per discipline-requiring card."""
    player, aniel = ctx["player"], context_vampire(state, ctx)
    if aniel is None or aniel.card.krcg_id != KRCG_ID or aniel.zone not in ("ready", "torpor"):
        return []
    if aniel.blood < BLOOD_COST:
        return []
    opponent = state.other_player(player)
    options: list[HookOption] = []
    for vampire in state.players[opponent].vampires.values():
        if vampire.zone != "ready":
            continue
        for placer, count in vampire.corruption_counters.items():
            if count > 0:
                options.append(_counter_burn_option(aniel, vampire, placer))
        for attachment in vampire.attachments:
            if attachment.zone == "attached" and attachment.requires_discipline:
                options.append(_discipline_card_burn_option(aniel, vampire, attachment))
    return options
