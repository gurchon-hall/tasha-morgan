"""Influence phase: transfers (2P ramp) and the free reveal action.

Source: Rulebook SS4 Influence Phase, replaced by 2P variant SS2.3 (per the
`vtes-rules-reference` skill condensed mapping): "4 transfers. Rulebook
ramp-up 1/2/3 is replaced in 2P: first player gets 3 on their first
influence phase, then 4 for all. Costs: 1 transfer = 1 pool -> uncontrolled
vampire; 2 transfers = 1 blood from uncontrolled vampire -> pool; 4
transfers + burn 1 pool = move a crypt card to the uncontrolled region. A
vampire with blood >= capacity may be revealed into the ready region,
unlocked, any time in this phase."

Four influence-phase action types are implemented here (CLAUDE.md task
scope: "all four transfer types from the rules-reference skill"): the three
costed transfer types quoted above, plus the free reveal action (the
fourth action type the Influence phase enumerates, even though it does not
itself cost a transfer).
"""

from typing import TYPE_CHECKING

from ..damage import add_blood
from ..decision import Choice, Decision
from ..pool import gain_pool, lose_pool
from ..state import VampireInPlay

if TYPE_CHECKING:
    from ..state import GameState

FIRST_INFLUENCE_PHASE_TRANSFERS = 3
"""2P variant SS2.3: the first player's very first influence phase of the game."""
STANDARD_TRANSFERS = 4
"""2P variant SS2.3: every influence phase thereafter, for both players."""


def influence_phase(state: GameState, player: str) -> None:
    if not state.first_influence_phase_used:
        remaining = FIRST_INFLUENCE_PHASE_TRANSFERS
        state.first_influence_phase_used = True
    else:
        remaining = STANDARD_TRANSFERS

    while True:
        choices = _available_choices(state, player, remaining)
        if not choices:
            return
        decision = Decision(
            player=player,
            kind="influence_action",
            choices=choices + (Choice("end_phase", "End influence phase"),),
            context={"transfers_remaining": remaining},
        )
        choice = state.ask(decision).value
        if choice == "end_phase":
            return
        remaining -= _apply(state, player, choice)


def _available_choices(state: GameState, player: str, remaining: int) -> tuple[Choice, ...]:
    p = state.players[player]
    choices: list[Choice] = []

    if remaining >= 1 and p.pool >= 1:
        for v in p.vampires.values():
            if v.zone == "uncontrolled" and v.blood < v.card.capacity:
                choices.append(
                    Choice(
                        f"add_blood:{v.instance_id}",
                        f"Add 1 blood to {v.card.name} (1 transfer, 1 pool)",
                    )
                )

    if remaining >= 2:
        for v in p.vampires.values():
            if v.zone == "uncontrolled" and v.blood >= 1:
                choices.append(
                    Choice(
                        f"remove_blood:{v.instance_id}",
                        f"Remove 1 blood from {v.card.name} for 1 pool (2 transfers)",
                    )
                )

    if remaining >= 4 and p.pool >= 1 and p.crypt_deck:
        choices.append(
            Choice(
                "bring_crypt",
                "Bring the next crypt card to the uncontrolled region (4 transfers, 1 pool)",
            )
        )

    for v in p.vampires.values():
        if v.zone == "uncontrolled" and v.blood >= v.card.capacity:
            choices.append(Choice(f"reveal:{v.instance_id}", f"Reveal {v.card.name} (free)"))

    return tuple(choices)


def _apply(state: GameState, player: str, choice: str) -> int:
    """Apply the chosen influence action; return the number of transfers it consumed."""
    p = state.players[player]
    kind, _, rest = choice.partition(":")

    if kind == "add_blood":
        lose_pool(state, player, 1)
        add_blood(p.vampires[rest], 1)
        return 1

    if kind == "remove_blood":
        vampire = p.vampires[rest]
        vampire.blood -= 1
        gain_pool(state, player, 1)
        return 2

    if kind == "bring_crypt":
        lose_pool(state, player, 1)
        card = p.crypt_deck.pop(0)
        instance_id = p.new_instance_id()
        p.vampires[instance_id] = VampireInPlay(
            instance_id=instance_id, card=card, controller=player, zone="uncontrolled"
        )
        return 4

    if kind == "reveal":
        from ..contests import detect_contest_on_reveal

        vampire = p.vampires[rest]
        vampire.zone = "ready"
        vampire.locked = False
        detect_contest_on_reveal(state, vampire)
        return 0

    raise ValueError(f"unknown influence action {choice!r}")
