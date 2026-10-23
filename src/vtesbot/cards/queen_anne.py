"""Queen Anne (Vampire). krcg 201647. Snapshot: data/cards/201647.json
"Younger" is lower printed capacity (Rulebook §2); titled targets of either side.
Offered before casting and while unlocked only: RUL-018 and ENG-056, RUL-020."""

from vtesbot.cards.card import Card
from vtesbot.cards.common import context_vampire
from vtesbot.engine.cards import Sect
from vtesbot.engine.hook_contexts import (
    BleedAmountFixedModifierContext,
    DiablerieContext,
    Pending,
    PollingStepContext,
)
from vtesbot.engine.hooks import Hook, HookOption
from vtesbot.engine.politics import TITLE_VOTES
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 201647
BLOOD_COST = 1
PENDING_USED_KEY = "queen_anne_forced_abstain_used"
"""Once per referendum (Rulebook §3 "During X, do Y")."""

card = Card(KRCG_ID, "Queen Anne")


def _eligible_forced_abstain_targets(state: GameState, anne: VampireInPlay) -> list[VampireInPlay]:
    """Untitled vampires have no vote to force out, so are never offered."""
    return [
        v
        for player_state in state.players.values()
        for v in player_state.vampires.values()
        if v.zone == "ready"
        and v.card.sect is Sect.CAMARILLA
        and v.card.capacity < anne.card.capacity
        and v.card.title in TITLE_VOTES
    ]


@card.on(Hook.POLLING_STEP)
def _provide_queen_anne_forced_abstain(
    state: GameState, ctx: PollingStepContext
) -> list[HookOption]:
    """ "Called by Anne": the caller vampire is this Anne, so only her controller."""
    if ctx["phase"] != "before_cast":
        return []
    anne = state.players[ctx["player"]].vampires.get(ctx["caller_vampire_id"])
    if anne is None or anne.card.krcg_id != KRCG_ID or not anne.is_ready_unlocked:
        return []
    if anne.blood < BLOOD_COST:
        return []
    pending: Pending | None = ctx["pending"]
    if pending is None or pending.get(PENDING_USED_KEY, False):
        return []
    options: list[HookOption] = []
    for target in _eligible_forced_abstain_targets(state, anne):

        def _apply(_s: GameState, source_id: str = f"title:{target.instance_id}") -> None:
            anne.blood -= BLOOD_COST
            pending["forced_abstain"].add(source_id)
            pending[PENDING_USED_KEY] = True

        options.append(
            card.option(
                f"queen_anne_forced_abstain:{target.instance_id}",
                f"Queen Anne: burn 1 blood to force {target.card.name} to abstain",
                _apply,
            )
        )
    return options


@card.on(Hook.DIABLERIE)
def _provide_queen_anne_diablerie_unlock(
    state: GameState, ctx: DiablerieContext
) -> list[HookOption]:
    """Only once Anne herself diablerized; not offered once unlocked, which
    would loop the window."""
    diablerist = state.players[ctx["player"]].vampires.get(ctx["diablerist"])
    if diablerist is None or diablerist.card.krcg_id != KRCG_ID or not diablerist.locked:
        return []

    def _apply(_s: GameState) -> None:
        diablerist.locked = False

    return [card.option("queen_anne_diablerie_unlock", "Queen Anne: unlock", _apply)]


@card.on(Hook.BLEED_AMOUNT_FIXED_MODIFIER)
def _provide_queen_anne_bleed(state: GameState, ctx: BleedAmountFixedModifierContext) -> int:
    vampire = context_vampire(state, ctx)
    return 1 if vampire is not None and vampire.card.krcg_id == KRCG_ID else 0
