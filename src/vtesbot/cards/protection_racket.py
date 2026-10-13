"""Protection Racket (Reaction). krcg id 101501.

Card text (verbatim, via the installed `krcg` 5.14 package's own
`krcg.vtes.VTES["Protection Racket"].card_text`, 2026-10-11, matching the raw
snapshot saved to `data/cards/101501.json`):
    "Requires an Anarch.
    +1 intercept, with an additional +1 intercept if the acting minion is
    titled."

Rulings (verbatim, via krcg; `VTES["Protection Racket"].rulings`):
    - "The additional intercept is gained or lost if the acting vampire
      changes sect during the action (eg. with {The Red Question} or {Mask
      of a Thousand Faces})." [ANK 20190416]

Card type: Reaction (`types == ["Reaction"]`). `discipline_requirement is
None`, `clans is None` -- no Discipline or clan
requirement at all (confirmed by the installed package's own `disciplines ==
[]`, `clans is None`); the only playability gate is the printed "Requires an
Anarch" sentence. `cost is None` (free). Legal since 2016-01-17; confirmed on
the active 2P allowed list (`data/formats/2p/2026-10-03.json`) and in the
suggested 2P decklist `data/decks/vekn-2p/brujah.json`.

Status: implemented.

"Requires an Anarch": per Rulebook SS6 Vampire Sects, "Some cards can only be
played by Anarch vampires" -- this restricts the minion *playing* the card,
not the (textually distinct) "acting minion" named by the card's second
clause. Protection Racket is a *Reaction* card (SS8 glossary: "A card played
by a Methuselah's ready, unlocked minion in response to an action taken by a
minion controlled by another Methuselah"), so the minion playing it is the
*reacting* (defending) Methuselah's own vampire, unrelated to the acting
minion whose action it reacts against. Confirmed against other printed
Reaction cards phrased the same way, e.g. Car Bomb (100293): "Requires a
ready anarch. ... Lock this reacting minion" names its Anarch requirement
and its locking effect against the same noun, "this reacting minion", never
the acting one. Every provider below therefore checks `vampire.card.sect is
Sect.ANARCH` on the *candidate reacting* vampire, mirroring `dust_up.py`'s
sect-gate shape but applied to the other side of the action -- including
treating `sect is None` as "does not qualify" (`CryptCard`'s own
docstring).

"+1 intercept, with an additional +1 intercept if the acting minion is
titled.": a plain `"intercept_modifier"` provider; the hook's sole call site
(`_duel_stealth_intercept`) only ever offers it with `player=defender`, so no
extra "am I the defender" check is needed. "The acting minion" is read from
that call site's own context, `context["acting_vampire"]` looked up in
`state.players[context["actor"]].vampires`. "Titled" is `CryptCard.title is
not None` (a printed title, independent of which one; distinct from
`engine/politics.py::TITLE_VOTES`, a Sabbat/Camarilla-titles-only vote-value
table, not a generic "is this vampire titled" predicate). The bonus is
computed fresh on every `offer()` call, not cached once per action: per the
ruling on file, "the additional intercept is gained or lost if the acting
vampire changes sect during the action (eg. with {The Red Question} or {Mask
of a Thousand Faces})" [ANK 20190416], re-evaluating live is correct. Neither
Red Question nor Mask of a Thousand Faces is implemented yet, and
`CryptCard.sect`/`title` have no in-game mutation path modeled anywhere in
this engine today, so the specific "changes sect mid-action" scenario is not
reachable with the current card pool (not reachable today, but correctly
modeled either way, per `dust_up.py`'s OQ-21 citation) -- not a fresh gap
introduced by this card, and no block on implementing the clause's own
live-reads-every-time behaviour.

SS8 glossary, same page as the Reaction Card definition: "A minion cannot
play the same reaction card more than once during a single action (even if
using a different Discipline level)" -- restricts the same *minion*, not the
whole Methuselah (two different eligible Anarch vampires may each play their
own copy within the same action; this project's established precedent for
this exact sentence, `telepathic_counter.py`'s own `USED_BY_KEY` set). Tracked
per-action via the shared `pending: dict[str, Any]` scratch container
(`engine/action.py::perform_minion_action`/`attempt_block`, OQ-11, `docs/
OPEN_QUESTIONS.md`), threaded unchanged into this hook's own context across
every retry of the block-attempt ping-pong for one action.

"A reaction card does not lock the minion playing it." (Rulebook SS2 Card
Types, same paragraph as the Reaction Card definition): no provider below
ever sets `.locked` on the vampire it plays through -- the engine's own
block-attempt machinery already never locks a defending vampire merely for
adding intercept (only the *blocking* vampire itself, chosen separately, gets
locked, and only once its block actually succeeds, `engine/action.py::
attempt_block`); this card's own eligibility re-check (`is_ready_unlocked`)
on every fresh `offer()` call would in any case keep correctly re-offering
the same vampire for a second, later intercept-add within the same action if
nothing else about it changed, consistent with staying unlocked.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import INTERCEPT_MODIFIER_HOOK
from vtesbot.engine.cards import Sect
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101501
USED_BY_KEY = "protection_racket_used_by"


def _eligible_vampires(state: GameState, player: str, used_by: set[str]) -> list[VampireInPlay]:
    """Candidate *reacting* vampires: `player`'s own ready, unlocked, Anarch
    vampires (SS8 glossary "Reaction Card" + "Requires an Anarch", see module
    docstring) that have not already played this card this action."""
    return [
        v
        for v in state.players[player].vampires.values()
        if v.is_ready_unlocked and v.instance_id not in used_by and v.card.sect is Sect.ANARCH
    ]


def _acting_vampire_titled(state: GameState, context: Mapping[str, Any]) -> bool:
    """Whether "the acting minion" (the vampire whose action is currently
    being evaluated for a block, `context["actor"]`/`context["acting_vampire"]`
    -- see module docstring) currently has a printed title. Missing/unknown
    data (not reachable from the hook's own sole call site today, `engine/
    action.py::_duel_stealth_intercept`, which always supplies both) degrades
    to "not titled" rather than guessing."""
    actor = context.get("actor")
    acting_vampire_id = context.get("acting_vampire")
    if actor is None or acting_vampire_id is None:
        return False
    acting_vampire = state.players[actor].vampires.get(acting_vampire_id)
    return acting_vampire is not None and acting_vampire.card.title is not None


def _provide_protection_racket(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]  # INTERCEPT_MODIFIER_HOOK is only ever offered to the defender.
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    pending = context.get("pending")
    used_by: set[str] = pending.setdefault(USED_BY_KEY, set()) if pending is not None else set()

    eligible = _eligible_vampires(state, player, used_by)
    if not eligible:
        return []

    bonus = 2 if _acting_vampire_titled(state, context) else 1

    def _make_apply(vampire: VampireInPlay) -> Any:
        def _apply(s: GameState) -> int:
            play_from_hand(s, player, KRCG_ID)
            used_by.add(vampire.instance_id)
            return bonus

        return _apply

    return [
        HookOption(
            choice=Choice(
                f"protection_racket:{vampire.instance_id}",
                f"Protection Racket: +{bonus} intercept ({vampire.card.name})",
            ),
            apply=_make_apply(vampire),
        )
        for vampire in eligible
    ]


hooks.register(INTERCEPT_MODIFIER_HOOK, _provide_protection_racket)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Protection Racket",
        status=Status.IMPLEMENTED,
        hooks=(Hook.INTERCEPT_MODIFIER,),
        source=__name__,
    )
)
