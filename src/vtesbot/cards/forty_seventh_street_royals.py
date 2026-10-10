"""47th Street Royals (Ally). krcg id 102217.

Card text (re-verified live via a fresh `krcg.load()[102217]` fetch,
2026-10-09, matching the raw snapshot `data/cards/102217.json`, byte-for-byte
unchanged since OQ-7/OQ-12/OQ-13/OQ-14's own quotes):
    "Unique mortal with 2 life. 1 strength, 0 bleed.
    You can burn 47th Street Royals to reduce a bleed against you by 3."

Rulings: none on file -- `krcg.load()[102217].rulings == []`.

Card type: Ally. `clan_requirement == ["Brujah"]`, `discipline_requirement.
disciplines == []`. `cost is None` and `burn_option is False` per krcg's own
fields (this card's burn-to-reduce-bleed mechanic is the card's own printed
text, not the engine's generic `burn_option` flag). Listed in the active 2P
allowed list (`data/formats/2p/2026-10-03.json`, `krcg_id: 102217`).

Status: implemented. Was blocked (OQ-14, `docs/OPEN_QUESTIONS.md`), on top of
the earlier, also now-resolved OQ-12 ("recruit ally" minion action) and OQ-13
(acting-vampire identity threaded into the `"recruit_ally_play"` hook
context). OQ-14 itself was the discovery that wiring this card's own recruit
side would make OQ-10's ally-uniqueness gap live in an ordinary legal 2P
game; `rules-engineer` resolved OQ-10 (contest *detection*, `AllyInPlay.
contested_with`/`zone == "contested"`, `engine/allies.py::
detect_contest_on_recruit`, called from `_perform_recruit_ally`'s own
production call site) and then OQ-15 (contest *resolution*, the
pay-1-pool-or-yield unlock-phase loop that actually ends a contest --
`engine/allies.py::resolve_one_ally_contest` plus `engine/phases/unlock.py::
_unlock_own_allies`). With both halves of that prerequisite now independently
audited clean (per this task's own briefing), this card's own two clauses are
wired below. OQ-16 ("cannot contest yourself") stays open but is confirmed
unreachable here: no deck-legality check yet lets one player hold two copies
of the same unique card, so `detect_contest_on_recruit` never needs to
consider that case for this card either.

Two independent clauses, matching the registry's established "wire what the
text says, nothing more" pattern (`threats.py`/`bonding.py`):

1. "Unique mortal with 2 life. 1 strength, 0 bleed." -- the Ally's own
   recruit eligibility, wired against the `"recruit_ally_play"` hook
   (`engine/phases/minion.py::RECRUIT_ALLY_PLAY_HOOK`, OQ-12). `_provide_
   recruit` mirrors the shape OQ-12/OQ-13's own scaffolding tests already
   exercise with a stand-in provider (`tests/rules/test_recruit_ally_action.
   py`, `tests/rules/test_ally_contests.py`): checked against *this specific*
   acting vampire (`context["vampire"]`, OQ-13) rather than merely "the
   player controls a Brujah somewhere" (Rulebook SS2 "Card Types" >
   "Requirements for Playing Cards" binds a minion card's requirement to the
   specific acting minion), via `acting_vampire.card.clan` -- confirmed by
   reading `engine/cards.py::CryptCard.clan` directly rather than assumed:
   a plain printed-stat field, exactly the engine's existing "clan/title/
   disciplines are plain printed stats, not behaviour" contract. Returns a
   `RecruitAllySpec(card=..., life=2, strength=1, bleed=0, pay_cost=None)`
   (`engine/allies.py::RecruitAllySpec`) -- `pay_cost=None` because krcg's
   own `cost` field is `None` ("Cost: As listed on the ally card"; this card
   lists none). `_perform_recruit_ally` (`engine/phases/minion.py`) handles
   everything else generically: announcing (removing the card from hand via
   `play_from_hand_pending`, done inside this module's own `apply`, per
   `RecruitAllySpec`'s own contract that `apply` must have already removed
   the card), the block-attempt window, paying the (here: nonexistent) cost
   only on success, placing the ally in play ready-but-locked
   (`recruit_ally`), burning the card to the ash heap with no ally created on
   a block (Rulebook SS4 "Resolve the Action"), and -- the exact prerequisite
   this entry was blocked on -- calling `detect_contest_on_recruit` after
   every successful recruit, so two Methuselahs each recruiting their own
   copy in an ordinary 2P game correctly ends with both copies `zone ==
   "contested"`, out of play, not two silently-coexisting `AllyInPlay`
   instances. Nothing about uniqueness/contest handling needs to appear in
   *this* module -- it is unconditionally generic in `recruit_ally`/
   `_perform_recruit_ally` now, exactly per OQ-14's own resolution note.

2. "You can burn 47th Street Royals to reduce a bleed against you by 3." --
   a reaction, wired against the already-wired `"bleed_amount_modifier"` hook
   (`engine/phases/minion.py::_perform_bleed`'s `resolve()`), byte-for-byte
   the same shape as `telepathic_counter.py`'s reduction and the exact
   mechanism already proven by `tests/rules/test_allies.py::
   test_ally_burned_as_a_bleed_reduction_reaction_cost`'s stand-in provider,
   except the cost consumed is the ally itself (`engine/allies.py::
   burn_ally`), not a card played from hand. `_provide_bleed_reduction`
   offers its option only to this ally's own controller (checked the same
   way `telepathic_counter.py` checks "is `context["player"]` the defender":
   the acting, bleeding vampire -- `context["vampire"]` -- is not one of
   `context["player"]`'s own vampires), and only while this specific ally
   (matched by `krcg_id`, since it is Unique there can be at most one live
   copy under any one controller at a time -- OQ-16 notwithstanding, see
   above) is `zone == "ready"`: a `"contested"` ally is "turned face down and
   out of play" (Rulebook SS4 Advanced Rules > Contested Cards, quoted in
   full in `engine/allies.py`'s own module docstring) for the whole contest,
   so it cannot react, exactly like a contested *vampire* cannot act; a
   `"burned"` one is simply gone. `AllyInPlay.is_ready_unlocked` is not used
   here deliberately -- unlike a vampire or an acting minion, nothing in the
   rules requires this *reacting* ally itself to be unlocked (it is not
   taking an action, merely being spent as a cost: Rulebook SS8 glossary
   "Reaction Card" requires the reacting *minion* to be "ready, unlocked",
   but that requirement is about which of the Methuselah's own minions may
   play the reaction, not about the specific card/entity being spent as the
   reaction's own cost -- the card text names no minion at all, "you can
   burn 47th Street Royals", so there is no separate "ready unlocked minion
   playing this" to check beyond the ally being in play and usable, i.e.
   `zone == "ready"`), so only `zone == "ready"` is checked, matching exactly
   what `tests/rules/test_allies.py`'s own proven stand-in checks
   (`a.zone == "ready" and a.name == "47th Street Royals"`). Reducing the
   pending bleed amount reuses `_perform_bleed`'s own `amount_box`/`pending`
   threading and its `amount = max(0, amount_box[0])` clamp -- no separate
   clamp is needed here, same as `telepathic_counter.py`.
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
