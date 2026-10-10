"""Life in the City (Master). krcg id 101104.

Card text (fetched via krcg 5.14+, `krcg.load()["Life in the City"].text`,
2026-10-09; raw snapshot `data/cards/101104.json`):
    "Trifle.
    Add 1 blood to a ready vampire."

Rulings: none on file -- `krcg.load()["Life in the City"].rulings == []`,
cross-checked against `https://api.krcg.org/card/101104` (2026-10-09, same
empty list).

Card type: Master. `discipline_requirement.disciplines == []` (no discipline
needed), `clan_requirement == []`, `cost is None` (free to play).
`trifle is True` (Rulebook SS4 Master Phase / SS8 glossary "Trifle": "When a
Methuselah successfully plays a trifle, they gain an additional master phase
action... A Methuselah can gain only one master phase action from trifles in
a given master phase" -- already implemented generically by
`engine/phases/master.py::master_phase`, which the `"master_phase_play"`
hook's `apply(state) -> bool` contract plugs straight into).

Timing window: master phase action (`"master_phase_play"` hook, wired in
`engine/phases/master.py`).

Target: "a ready vampire" -- the printed text carries no "you control"
qualifier, so the legal target pool is *every* ready vampire in the game,
either player's (Rulebook SS8 glossary "Ready Region: Area containing a
Methuselah's minions that are not in torpor" -- i.e. any vampire with
`zone == "ready"`; "ready" is independent of the locked/unlocked flag, which
only governs whether *that* vampire may currently act or block, not whether
it is in the ready region). Effect: `add_blood(state, vampire, 1)`
(`engine/damage.py`), which already caps at the target's effective capacity
(Rulebook SS1 Vampires; OQ-8, `docs/OPEN_QUESTIONS.md`) -- so targeting an
already-full vampire is a legal but effect-less play (the card is still
spent; this mirrors the engine's own
`add_blood` contract and the general "play = announce, show, resolve" rule,
Rulebook SS2, with no exception carved out for a fizzled effect).

Cost/requirements surfaced as legal choices (CLAUDE.md "never let an agent
play an unplayable card"): the card must actually be in `player`'s hand, and
at least one ready vampire must exist anywhere in play; absent either, the
provider offers nothing and no decision is raised (the project's "only when
needed" invariant).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.damage import add_blood
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101104
MASTER_PHASE_PLAY_HOOK = "master_phase_play"


def _ready_targets(state: GameState) -> list[VampireInPlay]:
    return [
        vampire
        for player_state in state.players.values()
        for vampire in player_state.vampires.values()
        if vampire.zone == "ready"
    ]


def _provide_life_in_the_city(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    targets = _ready_targets(state)
    if not targets:
        return []

    options: list[HookOption] = []
    for vampire in targets:

        def _apply(s: GameState, vampire: VampireInPlay = vampire) -> bool:
            play_from_hand(s, player, KRCG_ID)
            add_blood(s, vampire, 1)
            return True  # trifle: grants the one extra master phase action

        options.append(
            HookOption(
                choice=Choice(
                    f"life_in_the_city:{vampire.instance_id}",
                    f"Life in the City: add 1 blood to {vampire.card.name} ({vampire.controller})",
                ),
                apply=_apply,
            )
        )
    return options


hooks.register(MASTER_PHASE_PLAY_HOOK, _provide_life_in_the_city)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Life in the City",
        status=Status.IMPLEMENTED,
        hooks=(Hook.MASTER_PHASE_PLAY,),
        source=__name__,
    )
)
