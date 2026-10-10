"""Grooming the Protégé (krcg id 100860, `src/vtesbot/cards/
grooming_the_protege.py`).

Card text (fetched live via the krcg API, `https://api.krcg.org/card/100860`,
2026-10-10; matches the raw snapshot `data/cards/100860.json`):
    "Move up to 3 blood from a ready vampire you control to a younger
    vampire of the same clan in your uncontrolled region."

Rulings: none on file -- `rulings == []`, both in the raw snapshot above and
cross-checked against the installed `krcg` 4.18 package (`vtes.VTES.load()`;
`vtes.VTES["Grooming the Protege"].rulings == []`).

Card type: Master (`types == ["Master"]`). `discipline_requirement.
disciplines == []` (no discipline needed), `clan_requirement == []` (the
*card itself* requires no clan to play -- the "same clan" clause below is
the card's own effect-level target restriction, not a play requirement),
`cost is None` (free to play), `trifle is False` (no bonus master phase
action; unlike `life_in_the_city.py`, this card's `apply()` always returns
`False`).

Timing window: master phase action (`"master_phase_play"` hook, wired in
`engine/phases/master.py`, same pattern as `life_in_the_city.py`).

Reading "a younger vampire" (unlike Enchant Kindred's OQ-17, this card's own
sentence names an explicit comparison referent, so no Open Question is
needed here): the clause is "a ready vampire you control" ... "to a younger
vampire ... in your uncontrolled region" -- both vampires are named in the
same sentence, so "younger" is unambiguously relative to the first-named,
ready, source vampire (not some other unnamed reference point, which was
OQ-17's concern for Enchant Kindred's differently-structured sentence, where
no "ready vampire" was named at all). The rulebook glossary states capacity
"is also a relative measure of the vampire's age"
(`data/sources/rulebook/2026-10-09/8-glossaries.md:47-48`, cited by OQ-17),
so "younger" is read here as strictly lower *printed* capacity
(`vampire.card.capacity`, the plain printed stat -- OQ-8's attachment-aware
`effective_capacity` is deliberately not used for this age comparison, which
is about the vampire's identity, not how much blood it can currently hold;
`effective_capacity` is still used below for the blood-capacity cap on the
destination, which is the correct use per OQ-8's own resolution).

Source: "a ready vampire you control" -- `zone == "ready"` and
`controller == player`, independent of the `locked` flag (mirrors
`life_in_the_city.py`'s own reading of "ready region": "Area containing a
Methuselah's minions that are not in torpor" -- `locked` only governs
whether a vampire may currently act or block, not whether it is in the
ready region). Must have `blood > 0` (nothing to move otherwise).

Target: "a younger vampire of the same clan ... in your uncontrolled
region" -- `zone == "uncontrolled"` and `controller == player` (own
uncontrolled region only, per "your"), `card.clan == source.card.clan`
(same clan; `CryptCard.clan` is a plain printed stat, per `engine/cards.py`),
and `card.capacity < source.card.capacity` (strictly younger, see above).

Amount: "up to 3 blood" -- every integer amount from 1 up to
`min(3, source.blood, effective_capacity(target) - target.blood)` is offered
as a separate legal choice (CLAUDE.md "the engine yields a Decision with the
full list of legal choices"; the player may choose to move less than the
maximum, e.g. to keep blood on the source vampire). An amount of 0 is never
offered as its own choice: declining entirely is already covered by the
master phase's own "Pass" option (`engine/phases/master.py`), and moving 0
blood has no effect, so offering it would be a vacuous choice.

Cost/requirements surfaced as legal choices (CLAUDE.md "never let an agent
play an unplayable card"): the card must actually be in `player`'s hand, at
least one qualifying (ready, blood > 0) source vampire must exist, and for
each source at least one target (own uncontrolled, same clan, strictly
younger, with room to receive at least 1 blood) must exist; absent any of
these, no decision is raised for that case (the project's "only when needed"
invariant).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import effective_capacity, hooks
from vtesbot.engine.damage import add_blood
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 100860
MASTER_PHASE_PLAY_HOOK = "master_phase_play"
MAX_BLOOD = 3


def _sources(player_state) -> list[VampireInPlay]:
    return [v for v in player_state.vampires.values() if v.zone == "ready" and v.blood > 0]


def _targets(player_state, source: VampireInPlay) -> list[VampireInPlay]:
    return [
        v
        for v in player_state.vampires.values()
        if v.zone == "uncontrolled"
        and v.card.clan == source.card.clan
        and v.card.capacity < source.card.capacity
    ]


def _provide_grooming_the_protege(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    player_state = state.players[player]
    options: list[HookOption] = []
    for source in _sources(player_state):
        for target in _targets(player_state, source):
            room = effective_capacity(state, target) - target.blood
            max_amount = min(MAX_BLOOD, source.blood, room)
            for amount in range(1, max_amount + 1):

                def _apply(
                    s: GameState,
                    source: VampireInPlay = source,
                    target: VampireInPlay = target,
                    amount: int = amount,
                ) -> bool:
                    play_from_hand(s, player, KRCG_ID)
                    source.blood -= amount
                    add_blood(s, target, amount)
                    return False  # trifle is False: no bonus master phase action

                options.append(
                    HookOption(
                        choice=Choice(
                            f"grooming_the_protege:{source.instance_id}:"
                            f"{target.instance_id}:{amount}",
                            f"Grooming the Protégé: move {amount} blood from "
                            f"{source.card.name} to {target.card.name}",
                        ),
                        apply=_apply,
                    )
                )
    return options


hooks.register(MASTER_PHASE_PLAY_HOOK, _provide_grooming_the_protege)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Grooming the Protégé",
        status=Status.IMPLEMENTED,
        hooks=(Hook.MASTER_PHASE_PLAY,),
        source=__name__,
    )
)
