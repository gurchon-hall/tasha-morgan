"""Allies in play: bring one into play, and remove one from play.

OQ-7 (`docs/OPEN_QUESTIONS.md`): provides the two effects a card needs on
top of `engine/state.py::AllyInPlay` -- entering play, and being removed
(burned) as a reaction cost. Mirrors `engine/damage.py::burn_vampire` in
shape and scope.

OQ-12 (resolved): the "recruit ally" minion action (`engine/phases/
minion.py::_perform_recruit_ally`) is wired on top of `recruit_ally` below
via a `"recruit_ally_play"` hook, mirroring `engine/phases/master.py`'s
`"master_phase_play"` pattern -- a provider's `apply(state)` returns a
`RecruitAllySpec` (see below). `recruit_ally` itself stays the minimal
"bring into play" primitive.

Deliberately out of scope (per `AllyInPlay`'s own docstring): ally bleed/
block/combat participation, and an ally acting as the recruiter of another
ally -- Rulebook SS4 "Recruit Ally: Any ready minion" would literally permit
a ready unlocked ally, but no card needs it and `engine/phases/unlock.py`
never unlocks allies, so building that ahead of a sourced need would
violate CLAUDE.md rule 2.

OQ-10 (resolved): `detect_contest_on_recruit` gives an ally the same
uniqueness enforcement `engine/contests.py::detect_contest_on_reveal` gives
a crypt card. Kept out of `contests.py` rather than merged into it: that
module is scoped to the 2P variant's crypt-card override ("contested crypt
cards stay in play and usable"); the 2P variant's "Contested crypt cards"
section is worded for crypt cards specifically, and its own aside ("this
means that contested crypt cards are no longer out of play") confirms by
negation that the override does not reach an Ally/Equipment/Location. So an
ally contest follows the unmodified Rulebook SS4 Advanced Rules > Contested
Cards rule: both copies turned face down and out of play for the whole
contest.

OQ-15 (resolved): `resolve_one_ally_contest` applies the rulebook's
pay-1-pool-or-yield structure (Advanced Rules > Contested Cards: "The cost
to contest a card is 1 pool, which you pay during each of your unlock
phases ... [or] yield the card ... burned ... If all other cards contesting
your unique card are yielded, then the card is unlocked and turned face up
during your next unlock phase") -- the same structure `engine/contests.py::
resolve_one_contest` already applies to crypt cards. One difference: a
contested crypt card never needs a "restore to ready" step (the 2P override
already keeps it `zone == "ready"` throughout), but an ally has no such
override, so the surviving copy's `zone` must flip back to `"ready"` -- and
per the wording above, that happens on the surviving controller's own
*next* unlock phase, not instantaneously on the opponent's yield. See
`resolve_one_ally_contest`'s own docstring for the pay/yield split, and
`engine/phases/unlock.py::_unlock_own_allies` for the delayed restore.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .cards import LibraryCard
from .decision import Choice, Decision
from .pool import lose_pool
from .state import AllyInPlay

if TYPE_CHECKING:
    from .state import GameState


@dataclass(frozen=True)
class RecruitAllySpec:
    """What a `"recruit_ally_play"` hook option's `apply(state)` must return
    (OQ-12, `docs/OPEN_QUESTIONS.md`).

    Rulebook SS4 "Announce the Action": "Any card required for the action is
    played (face up) at this time, but is temporarily set aside (out of
    play) until the action resolves." A registered provider's `apply(state)`
    is invoked immediately when the acting player chooses this option (at
    announce time, before the block-attempt window opens) and must already
    have removed its own specific card from `player`'s hand and drawn its
    replacement (`vtesbot.cards._shared.play_from_hand_pending` -- not
    `play_from_hand`, since the final destination is not yet known). `card`
    is that removed card, kept here so `_perform_recruit_ally` can move it to
    the ash heap if the action ends up blocked (Rulebook SS4 "Resolve the
    Action": "If the action is blocked, then any card played to perform the
    action is burned"), without the engine ever having to special-case which
    card that was.

    `life`/`strength`/`bleed` are the specific Ally card's own printed stats
    (Rulebook SS4 Recruit Ally: "they receive blood counters from the blood
    bank to represent their life (listed on the ally's card)") -- read off
    the card's own text by its `src/vtesbot/cards/` module (CLAUDE.md SS6:
    the engine never special-cases a card name), exactly like `recruit_ally`
    already requires of any direct caller.

    `pay_cost` (Rulebook SS4 Recruit Ally: "Cost: As listed on the ally
    card"; "Resolve the Action": "the cost of the action is paid" only if
    the action succeeds) is called, if provided, only once the action is
    known to succeed, before the ally is placed in play; `None` (the
    default) means the card has no cost to pay (e.g. 47th Street Royals,
    whose own `cost` field is `None` per krcg).
    """

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
    """Bring a new ally into play under `player`'s control.

    Rulebook SS4 default actions (per the `vtes-rules-reference` skill
    condensed mapping): "recruit ally (undirected, +1 stealth; recruited
    ally cannot act this turn)" -- the ally enters the ready region locked,
    since it cannot act the turn it is recruited.
    """
    p = state.players[player]
    instance_id = p.new_ally_instance_id()
    ally = AllyInPlay(
        instance_id=instance_id,
        krcg_id=krcg_id,
        name=name,
        controller=player,
        life=life,
        strength=strength,
        bleed=bleed,
        zone="ready",
        locked=True,
    )
    p.allies[instance_id] = ally
    return ally


def detect_contest_on_recruit(state: GameState, recruited: AllyInPlay) -> None:
    """Flag `recruited` and any same-named in-play opposing ally as contested,
    and move both out of the usable "ready" zone for the contest's duration.

    Source: Rulebook SS4 Advanced Rules > Contested Cards (OQ-10, `docs/
    OPEN_QUESTIONS.md`): "If more than one unique card with the same name is
    brought into play, that means control of the card is being contested.
    For the duration of the contest, all of the contested cards are turned
    face down and are out of play." Not overridden for an ally by the 2P
    variant (that override is scoped to crypt cards only -- see this
    module's docstring); matched by
    printed name (`AllyInPlay.name`), exactly as the rulebook's own test is
    "the same name", not the same krcg id (a reprint under the same name is
    still the same unique card).

    Mirrors `engine/contests.py::detect_contest_on_reveal`'s shape (only
    checks the opponent, never the same player's own allies -- matching that
    function's own scope: normal deck construction cannot give one player two
    copies of a unique card in the first place, and the rulebook's own
    "contest yourself" edge case, DECK CONSTRUCTION caution box on the same
    Contested Cards page, is equally unimplemented on the vampire side today,
    so this is not a new gap introduced here). Only `"ready"` opposing allies
    can be contested against -- a `"burned"` one is gone, and with exactly
    two players (CLAUDE.md SS3) the opponent can never already have a
    `"contested"` copy of the same name waiting (that would require a third
    copy, impossible between two players at once).
    """
    opponent = state.other_player(recruited.controller)
    for other in state.players[opponent].allies.values():
        if other.zone == "ready" and other.name == recruited.name:
            recruited.contested_with = other.instance_id
            other.contested_with = recruited.instance_id
            recruited.zone = "contested"
            other.zone = "contested"
            return


def resolve_one_ally_contest(state: GameState, player: str, ally: AllyInPlay) -> None:
    """Rulebook SS4 Unlock Phase + Advanced Rules > Contested Cards (OQ-15,
    `docs/OPEN_QUESTIONS.md`): pay 1 pool to keep contesting `ally` this
    unlock phase, or yield (burn your own copy).

    Mirrors `engine/contests.py::resolve_one_contest`'s own two branches
    exactly, with the one difference OQ-15 identified: that function's
    crypt-card "pay" branch never touches `zone` because the 2P variant's
    "contested crypt cards stay in play and usable" override already keeps a
    contested vampire `zone == "ready"` throughout the whole contest. That
    override is scoped to crypt cards only (`engine/allies.py`'s own module
    docstring, OQ-10) -- an ally has no such override, so "paying" here
    correctly leaves `ally.zone == "contested"` (still out of play) rather
    than restoring it.

    The "yield" branch burns the yielding ally (same as the crypt-card case)
    and clears the opponent's own `contested_with` immediately -- but, unlike
    the crypt-card case, does *not* also restore the opponent's `zone` to
    `"ready"` here: the rulebook's own wording is "the card is unlocked and
    turned face up during your next unlock phase, ending the contest" -- a
    further, later event tied to the *surviving controller's own* next
    unlock phase, not the yielding player's current one (in 2P's alternating
    turns, that may not come up until after the opponent's own next turn).
    The surviving ally's own `zone` flip to `"ready"` is handled by
    `engine/phases/unlock.py::_unlock_own_allies`, run as part of its
    controller's own (later) `unlock_phase` call, exactly where the
    rulebook situates it.
    """
    choices = (
        Choice("pay", "Pay 1 pool to keep contesting"),
        Choice("yield", "Yield: burn this ally"),
    )
    decision = Decision(
        player=player,
        kind="ally_contest_resolution",
        choices=choices,
        context={"ally": ally.instance_id, "contested_with": ally.contested_with},
    )
    choice = state.ask(decision)
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
    """Remove `ally` from play (destroyed/burned).

    Mirrors `engine/damage.py::burn_vampire`. Used both for damage-based
    destruction (an ally's life reaching 0 -- Rulebook SS4 Combat, "Allies/
    retainers lose life for any damage"; not yet driven by any call site,
    since no card in the pool deals damage to an ally) and for a card's own
    printed self-burn reaction cost (e.g. 47th Street Royals: "You can burn
    47th Street Royals to reduce a bleed against you by 3" -- a card-text
    cost, CLAUDE.md "Golden Rule for Cards", not a generic engine rule).
    """
    ally.zone = "burned"
    ally.locked = False
