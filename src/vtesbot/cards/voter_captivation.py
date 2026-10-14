"""Voter Captivation (Action Modifier). krcg id 102131.

Card text (fetched via krcg 5.14+, `krcg.load()[102131].text`, 2026-10-09):
    "Only usable after resolution of a political action whose referendum
    passed.
    [pre] This vampire gains 1 blood for each vote by which the referendum
    passed.
    [PRE] As above, but move up to 2 of those blood to your pool instead of
    this vampire."

Rulings (verbatim, via krcg):
    - "Is played after resolution, after all combats (if any) are handled,
      but still during the action. Action modifiers and effects that can be
      played 'after resolution' can be played before or after it."
      [PIB 20150915] [LSJ 19981028] [ANK 20190425]
    - "Is played after the referendum is resolved. If the effect of the
      referendum ousts the acting Methuselah, there is no time to play it to
      prevent the ousting." [RTR 19951110]
    - "Can be used after a referendum that is automatically passing, but the
      vote is considered to have passed by 0 votes." [LSJ 19980107]
      [PIB 20150105]

`types == ["Action Modifier"]`; `disciplines == ["pre"]`; `clans == []` (no
clan requirement -- any Methuselah's own ready [pre]/[PRE] vampire qualifies,
not only a Toreador's, despite shipping in the suggested Toreador 2P deck).

Status: implemented (OQ-36, `docs/OPEN_QUESTIONS.md`, resolved --
`engine/action.py::REFERENDUM_RESOLVED_HOOK`, dispatched via
`hooks.resolve_impulse_window` right after a passing political action's own
`resolve(pending)` call returns).

Who may play it: the card names no specific vampire/Methuselah up front --
"this vampire" (both clauses) is whichever ready vampire the playing
Methuselah chooses, not necessarily the referendum's own caller. The hook
is offered to both `caller`/`other` by its own dispatch (`engine/action.py`),
so either side may play their own copy for their own eligible vampire; this
module's own gate is purely "does `context['player']` control a ready
vampire with the needed discipline, and hold the card in hand" -- mirroring
`enchant_kindred.py`'s/`fleetness.py`'s own per-vampire `context["player"]`
eligibility pattern, not `perfect_paragon.py`'s basic clause (which is
caller-only because its own text says "This vampire gets +3 votes" immediately
after "[pre] Only usable during the polling step", read there as the calling
vampire specifically -- Voter Captivation's own trigger carries no such tie).
Discipline gating reads the plain printed `card.disciplines` (not the
attachment-aware `effective_disciplines`), the same convention
`enchant_kindred.py`/`fleetness.py`/`dust_up.py` already use. "This vampire"
must be in play and not in torpor to receive blood/act as "your" vampire at
all -- `zone == "ready"` is the gate (mirrors `engine/politics.py`'s own
"`VampireInPlay.locked` is irrelevant" voting convention: this card is not an
action, so lock state does not matter either).

Single, repeatable two-sided window, not a proactive/reactive split (unlike
OQ-30/31's `INTERCEPT_DECREASE_HOOK` family): Perfect Paragon's own split
exists because that card can be played either before any block candidate is
fixed or reactively once one is -- two textually and timing-distinct moments
within one action. Voter Captivation has only one trigger moment ("after
resolution... whose referendum passed"), and the first ruling above
("can be played before or after" some other post-resolution effect) is
already satisfied structurally by `hooks.resolve_impulse_window`'s own
alternating, repeat-until-both-pass loop -- not a second, differently-shaped
offer point this module would need to build. No further engine gap found.

Basic clause ("This vampire gains 1 blood for each vote by which the
referendum passed"): `context["margin"]` (`votes_for - votes_against`,
computed by `perform_minion_action` only once the referendum is confirmed
passed, so always >= 1 under this engine's current dispatch gate -- see
`REFERENDUM_RESOLVED_HOOK`'s own docstring) is added via
`engine/damage.py::add_blood`, which already floors at 0 and caps at the
target's `effective_capacity` (OQ-8) -- no extra capacity-check code needed
here, matching `enchant_kindred.py`'s own use of the same helper. The "0
votes" automatically-passing ruling needs no special-case: `add_blood`
already treats a 0 amount as a no-op, and this engine has no automatically-
passing mechanism yet to ever actually reach that case (`docs/
OPEN_QUESTIONS.md` OQ-6's own note, `perfect_paragon.py`'s identical
"unreachable today, not a dropped ruling" precedent) -- not gated out here
regardless, since the ruling explicitly permits the play even at margin 0.

Superior clause ("As above, but move up to 2 of those blood to your pool
instead of this vampire"): the redirected blood never reaches the vampire at
all -- `moved` (chosen below) is subtracted from `margin` before `add_blood`
runs, then `gain_pool`s the controller directly. "Up to 2" is a genuine choice
(0..`min(2, margin)`), raised as its own `Decision`
("voter_captivation_redirect") inside `apply()`, mirroring
`kine_resources_contested.py`'s own nested post-play allocation decision; with
`margin == 0` the only legal amount is 0, so (per the `enchant_kindred.py`
"single eligible option: bind directly, no decision raised" convention) no
decision is raised in that edge case.

Per-vampire once-per-action cap (`rules-auditor` finding): Rulebook §2 Card
Types, verbatim: "A minion cannot play the same action modifier card more
than once during a single action (even if using a different Discipline
level)." Two copies of this card in hand previously let the same target
vampire be fed the option twice in the same `REFERENDUM_RESOLVED_HOOK`
window (`hooks.resolve_impulse_window` re-offers until both sides pass).
`context["pending"]` (now threaded through by `engine/action.py`'s own
dispatch, mirroring `cards/bonding.py`'s `LIMITED_USED_KEY` convention)
tracks `GRANTED_KEY`, a `set[str]` of target vampire `instance_id`s already
granted *either* clause this window; both providers below skip a target
already in that set, and `apply()` adds it. This caps per target vampire,
not globally -- a second copy may still benefit a *different* ready
vampire the same controller controls, which the rulebook clause does not
forbid (it restricts the same card being played twice by *one* minion, not
a second, independent minion playing its own copy).
"""

from collections.abc import Mapping
from typing import Any

from vtesbot.cards._shared import play_from_hand
from vtesbot.cards.registry import CardRegistration, Hook, Status, register
from vtesbot.engine import hooks
from vtesbot.engine.action import REFERENDUM_RESOLVED_HOOK
from vtesbot.engine.damage import add_blood
from vtesbot.engine.decision import Choice, Decision
from vtesbot.engine.hooks import HookOption
from vtesbot.engine.pool import gain_pool
from vtesbot.engine.state import GameState, VampireInPlay

KRCG_ID = 102131
BASIC = "pre"
SUPERIOR = "PRE"
MAX_REDIRECT = 2
"""Printed "move up to 2 of those blood ...."."""
CARD_TYPE = "Action Modifier"
"""`HookOption.played_card_type` (OQ-33, `docs/OPEN_QUESTIONS.md`): matches
this module's own "Card type" docstring fact above."""
GRANTED_KEY = "voter_captivation_granted_vampires"
"""Module docstring's "Per-vampire once-per-action cap": `context["pending"]`
key holding the `set[str]` of target vampire `instance_id`s already granted
this window."""


def _granted(pending: dict[str, Any]) -> set[str]:
    return pending.setdefault(GRANTED_KEY, set())


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _eligible_vampires(state: GameState, player: str, required: str) -> list[VampireInPlay]:
    return [
        v
        for v in state.players[player].vampires.values()
        if v.zone == "ready" and required in v.card.disciplines
    ]


def _provide_voter_captivation_basic(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "[pre] This vampire gains 1 blood for each vote by which the
    referendum passed." -- see module docstring for the per-player
    eligibility gate and the `add_blood` capacity cap."""
    player = context["player"]
    margin = context["margin"]
    granted = _granted(context["pending"])
    if not _has_card_in_hand(state, player):
        return []
    targets = [
        v
        for v in state.players[player].vampires.values()
        if v.zone == "ready"
        and (BASIC in v.card.disciplines or SUPERIOR in v.card.disciplines)
        and v.instance_id not in granted
    ]
    if not targets:
        return []

    options: list[HookOption] = []
    for target in targets:

        def _apply(s: GameState, target_id: str = target.instance_id) -> None:
            play_from_hand(s, player, KRCG_ID)
            vampire = s.players[player].vampires[target_id]
            add_blood(s, vampire, margin)
            granted.add(target_id)

        options.append(
            HookOption(
                choice=Choice(
                    f"voter_captivation:basic:{target.instance_id}",
                    f"Voter Captivation [pre]: {target.card.name} gains {margin} blood",
                ),
                apply=_apply,
                played_card_type=CARD_TYPE,
            )
        )
    return options


def _provide_voter_captivation_superior(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "[PRE] As above, but move up to 2 of those blood to your pool
    instead of this vampire." -- see module docstring for the nested
    redirect-amount `Decision`."""
    player = context["player"]
    margin = context["margin"]
    granted = _granted(context["pending"])
    if not _has_card_in_hand(state, player):
        return []
    targets = [
        v for v in _eligible_vampires(state, player, SUPERIOR) if v.instance_id not in granted
    ]
    if not targets:
        return []

    options: list[HookOption] = []
    for target in targets:

        def _apply(s: GameState, target_id: str = target.instance_id) -> int:
            play_from_hand(s, player, KRCG_ID)
            granted.add(target_id)
            max_redirect = min(MAX_REDIRECT, margin)
            if max_redirect <= 0:
                moved = 0
            else:
                choices = tuple(
                    Choice(f"redirect:{n}", f"Move {n} blood to your pool")
                    for n in range(0, max_redirect + 1)
                )
                decision = Decision(
                    player=player,
                    kind="voter_captivation_redirect",
                    choices=choices,
                )
                moved = int(s.ask(decision).value.split(":", 1)[1])
            vampire = s.players[player].vampires[target_id]
            add_blood(s, vampire, margin - moved)
            gain_pool(s, player, moved)
            return moved

        options.append(
            HookOption(
                choice=Choice(
                    f"voter_captivation:superior:{target.instance_id}",
                    f"Voter Captivation [PRE]: {target.card.name} gains blood "
                    "(move up to 2 to your pool instead)",
                ),
                apply=_apply,
                played_card_type=CARD_TYPE,
            )
        )
    return options


hooks.register(REFERENDUM_RESOLVED_HOOK, _provide_voter_captivation_basic)
hooks.register(REFERENDUM_RESOLVED_HOOK, _provide_voter_captivation_superior)

register(
    CardRegistration(
        krcg_id=KRCG_ID,
        name="Voter Captivation",
        status=Status.IMPLEMENTED,
        hooks=(Hook.REFERENDUM_RESOLVED,),
        source=__name__,
    )
)
