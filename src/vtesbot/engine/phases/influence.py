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

"capacity" above is a vampire's *effective* capacity (OQ-8,
`docs/OPEN_QUESTIONS.md`): printed capacity as modified by any attached
card's own bonus (e.g. Celerity's "+1 capacity") -- see
`engine/attachments.py::effective_capacity`, consulted below instead of a
bare `v.card.capacity` read.

OQ-24 (`docs/OPEN_QUESTIONS.md`, resolved): until this pass, this phase was
a closed, hardcoded implementation of exactly the three transfer types
above plus the free reveal, with no hook dispatch at all -- unlike
`engine/phases/master.py::master_phase`'s own `"master_phase_play"` hook.
Wider View (krcg id 102180, "You can use 1 transfer to draw 1 card from
your crypt and then remove a crypt card in your uncontrolled region from
the game. You can use 4 transfers to burn this card and gain 2 pool.")
needs two further transfer-costed options available during this same
phase, which no existing hardcoded `kind` branch can express. Fixed by
adding `INFLUENCE_PHASE_ACTION_HOOK` (`"influence_phase_action"`), offered
via `hooks.offer` alongside the three hardcoded transfer types (kept as a
hardcoded baseline rather than reimplemented as hook providers of their own
-- see this module's own "Why hardcoded baseline, not hook providers"
note below for the reasoning) -- mirrors `master_phase`'s own
offer/by-value/dispatch shape. A provider's `HookOption.apply(state)` must
return an `int`: the number of transfers the chosen option consumed (the
same "`apply`'s return value documents the hook's own contract" pattern
`master_phase`'s own module docstring already uses for its `bool`
"is this a trifle" contract). As with every hook, legality of each offered
option (e.g. Wider View's own 1-transfer draw option needing both a
non-empty `crypt_deck` *and* at least one uncontrolled vampire to remove)
is the registering provider's own responsibility (`GameState.ask`'s
"legality by construction" invariant, `engine/state.py` module docstring) --
the engine never second-guesses what a provider offers.

Why hardcoded baseline, not hook providers: reimplementing the three
existing transfer types as the *first* registered providers against
`INFLUENCE_PHASE_ACTION_HOOK` would mean moving `_available_choices`/
`_apply`'s existing, already-tested logic into provider functions that live
in `engine/`, not `src/vtesbot/cards/` (CLAUDE.md SS6: "Card hooks ... lives
in `src/vtesbot/cards/`. Do not special-case card names in the engine" --
these three are generic rulebook mechanics, not any card's text, so they
belong in `engine/` either way, but moving them behind the hook machinery
would add indirection with no reader-facing benefit, since nothing outside
this module needs to add to or override them). Keeping them hardcoded and
simply unioning the hook's own options alongside them is the smaller diff
and leaves the three types' own byte-for-byte behaviour, and every existing
test asserting it, untouched.
"""

from typing import TYPE_CHECKING

from .. import hooks
from ..attachments import effective_capacity
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

INFLUENCE_PHASE_ACTION_HOOK = "influence_phase_action"
"""OQ-24: a card-sourced, transfer-costed influence-phase option, offered
alongside the three hardcoded transfer types. `HookOption.apply(state)`
must return the `int` number of transfers consumed."""


def influence_phase(state: GameState, player: str) -> None:
    if not state.first_influence_phase_used:
        remaining = FIRST_INFLUENCE_PHASE_TRANSFERS
        state.first_influence_phase_used = True
    else:
        remaining = STANDARD_TRANSFERS

    while True:
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
        # Audit-driven guard (OQ-24 addendum, `docs/OPEN_QUESTIONS.md`): a
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


def _available_choices(state: GameState, player: str, remaining: int) -> tuple[Choice, ...]:
    p = state.players[player]
    choices: list[Choice] = []

    if remaining >= 1 and p.pool >= 1:
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

    if remaining >= 4 and p.pool >= 1 and p.crypt_deck:
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
