"""On the Qui Vive (Reaction). krcg id 101321.

Card text (verbatim, via the installed `krcg` 4.18 `krcg.vtes.VTES` package
-- the project's `uv run` virtualenv has a newer `krcg` (5.14) whose own
`krcg.load()` API has no `to_json()`/raw-schema equivalent, the same
pre-existing gap `organized_resistance.py`'s own docstring notes --
2026-10-14, matching the raw snapshot saved to `data/cards/101321.json`):
    "Only usable by a locked minion. A minion can play only one On the Qui
    Vive between their unlock phases.
    This minion wakes (they ignore the requirement to be unlocked for
    playing reaction cards and attempting to block until the end of the
    action). If this minion is an ally, they do not unlock as normal
    during their next unlock phase."

Rulings (verbatim, via krcg; `VTES["On the Qui Vive"].rulings`):
    - "The minion need not attempt to block nor play further reaction
      cards: that is merely an option." [TOM 19951129]
    - "Can be played or used after action resolution (e.g. to use a
      reaction card like {Fast Reaction} after combat)." [LSJ 20091123]
    - "Can be played or used during the 'as a card is played' window,
      except in combat, or when there is no action." [ANK 20210819]

Card type: Reaction (`types == ["Reaction"]`). `clans == []`,
`disciplines == []` -- no clan/Discipline requirement; the only
playability gate is the printed "Only usable by a locked minion"
relaxation of the normal Reaction-card eligibility rule. `blood_cost`/
`pool_cost` are both `None` (free). Legal since 2006-10-04 (live
`api.krcg.org`); confirmed on the active 2P allowed list
(`data/formats/2p/2026-10-03.json`) and in
`data/decks/vekn-2p/toreador.json`.

Status: implemented, against `WAKE_LOCKED_MINION_HOOK` only (OQ-48,
`docs/OPEN_QUESTIONS.md`, resolved) -- the one timing window
`engine/action.py::attempt_block`'s retry loop offers the defender, before
its own block-candidate list is (re)computed. A chosen option's `apply`
sets `VampireInPlay.woken = True` on the playing vampire (`engine/
state.py`), which `ready_unlocked_vampires`/`attempt_block` and every
other registered Reaction card's own `is_ready_unlocked` eligibility check
already honor with no further change -- covering both halves of the
primary clause (attempting to block; playing further reaction cards) for
the rest of the action, "while remaining structurally locked."

Scope decision on [LSJ 20091123]/[ANK 20210819]: those rulings describe
*additional* play windows for the card itself (after action resolution;
during the "as a card is played" window; or with no action at all), not a
further mandatory effect -- [TOM 19951129] confirms the woken state's only
value is the optional eligibility it grants, already fully captured by
`woken`. Deliberately not hooked into `ACTION_SUCCEEDED_HOOK`/
`REFERENDUM_RESOLVED_HOOK`/`CANCEL_AS_PLAYED_HOOK`'s `"mid_cast"` window:
none of those dispatch points models "no action is in progress at all" or
a generic "as any card is played" moment, and this deck's other two
Reaction cards (Second Tradition: Domain, Telepathic Counter) only ever
check `is_ready_unlocked` from inside a block attempt already in progress,
so the one implemented window is what this deck's bot can actually use.
Noted here, not silently dropped.

Ally footnote ("If this minion is an ally, they do not unlock as normal
during their next unlock phase"): `AllyInPlay.skip_next_unlock` (OQ-46)
exists for this, but this module's own provider never targets an ally.
Allies never attempt to block (out of this engine's scope, OQ-46's own
solution note) and never play reaction cards at all, so there is no
decision point at which playing this card on a locked ally would do
anything but discard a card for a pure downside -- not a candidate option
worth offering an agent. If a future card gives allies some reaction
capability, revisit.

"A minion can play only one On the Qui Vive between their unlock phases":
`VampireInPlay.qui_vive_played_since_unlock` (new field, `engine/
state.py`), set by this module's own `apply`, cleared each unlock phase by
`engine/phases/unlock.py::_unlock_own_vampires` -- a window wider than one
action (unlike `woken`) and not turn-number-aligned, so a plain flag
rather than `ability_used_turn`'s "store the turn number" convention (see
that field's own docstring for why). Also independently excludes a
candidate already `woken` this action (the engine does nothing to stop
`WAKE_LOCKED_MINION_HOOK` being re-offered for one on a block-attempt
retry, OQ-48's own note) -- re-waking an already-woken vampire would be a
redundant, no-op choice, not a second use of the card.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import WAKE_LOCKED_MINION_HOOK
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 101321
CARD_TYPE = "Reaction"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): matches
this module's own "Card type: Reaction" docstring fact above."""


def _eligible_locked(state: GameState, player: str) -> list[VampireInPlay]:
    """ "Only usable by a locked minion": `player`'s own in-play, currently
    *locked* vampires that are not already `woken` (would be a no-op) and
    have not already played this card since their own last unlock phase."""
    return [
        v
        for v in state.players[player].vampires.values()
        if v.zone == "ready" and v.locked and not v.woken and not v.qui_vive_played_since_unlock
    ]


def _provide_on_the_qui_vive(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]  # WAKE_LOCKED_MINION_HOOK is only ever offered to the defender.
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    eligible = _eligible_locked(state, player)
    if not eligible:
        return []

    def _make_apply(vampire: VampireInPlay) -> Any:
        def _apply(s: GameState) -> None:
            play_from_hand(s, player, KRCG_ID)
            vampire.woken = True
            vampire.qui_vive_played_since_unlock = True

        return _apply

    return [
        HookOption(
            choice=Choice(
                f"on_the_qui_vive:{vampire.instance_id}",
                f"On the Qui Vive: wake {vampire.card.name}",
            ),
            apply=_make_apply(vampire),
            played_card_type=CARD_TYPE,
        )
        for vampire in eligible
    ]


hooks.register(WAKE_LOCKED_MINION_HOOK, _provide_on_the_qui_vive)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="On the Qui Vive",
        status=Status.IMPLEMENTED,
        hooks=(Hook.WAKE_LOCKED_MINION,),
        source=__name__,
    )
)
