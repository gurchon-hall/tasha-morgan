"""Allies in play: bring in (ENG-001), remove one. Recruit action wires via a
`"recruit_ally_play"` hook (ENG-006). Contested Cards (ENG-004) unmodified §4; pay/yield
(ENG-009) mirrors `engine/contests.py`."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .cards import LibraryCard
from .decision import Choice, Decision
from .pool import can_afford_without_ousting, lose_pool
from .state import AllyInPlay

if TYPE_CHECKING:
    from .state import GameState


@dataclass(frozen=True)
class RecruitAllySpec:
    """What a `"recruit_ally_play"` hook's `apply(state)` returns (ENG-006). `card` is the
    already-removed card, kept to burn if blocked (§4). `pay_cost` runs only once the
    action succeeds."""

    card: LibraryCard
    life: int
    strength: int = 0
    bleed: int = 0
    pay_cost: Callable[[GameState], None] | None = None


def recruit_ally(
    state: GameState,
    player: str,
    *,
    krcg_id: int,
    name: str,
    life: int,
    strength: int = 0,
    bleed: int = 0,
) -> AllyInPlay:
    """Bring a new ally into play under `player`'s control (§4 default actions:
    "recruited ally cannot act this turn"), so it enters locked."""
    p = state.players[player]
    instance_id = p.new_ally_instance_id()
    ally = AllyInPlay(
        instance_id=instance_id,
        krcg_id=krcg_id,
        name=name,
        controller=player,
        life=life,
        starting_life=life,
        strength=strength,
        bleed=bleed,
        zone="ready",
        locked=True,
    )
    p.allies[instance_id] = ally
    return ally


def add_life(ally: AllyInPlay, amount: int) -> int:
    """Add life to an ally, capped at its own printed `starting_life` (ENG-041;
    e.g. Seraphina, krcg 201686: "...can add 2 blood or life to a minion you
    control... not to exceed starting life."). Mirrors `engine/damage.py::
    add_blood`'s capped shape. Returns the amount actually added."""
    if amount <= 0:
        return 0
    added = min(amount, ally.starting_life - ally.life)
    ally.life += added
    return added


def detect_contest_on_recruit(state: GameState, recruited: AllyInPlay) -> None:
    """Flags `recruited` + a same-named opposing ally as contested
    (§4, ENG-004; not 2P-overridden), matched by `name`. ENG-010: a
    same-controller collision burns the incoming copy instead."""
    own = state.players[recruited.controller]
    for mine in own.allies.values():
        if mine is recruited:
            continue
        if mine.zone == "ready" and mine.name == recruited.name:
            recruited.zone = "burned"
            recruited.locked = False
            return
    opponent = state.other_player(recruited.controller)
    for other in state.players[opponent].allies.values():
        if other.zone == "ready" and other.name == recruited.name:
            recruited.contested_with = other.instance_id
            other.contested_with = recruited.instance_id
            recruited.zone = "contested"
            other.zone = "contested"
            return


def resolve_one_ally_contest(state: GameState, player: str, ally: AllyInPlay) -> None:
    """§4 Unlock + Contested Cards (ENG-009): pay 1 pool to keep contesting, or yield
    (burn own copy). No 2P override: survivor's `zone` restores only on its own
    next unlock phase."""
    # DES-009: paying must not leave the payer at 0 pool; yielding stays.
    pay = (Choice("pay", "Pay 1 pool to keep contesting"),)
    choices = (
        *(pay if can_afford_without_ousting(state, player, 1) else ()),
        Choice("yield", "Yield: burn this ally"),
    )
    decision = Decision(
        player=player,
        kind="ally_contest_resolution",
        choices=choices,
        context={"ally": ally.instance_id, "contested_with": ally.contested_with},
    )
    choice = state.ask_unless_forced(decision)
    if choice.value == "pay":
        lose_pool(state, player, 1)
    else:
        opponent_ally = _find_ally_instance(state, ally.contested_with)
        ally.zone = "burned"
        ally.locked = False
        if opponent_ally is not None:
            # Cleared immediately (nothing contests the opponent's copy any
            # more), but its `zone` deliberately stays "contested" here --
            # see this function's own docstring and `_unlock_own_allies`.
            opponent_ally.contested_with = None
        ally.contested_with = None


def _find_ally_instance(state: GameState, instance_id: str | None) -> AllyInPlay | None:
    if instance_id is None:
        return None
    for player_state in state.players.values():
        if instance_id in player_state.allies:
            return player_state.allies[instance_id]
    return None


def burn_ally(state: GameState, player: str, ally: AllyInPlay) -> None:
    """Remove `ally` from play (destroyed/burned). Mirrors `burn_vampire`; used for
    damage-based destruction (§4) and a card's own self-burn cost."""
    ally.zone = "burned"
    ally.locked = False
