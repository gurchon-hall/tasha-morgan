"""Celerity (Master: Discipline). krcg 100312. Snapshot: data/cards/100312.json

Text: "Discipline.
Put this card on a vampire. This vampire gets +1 level of Celerity [cel]
and +1 capacity. Cannot be put on a vampire with superior Celerity [CEL]."

Rulings: none.

Notes:
- Target: either player's vampire in play (ready or torpor), never an
  uncontrolled one (Rulebook §8 glossary "Target").
- "Superior" is checked on effective disciplines, so a copy already
  attached counts (ENG-002). Copies stack: each adds one level, capped at
  superior (Rulebook §2 Card Types > Disciplines: "increasing the level
  ... from basic to superior"), and +1 capacity.
- Not a trifle: playing it uses the master phase action.
"""

from vtesbot.cards.card import Card
from vtesbot.cards.common import find_vampire
from vtesbot.engine.attachments import effective_disciplines
from vtesbot.engine.cards import CardAttachment
from vtesbot.engine.hook_contexts import (
    CapacityModifierContext,
    DisciplineLevelModifierContext,
    MasterPhasePlayContext,
)
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 100312
SUPERIOR = "CEL"
BASIC = "cel"

card = Card(KRCG_ID, "Celerity", "Master")


def _attached_copies(vampire: VampireInPlay) -> int:
    return sum(1 for a in vampire.attachments if a.krcg_id == KRCG_ID)


def _eligible_targets(state: GameState) -> list[VampireInPlay]:
    return [
        vampire
        for player_state in state.players.values()
        for vampire in player_state.vampires.values()
        if vampire.zone in ("ready", "torpor")
        and SUPERIOR not in effective_disciplines(state, vampire)
    ]


@card.on(Hook.MASTER_PHASE_PLAY)
def _play(state: GameState, ctx: MasterPhasePlayContext) -> list[HookOption]:
    player = ctx["player"]
    if not card.in_hand(state, player):
        return []

    def attach(vampire: VampireInPlay) -> HookOption:
        def apply(s: GameState) -> bool:
            card.play_from_hand(s, player)
            vampire.attachments.append(CardAttachment(krcg_id=KRCG_ID, name="Celerity"))
            return False  # not a trifle: no extra master phase action

        return card.option(
            f"celerity:{vampire.instance_id}",
            f"Celerity: attach to {vampire.card.name} ({vampire.controller})",
            apply,
        )

    return [attach(vampire) for vampire in _eligible_targets(state)]


@card.on(Hook.CAPACITY_MODIFIER)
def _capacity(state: GameState, ctx: CapacityModifierContext) -> int:
    vampire = find_vampire(state, ctx["vampire"])
    return 0 if vampire is None else _attached_copies(vampire)


@card.on(Hook.DISCIPLINE_LEVEL_MODIFIER)
def _discipline_level(state: GameState, ctx: DisciplineLevelModifierContext) -> tuple[str, ...]:
    vampire = find_vampire(state, ctx["vampire"])
    copies = 0 if vampire is None else _attached_copies(vampire)
    if vampire is None or copies == 0:
        return ()
    printed = vampire.card.disciplines
    printed_level = 2 if SUPERIOR in printed else 1 if BASIC in printed else 0
    return (SUPERIOR,) if min(2, printed_level + copies) == 2 else (BASIC,)
