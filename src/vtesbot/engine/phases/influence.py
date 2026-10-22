"""Influence phase (Rulebook §4, 2P §2.3): blood add/remove, bring crypt
card, free reveal; 3->4 transfer ramp; ENG-002 capacity.
`INFLUENCE_PHASE_ACTION_HOOK` adds ENG-016 options alongside.
"""

from typing import TYPE_CHECKING

from .. import hooks
from ..attachments import effective_capacity
from ..damage import add_blood
from ..decision import Choice, Decision
from ..hooks import Hook
from ..pool import can_afford_without_ousting, gain_pool, lose_pool
from ..state import VampireInPlay

if TYPE_CHECKING:
    from ..state import GameState

FIRST_INFLUENCE_PHASE_TRANSFERS = 3
"""2P variant §2.3: the first player's very first influence phase of the game."""
STANDARD_TRANSFERS = 4
"""2P variant §2.3: every influence phase thereafter, for both players."""

INFLUENCE_PHASE_ACTION_HOOK = Hook.INFLUENCE_PHASE_ACTION


def influence_phase(state: GameState, player: str) -> None:
    if not state.first_influence_phase_used:
        remaining = FIRST_INFLUENCE_PHASE_TRANSFERS
        state.first_influence_phase_used = True
    else:
        remaining = STANDARD_TRANSFERS

    while not state.game_over:
        hook_options = hooks.offer(
            INFLUENCE_PHASE_ACTION_HOOK, state, player=player, transfers_remaining=remaining
        )
        by_value = {o.choice.value: o for o in hook_options}
        choices = _available_choices(state, player, remaining) + tuple(
            o.choice for o in hook_options
        )
        if not choices:
            return
        all_choices = choices + (Choice("end_phase", "End influence phase"),)
        # Audit-driven guard (ENG-016 addendum): a
        # hook-provided choice value colliding with a hardcoded one (or with
        # "end_phase") would otherwise silently take over that action --
        # see `hooks.ensure_unique_choice_values`'s own docstring.
        hooks.ensure_unique_choice_values(all_choices, decision_kind="influence_action")
        decision = Decision(
            player=player,
            kind="influence_action",
            choices=all_choices,
            context={"transfers_remaining": remaining},
        )
        choice = state.ask(decision).value
        if choice == "end_phase":
            return
        if choice in by_value:
            remaining -= int(by_value[choice].apply(state))
        else:
            remaining -= _apply(state, player, choice)
        if state.game_over:
            return


def _available_choices(state: GameState, player: str, remaining: int) -> tuple[Choice, ...]:
    p = state.players[player]
    choices: list[Choice] = []

    if remaining >= 1 and can_afford_without_ousting(state, player, 1):
        for v in p.vampires.values():
            if v.zone == "uncontrolled" and v.blood < effective_capacity(state, v):
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

    if remaining >= 4 and can_afford_without_ousting(state, player, 1) and p.crypt_deck:
        choices.append(
            Choice(
                "bring_crypt",
                "Bring the next crypt card to the uncontrolled region (4 transfers, 1 pool)",
            )
        )

    for v in p.vampires.values():
        if v.zone == "uncontrolled" and v.blood >= effective_capacity(state, v):
            choices.append(Choice(f"reveal:{v.instance_id}", f"Reveal {v.card.name} (free)"))

    return tuple(choices)


def _apply(state: GameState, player: str, choice: str) -> int:
    """Apply the chosen influence action; return the number of transfers it consumed."""
    p = state.players[player]
    kind, _, rest = choice.partition(":")

    if kind == "add_blood":
        lose_pool(state, player, 1)
        add_blood(state, p.vampires[rest], 1)
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
