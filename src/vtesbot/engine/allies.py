"""Allies in play: bring one into play, and remove one from play.

OQ-7 (`docs/OPEN_QUESTIONS.md`): `engine/state.py::AllyInPlay` gives an ally
a representation in play; this module provides the two effects a
currently-blocked card (47th Street Royals) needs built on top of it --
entering play, and being removed from play (burned) as a card's own
reaction cost. Mirrors the equivalent vampire-side helpers
(`engine/damage.py::burn_vampire`) in shape and in scope.

OQ-12 (`docs/OPEN_QUESTIONS.md`, resolved): the actual "recruit ally" minion
action (its own announce/block-attempt window, `engine/phases/minion.py::
_perform_recruit_ally`) is now wired on top of `recruit_ally` below, mirroring
`engine/phases/master.py`'s `"master_phase_play"` hook pattern: a card
module registers against the `"recruit_ally_play"` hook
(`engine/phases/minion.py::RECRUIT_ALLY_PLAY_HOOK`), offering one
`hooks.HookOption` per Ally library card of its own it finds in the acting
player's hand; `apply(state)` must return a `RecruitAllySpec` (see below).
`recruit_ally` itself is unchanged -- it remains the minimal "bring into
play" primitive, called by `_perform_recruit_ally`'s own `resolve()` only
once a recruit-ally attempt actually succeeds, and still the direct entry
point a scenario test (or 47th Street Royals' own reaction, which never
needs to be *recruited* by this path) uses to put an ally into play directly.

Still deliberately out of scope (see `AllyInPlay`'s own docstring, unchanged
by OQ-12): ally bleed/block/combat participation, and an ally itself ever
being the *acting* minion that attempts to recruit another ally (Rulebook
SS4 "Recruit Ally": "Who can recruit an ally: Any ready minion" -- read
literally this includes a ready unlocked ally, not only a vampire; but no
card in the pool needs this, and `engine/phases/unlock.py` does not unlock
allies at all yet, so no ally can ever reach "ready unlocked" in the first
place -- building ally-as-actor ahead of that sourced need is exactly what
CLAUDE.md rule 2 forbids. `_perform_recruit_ally` is therefore offered only
to ready unlocked *vampires*, the same scope boundary OQ-7 already drew for
every other ally capability.

OQ-10 (`docs/OPEN_QUESTIONS.md`, resolved by this pass): `detect_contest_on_
recruit` below gives an ally the uniqueness enforcement `recruit_ally` itself
never had (`engine/contests.py`'s own `detect_contest_on_reveal` is the
vampire-side equivalent, called from `engine/phases/influence.py` after a
crypt-card reveal; this is its ally-side counterpart, called from
`engine/phases/minion.py::_perform_recruit_ally` after a successful
recruit). Deliberately kept out of `engine/contests.py`, not merely mirrored
into it: that module is explicitly scoped to the 2P variant's own override
for *crypt* cards ("contested crypt cards stay in play and usable; 1 pool
each unlock phase or yield") -- re-checked live, the 2P variant's "Contested
crypt cards" section is titled and worded for crypt cards specifically, and
its own aside, "(Note: this means that contested crypt cards are no longer
out of play)", confirms by negation that the override does not reach an
Ally/Equipment/Location. So an ally contest follows the unmodified Rulebook
SS4 Advanced Rules > Contested Cards rule instead: "turned face down and are
out of play" for *both* copies, for the whole contest -- not merely a
`contested_with` flag layered on an unchanged, still-usable "ready" zone
(contrast `detect_contest_on_reveal`, which never touches `zone` precisely
*because* the 2P override keeps a contested crypt card ready/usable).

OQ-15 (`docs/OPEN_QUESTIONS.md`, resolved by this pass): `resolve_one_ally_
contest` below closes the gap the paragraph above used to describe -- the
rulebook's own "Contested Cards" section gives the resolution cost in full:
"The cost to contest a card is 1 pool, which you pay during each of your
unlock phases. Instead of paying the cost ... you may choose to yield the
card ... [a yielded card] is burned ... If all other cards contesting your
unique card are yielded, then the card is unlocked and turned face up during
your next unlock phase, ending the contest." This is the exact same
pay-1-pool-or-yield structure `engine/contests.py::resolve_one_contest`
already applies to crypt cards -- reused/mirrored here, not reinvented --
with one wrinkle OQ-15 flagged and this pass resolves carefully: a contested
crypt card never needs a "restore to ready" step on the surviving copy
because the 2P override already kept it `zone == "ready"` throughout; an
ally has no such override (this module's own `detect_contest_on_recruit`
moves *both* copies to `zone == "contested"`), so the surviving copy's own
`zone` must actually flip back to `"ready"` -- and the rulebook's own
wording ("unlocked and turned face up during your *next* unlock phase") says
this happens on the surviving controller's *own next* unlock phase, not
instantaneously with the opponent's yield. See `resolve_one_ally_contest`'s
own docstring for the "pay" vs "yield" split, and
`engine/phases/unlock.py::_unlock_own_allies` for the delayed-restore half
(a separate, later unlock-phase step, mirroring how `_unlock_own_vampires`
itself is a separate mandatory step from the optional contest-resolution
loop).
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

    Source: Rulebook SS4 Advanced Rules > Contested Cards (quoted in full in
    this module's own docstring and in `docs/OPEN_QUESTIONS.md` OQ-10): "If
    more than one unique card with the same name is brought into play, that
    means control of the card is being contested. For the duration of the
    contest, all of the contested cards are turned face down and are out of
    play." Not overridden for an ally by the 2P variant (that override is
    scoped to crypt cards only -- see this module's docstring); matched by
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
