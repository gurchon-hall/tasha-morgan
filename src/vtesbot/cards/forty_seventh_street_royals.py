"""47th Street Royals (Ally). krcg id 102217.

Card text (re-verified live via a fresh `krcg.load()[102217]` fetch,
2026-10-09, matching the raw snapshot `data/cards/102217.json`, byte-for-byte
unchanged since ENG-001/ENG-006/ENG-007/ENG-008's own quotes):
    "Unique mortal with 2 life. 1 strength, 0 bleed.
    You can burn 47th Street Royals to reduce a bleed against you by 3."

Rulings: none on file -- `krcg.load()[102217].rulings == []`.

Card type: Ally. `clan_requirement == ["Brujah"]`, `discipline_requirement.
disciplines == []`. `cost is None` and `burn_option is False` per krcg's own
fields (this card's burn-to-reduce-bleed mechanic is the card's own printed
text, not the engine's generic `burn_option` flag). Listed in the active 2P
allowed list (`data/formats/2p/2026-10-03.json`, `krcg_id: 102217`).

Status: implemented. Depends on ENG-006 ("recruit ally" minion action), ENG-007
(acting-vampire identity in the `"recruit_ally_play"` hook context), ENG-004
(ally contest *detection*, `AllyInPlay.contested_with`/`zone ==
"contested"`, `engine/allies.py::detect_contest_on_recruit`), and ENG-009
(contest *resolution*: `engine/allies.py::resolve_one_ally_contest` plus
`engine/phases/unlock.py::_unlock_own_allies`'s pay-1-pool-or-yield
unlock-phase loop) -- all resolved. ENG-010 ("cannot contest yourself",
resolved) now burns a same-controller second copy of a unique card
immediately on recruit rather than contesting it; still unreachable here, as
no deck-legality check yet lets one player hold two copies of the same
unique card.

Two independent clauses, matching the registry's established "wire what the
text says, nothing more" pattern (e.g. `threats.py`):

1. "Unique mortal with 2 life. 1 strength, 0 bleed." -- the Ally's own
   recruit eligibility, wired against the `"recruit_ally_play"` hook (ENG-006).
   Checked against *this specific* acting vampire (`context["vampire"]`,
   ENG-007) rather than merely "the player controls a Brujah somewhere"
   (Rulebook §2 "Requirements for Playing Cards" binds a minion card's
   requirement to the specific acting minion), via `acting_vampire.card.clan`
   -- a plain printed-stat field. Returns a `RecruitAllySpec(card=..., life=2,
   strength=1, bleed=0, pay_cost=None)` -- `pay_cost=None` because krcg's own
   `cost` field is `None` ("Cost: As listed on the ally card"; this card
   lists none). `_perform_recruit_ally` handles everything else generically:
   announcing, the block-attempt window, paying cost only on success,
   placing the ally in play ready-but-locked, burning the card on a block
   (Rulebook §4 "Resolve the Action"), and -- the prerequisite this entry
   was blocked on -- calling `detect_contest_on_recruit` after every
   successful recruit, so two Methuselahs each recruiting their own copy
   correctly end with both copies `zone == "contested"`. Nothing about
   uniqueness/contest handling needs to appear in *this* module.

2. "You can burn 47th Street Royals to reduce a bleed against you by 3." --
   a reaction, wired against the `"bleed_amount_modifier"` hook, the same
   shape as `telepathic_counter.py`'s reduction, except the cost consumed is
   the ally itself (`engine/allies.py::burn_ally`), not a card played from
   hand. `_provide_bleed_reduction` offers its option only to this ally's own
   controller, and only while this specific ally (matched by `krcg_id`; at
   most one live copy per controller since it is Unique, enforced by ENG-010's
   resolved fix) is `zone == "ready"`: a contested ally is "turned face
   down and out of play" (Rulebook §4 Advanced Rules > Contested Cards) for
   the whole contest and cannot react; a burned one is simply gone.
   `AllyInPlay.is_ready_unlocked` is deliberately not used: the card names no
   playing minion ("you can burn 47th Street Royals"), so §8 glossary
   "Reaction Card"'s "ready, unlocked" requirement (which governs which
   *minion* may play a reaction) does not apply to the ally being spent as
   the cost -- only `zone == "ready"` is checked, matching `tests/rules/
   test_allies.py`'s proven stand-in. Reducing the pending bleed amount
   reuses `_perform_bleed`'s own `amount_box`/`pending` threading and clamp.
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand_pending
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.allies import RecruitAllySpec, burn_ally
from vtesbot.engine.decision import Choice
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import RECRUIT_ALLY_PLAY_HOOK
from vtesbot.engine.state import GameState

KRCG_ID = 102217
BLEED_AMOUNT_MODIFIER_HOOK = "bleed_amount_modifier"
LIFE = 2
STRENGTH = 1
BLEED = 0
BLEED_REDUCTION = 3
CLAN_REQUIREMENT = ("Brujah",)
CARD_TYPE = "Ally"
"""`HookOption.played_card_type` (ENG-023): matches
this module's own "Card type: Ally" docstring fact above -- set only on the
recruit (`_provide_recruit`, the card actually leaving hand); the bleed-
reduction clause (`_provide_bleed_reduction`) burns an already-recruited,
in-play copy as its own cost, not a card played from hand (module docstring:
"the cost consumed is the ally itself ... not a card played from hand"), so
it leaves `HookOption.played_card_type` at its default `None` (see that
field's own docstring)."""


def _provide_recruit(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    acting_vampire_id = context.get("vampire")
    acting_vampire = state.players[player].vampires.get(acting_vampire_id)
    if acting_vampire is None:
        return []  # no such ready-unlocked vampire of this player's own is acting
    if acting_vampire.card.clan not in CLAN_REQUIREMENT:
        return []
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    def _apply(s: GameState) -> RecruitAllySpec:
        played = play_from_hand_pending(s, player, KRCG_ID)
        return RecruitAllySpec(
            card=played, life=LIFE, strength=STRENGTH, bleed=BLEED, pay_cost=None
        )

    return [
        HookOption(
            choice=Choice("recruit_47th_street_royals", "Recruit 47th Street Royals"),
            apply=_apply,
            played_card_type=CARD_TYPE,
        )
    ]


def _is_defender(state: GameState, player: str, acting_vampire_id: str) -> bool:
    return acting_vampire_id not in state.players[player].vampires


def _provide_bleed_reduction(state: GameState, context: Mapping[str, Any]) -> list[HookOption]:
    player = context["player"]
    acting_vampire_id = context["vampire"]
    if not _is_defender(state, player, acting_vampire_id):
        return []

    ally = next(
        (
            a
            for a in state.players[player].allies.values()
            if a.krcg_id == KRCG_ID and a.zone == "ready"
        ),
        None,
    )
    if ally is None:
        return []

    amount_box = context["amount"]

    def _apply(s: GameState) -> None:
        burn_ally(s, player, ally)
        amount_box[0] -= BLEED_REDUCTION

    return [
        HookOption(
            choice=Choice("burn_47th_street_royals", "Burn 47th Street Royals: reduce bleed by 3"),
            apply=_apply,
        )
    ]


hooks.register(RECRUIT_ALLY_PLAY_HOOK, _provide_recruit)
hooks.register(BLEED_AMOUNT_MODIFIER_HOOK, _provide_bleed_reduction)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="47th Street Royals",
        status=Status.IMPLEMENTED,
        hooks=(Hook.ALLY_ENTITY, Hook.RECRUIT_ALLY_PLAY, Hook.BLEED_AMOUNT_MODIFIER),
        source=__name__,
    )
)
