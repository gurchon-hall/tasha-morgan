"""Enchant Kindred (Action). krcg id 100640.

Card text (verbatim, re-verified via the installed `krcg` package's own raw
snapshot and cross-checked live against `https://api.krcg.org/card/100640`,
2026-10-10; both match `data/cards/100640.json` byte-for-byte):
    "[pre] Ⓓ Bleed with +1 bleed.
    [PRE] +1 stealth action. Add 2 blood to a younger vampire in your
    uncontrolled region."

Rulings: none on file -- `rulings == []`, both via the installed `krcg`
package and the live API (re-checked 2026-10-10).

Card type: Action (`types == ["Action"]`, *not* "Action Modifier").
`discipline_requirement == {"type": "Mono", "disciplines": ["pre"]}` (basic
Presence required to play the card at all; superior Presence, printed
uppercase "PRE" on a `CryptCard`, additionally unlocks the second clause --
Rulebook SS3 "Discipline symbol within a diamond ... may opt to use either
the basic (plain text) or the superior (bold) effect ... but not both").
`clan_requirement == []`, `cost is None`, `burn_option is False`,
`trifle is False`.

Status: implemented. Previously `blocked` (OQ-17, `docs/OPEN_QUESTIONS.md`,
now resolved) for want of a generic engine entry point letting a library
card of printed `types == ["Action"]` supply its own self-contained minion
action; `engine/phases/minion.py::ACTION_CARD_PLAY_HOOK` /
`ActionCardSpec` / `_perform_action_card` is that entry point. Both clauses
below are `ACTION_CARD_PLAY_HOOK` providers, mirroring the "basic vs
superior, two different hooks/providers for one physical card" shape already
used by `bonding.py`/`threats.py`/`telepathic_counter.py`/`celerity.py`
(`disciplines` gating: a vampire with only basic `"pre"` unlocks only the
basic clause; a vampire with superior `"PRE"` is eligible for either, per
Rulebook SS3 "may opt to use either effect").

"Ⓓ" (basic clause): the rulebook glossary's own "Directed Action" entry
(`data/sources/rulebook/2026-10-09/8-glossaries.md:59`) -- a *directed*
bleed, amount 2 (the default 1, +1 printed). Its card text literally prints
the word "Bleed", so (OQ-17's rules-auditor-fixed requirement)
`ActionCardSpec.action` is declared `ACTION_BLEED`, not left at the generic
`ACTION_ACTION_CARD` default -- this is required, not merely cosmetic, so an
existing bleed-gated provider sharing the same block-attempt/bleed-amount
hook windows (e.g. `bonding.py`'s superior clause, gated on
`context.get("action") == ACTION_BLEED`) is not silently and wrongly
suppressed when both cards are in the same hand. `resolve()` mirrors
`engine/phases/minion.py::_perform_bleed`'s own closure byte-for-byte (same
fixed/impulse-window/clamp/edge-holder computation), with the base amount
hardcoded to 2 (this card's own printed "+1 bleed" baked directly into the
baseline, replacing `_perform_bleed`'s `BLEED_AMOUNT` constant of 1) rather
than reinventing the pattern -- so any other bleed-amount card (Bonding's
basic clause, Threats, Telepathic Counter, a vampire's own flat "+1 bleed"
text via `BLEED_AMOUNT_FIXED_MODIFIER_HOOK`) still applies correctly on top
of this bleed, exactly as it would on top of an ordinary default bleed.

"+1 stealth action. Add 2 blood to a younger vampire in your uncontrolled
region." (superior clause): carries no "Ⓓ" marker and names no target
Methuselah -- an *undirected* action per the glossary's adjacent "Undirected
Action" entry (same file, line 197); its only effect touches the acting
player's own uncontrolled region. Not textually a bleed/hunt/etc., so
`ActionCardSpec.action` is left at the generic `ACTION_ACTION_CARD` default.
`base_stealth=1` bakes in the card's own printed "+1 stealth" baseline (this
action's equivalent of `HUNT_STEALTH`/`RECRUIT_ALLY_STEALTH`, not a
declinable modifier layered on top of a 0 baseline). Both clauses already
collapse to the engine's existing single-opponent block-attempt model for a
2P duel (`engine/action.py`'s own module docstring; not OQ-1, which is
scoped to unsettled card wording, not this already-settled structural
collapse), so neither raises a fresh prey/predator question.

"a younger vampire" (superior clause): names no explicit comparison target
in its own sentence. Per OQ-17's own resolution note (`docs/
OPEN_QUESTIONS.md`), confirmed directly by the project owner on 2026-10-10:
read as younger than the acting vampire (the vampire using the [PRE]
ability) -- consistent with the broader unqualified-comparative convention
other printed card texts use (e.g. Danny Larkshill, Apolonia Czarnecki, both
cross-checked live via `krcg.load()`), and with how `grooming_the_protege.py`
already reads an analogous (but differently worded) "younger vampire"
clause: strictly lower *printed* capacity (`vampire.card.capacity`, not the
attachment-aware `effective_capacity` -- OQ-8's `effective_capacity` is used
below only for the blood-capacity room check on the destination, which is
the correct use per OQ-8's own resolution) than the acting vampire.

Target region: "in your uncontrolled region" -- `zone == "uncontrolled"` and
`controller == player` (own uncontrolled region only). A target already at
(effective) capacity is not offered (no room for even 1 of the printed 2
blood would make offering it a vacuous choice; `add_blood` itself still
clamps defensively).

"which eligible vampire to add blood to" is a new per-card `Decision` (kind
"enchant_kindred_target") raised directly inside `resolve()`, once unblocked
-- OQ-17's own resolution confirmed the existing `Decision`/`Choice`
machinery already supports an arbitrary "pick one of your own eligible
vampires" choice with no further engine change needed. Mirrors
`engine/phases/unlock.py::_resolve_optional_effects_in_chosen_order`'s own
"only when needed" convention: with exactly one eligible target, applied
directly with no decision raised at all; with more than one, a `Decision`
offers one choice per eligible target (no "decline"/"pass" alternative --
by the time `resolve()` runs the card has already been played and the
effect is mandatory, Rulebook SS4 "Resolve the Action": only *which* target
remains to be chosen).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import effective_capacity, hooks
from vtesbot.engine.action import ACTION_BLEED
from vtesbot.engine.damage import add_blood
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.phases.minion import (
    ACTION_CARD_PLAY_HOOK,
    BLEED_AMOUNT_FIXED_MODIFIER_HOOK,
    BLEED_AMOUNT_MODIFIER_HOOK,
    PENDING_BLEED_AMOUNT_KEY,
    ActionCardSpec,
)
from vtesbot.engine.pool import lose_pool
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 100640
BASIC = "pre"
SUPERIOR = "PRE"
BASIC_BLEED_BASE_AMOUNT = 2
"""Default bleed amount (1) + this card's own printed "+1 bleed", baked into
the baseline the same way `_perform_bleed`'s own `BLEED_AMOUNT` constant (1)
is -- not a separately-offered, declinable modifier."""
SUPERIOR_STEALTH = 1
"""This card's own printed "+1 stealth" baseline for its undirected action
(mirrors `HUNT_STEALTH`/`RECRUIT_ALLY_STEALTH`, `engine/phases/minion.py`),
not a modifier layered on top of a 0 baseline."""
ADD_BLOOD_AMOUNT = 2


def _eligible_targets(
    state: GameState, player: str, acting_vampire: VampireInPlay
) -> list[VampireInPlay]:
    player_state = state.players[player]
    return [
        v
        for v in player_state.vampires.values()
        if v.zone == "uncontrolled"
        and v.card.capacity < acting_vampire.card.capacity
        and effective_capacity(state, v) - v.blood > 0
    ]


def _provide_enchant_kindred_basic(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "[pre] Ⓓ Bleed with +1 bleed" -- a directed bleed, amount 2."""
    player = context["player"]
    acting_vampire_id = context["vampire"]
    acting_vampire = state.players[player].vampires.get(acting_vampire_id)
    if acting_vampire is None:
        return []  # `player` is the defender this window, not the acting player.

    disciplines = acting_vampire.card.disciplines
    if BASIC not in disciplines and SUPERIOR not in disciplines:
        return []
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []

    def _apply(s: GameState) -> ActionCardSpec:
        play_from_hand(s, player, KRCG_ID)

        def resolve(pending: dict[str, Any]) -> None:
            other = s.other_player(player)
            base_amount = (
                BASIC_BLEED_BASE_AMOUNT
                + hooks.sum_modifiers(
                    BLEED_AMOUNT_FIXED_MODIFIER_HOOK,
                    s,
                    player=player,
                    vampire=acting_vampire.instance_id,
                )
                + pending.get(PENDING_BLEED_AMOUNT_KEY, 0)
            )
            amount_box = [base_amount]
            hooks.resolve_impulse_window(
                s,
                BLEED_AMOUNT_MODIFIER_HOOK,
                player,
                other,
                context={
                    "vampire": acting_vampire.instance_id,
                    "amount": amount_box,
                    "pending": pending,
                },
            )
            amount = max(0, amount_box[0])
            lose_pool(s, other, amount)
            if amount >= 1:
                s.edge_holder = player

        return ActionCardSpec(
            base_stealth=0,
            directed=True,
            resolve=resolve,
            action=ACTION_BLEED,
        )

    return [
        HookOption(
            choice=Choice("enchant_kindred:basic", "Enchant Kindred [pre]: Bleed with +1 bleed"),
            apply=_apply,
        )
    ]


def _provide_enchant_kindred_superior(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "[PRE] +1 stealth action. Add 2 blood to a younger vampire in your
    uncontrolled region." -- an undirected action."""
    player = context["player"]
    acting_vampire_id = context["vampire"]
    acting_vampire = state.players[player].vampires.get(acting_vampire_id)
    if acting_vampire is None:
        return []

    if SUPERIOR not in acting_vampire.card.disciplines:
        return []
    if not any(card.krcg_id == KRCG_ID for card in state.players[player].hand):
        return []
    if not _eligible_targets(state, player, acting_vampire):
        return []  # no legal target: do not offer a card play that cannot resolve.

    def _apply(s: GameState) -> ActionCardSpec:
        play_from_hand(s, player, KRCG_ID)

        def resolve(pending: dict[str, Any]) -> None:
            del pending  # no later window of its own to feed.
            targets = _eligible_targets(s, player, acting_vampire)
            if not targets:
                return  # defensive: nothing legal remains at resolve time.
            if len(targets) == 1:
                target = targets[0]
            else:
                choices = tuple(
                    Choice(
                        f"enchant_kindred_target:{v.instance_id}",
                        f"Add 2 blood to {v.card.name}",
                    )
                    for v in targets
                )
                decision = Decision(player=player, kind="enchant_kindred_target", choices=choices)
                chosen_value = s.ask(decision).value
                target_id = chosen_value.split(":", 1)[1]
                target = s.players[player].vampires[target_id]
            add_blood(s, target, ADD_BLOOD_AMOUNT)

        return ActionCardSpec(
            base_stealth=SUPERIOR_STEALTH,
            directed=False,
            resolve=resolve,
        )

    return [
        HookOption(
            choice=Choice(
                "enchant_kindred:superior",
                "Enchant Kindred [PRE]: +1 stealth action. "
                "Add 2 blood to a younger vampire in your uncontrolled region",
            ),
            apply=_apply,
        )
    ]


hooks.register(ACTION_CARD_PLAY_HOOK, _provide_enchant_kindred_basic)
hooks.register(ACTION_CARD_PLAY_HOOK, _provide_enchant_kindred_superior)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Enchant Kindred",
        status=Status.IMPLEMENTED,
        hooks=(Hook.ACTION_CARD_PLAY,),
        source=__name__,
    )
)
