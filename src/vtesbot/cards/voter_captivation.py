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

Who may play it (OQ-38, `docs/OPEN_QUESTIONS.md`, resolved -- user ruling,
Reading A): "this vampire" (both clauses) is the political action's own
*acting* vampire specifically -- `context["caller_vampire_id"]` -- never a
free choice among the controller's other ready [pre]/[PRE] vampires, and
never playable by the non-caller Methuselah at all. Rulebook §2 Card Types,
verbatim: "The acting minion can play [action modifier cards]... Some action
modifier cards are played by minions 'other than the acting minion'. Only
minions controlled by the same Methuselah can play those cards." Voter
Captivation carries no such override phrase, so the unqualified default
applies: only the acting minion, full stop. Unlike Scalpel Tongue (OQ-38's
other half), this card has no Reaction-typed half to separately justify a
non-caller use, so the defending Methuselah's own copy of Voter Captivation
is simply unplayable -- an accepted consequence of this reading, not a gap.
This replaces this module's earlier, broader reading (any ready [pre]/[PRE]
vampire of whichever Methuselah played the card) that `rules-auditor`
flagged as unverified against the Perfect Paragon precedent (OQ-30/31, an
identical "[pre] This vampire ..." shape immediately after a trigger clause,
already read there as caller-only).

`REFERENDUM_RESOLVED_HOOK` is still offered to both `caller`/`other` by its
own dispatch (`engine/action.py`, `hooks.resolve_impulse_window`'s two-sided
alternation) -- this module's own gate is what actually enforces the
restriction: `context["player"] != context["caller"]` short-circuits to no
options, so `other`'s own turn in the window never sees anything from this
card regardless of what vampires they control.

`context["caller_vampire_id"]` resolves to a live `VampireInPlay` via
`state.players[context["caller"]].vampires.get(...)` -- `None` (vampire
removed from the game some other way) or `zone != "ready"` (e.g. sent to
torpor by combat before resolution, structurally possible since this hook
fires after any combat the political action's own block attempt produced)
both mean no option is offered; `VampireInPlay.locked` is irrelevant here
(mirrors `engine/politics.py`'s own "locked is irrelevant to voting"
convention -- this card is not an action and raises nothing about the
vampire's own lock state, and the acting vampire is, in any case, always
locked by this point, Rulebook §4, so checking it would make the card
permanently unplayable). Discipline gating reads the plain printed
`card.disciplines` (not the attachment-aware `effective_disciplines`), the
same convention `enchant_kindred.py`/`fleetness.py`/`dust_up.py` already use.

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

Per-action cap (`rules-auditor` finding): Rulebook §2 Card Types, verbatim:
"A minion cannot play the same action modifier card more than once during a
single action (even if using a different Discipline level)." With "this
vampire" now pinned to the single acting vampire (OQ-38 above), only one
vampire is ever a candidate target -- but a second copy of this card in hand
could still try to feed that same vampire the option a second time in the
same `REFERENDUM_RESOLVED_HOOK` window (`hooks.resolve_impulse_window`
re-offers until both sides pass). `context["pending"]` (threaded through by
`engine/action.py`'s own dispatch, mirroring `cards/bonding.py`'s
`LIMITED_USED_KEY` convention) tracks `GRANTED_KEY`, a `set[str]` holding the
acting vampire's own `instance_id` once granted *either* clause this window;
both providers below skip entirely once it is present. (Kept as a `set`,
not a plain `bool`, for parity with other per-action caps in this codebase
that key off an instance id -- only ever holds at most one element now that
the target can no longer vary.)

Cost paid even if canceled (OQ-38's companion ruling, user ruling): "Action
modifiers can only be played once [per minion per action]; if [a play is]
canceled as played, another copy can be played." `apply_chosen_option`
(`engine/hooks.py`, OQ-32, resolved) already implements the generic half of
this -- "cost is still paid," effect suppressed, and a canceled attempt does
not itself trigger a once-per-action limit -- but only for a provider that
actually splits its own card-play `cost` out of `apply`. This module's
earlier draft played `play_from_hand` unconditionally inside `apply()`, the
same atomic-cost-and-effect pattern OQ-32's own review flagged (and fixed,
for Telepathic Counter) as a landmine: since `REFERENDUM_RESOLVED_HOOK` *is*
dispatched through `hooks.resolve_impulse_window` (exposed to
`CANCEL_AS_PLAYED_HOOK`), a future cancellation provider would have left the
physical card sitting back in hand, unspent, exactly the bug OQ-32 already
warned about for Organized Resistance/Protection Racket. Both clauses below
now set `HookOption.cost = play_from_hand(...)`, leaving only the blood/pool
grant and `GRANTED_KEY` bookkeeping inside `apply` -- so a canceled attempt
still discards the physical copy (cost paid) but never marks the acting
vampire as granted (limit not triggered, matching the quoted user ruling: a
second copy may still be played to the same vampire this window if the
first attempt was canceled).
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
"""Module docstring's "Per-action cap": `context["pending"]` key holding the
`set[str]` with the acting vampire's own `instance_id`, once granted either
clause this window."""


def _granted(pending: dict[str, Any]) -> set[str]:
    return pending.setdefault(GRANTED_KEY, set())


def _has_card_in_hand(state: GameState, player: str) -> bool:
    return any(card.krcg_id == KRCG_ID for card in state.players[player].hand)


def _caller_vampire(state: GameState, context: Mapping[str, Any]) -> VampireInPlay | None:
    """Module docstring's "Who may play it" (OQ-38): "this vampire" is the
    political action's own acting vampire, `context["caller_vampire_id"]`,
    never a free choice among the controller's other vampires."""
    vampire = state.players[context["caller"]].vampires.get(context["caller_vampire_id"])
    if vampire is None or vampire.zone != "ready":
        return None
    return vampire


def _provide_voter_captivation_basic(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "[pre] This vampire gains 1 blood for each vote by which the
    referendum passed." -- see module docstring for the caller-only
    eligibility gate and the `add_blood` capacity cap."""
    player = context["player"]
    if player != context["caller"]:
        return []
    if not _has_card_in_hand(state, player):
        return []
    margin = context["margin"]
    granted = _granted(context["pending"])
    target = _caller_vampire(state, context)
    if (
        target is None
        or target.instance_id in granted
        or not (BASIC in target.card.disciplines or SUPERIOR in target.card.disciplines)
    ):
        return []

    def _cost(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)

    def _apply(s: GameState, target_id: str = target.instance_id) -> None:
        vampire = s.players[player].vampires[target_id]
        add_blood(s, vampire, margin)
        granted.add(target_id)

    return [
        HookOption(
            choice=Choice(
                f"voter_captivation:basic:{target.instance_id}",
                f"Voter Captivation [pre]: {target.card.name} gains {margin} blood",
            ),
            apply=_apply,
            cost=_cost,
            played_card_type=CARD_TYPE,
        )
    ]


def _provide_voter_captivation_superior(
    state: GameState, context: Mapping[str, Any]
) -> list[HookOption]:
    """ "[PRE] As above, but move up to 2 of those blood to your pool
    instead of this vampire." -- see module docstring for the caller-only
    eligibility gate and the nested redirect-amount `Decision`."""
    player = context["player"]
    if player != context["caller"]:
        return []
    if not _has_card_in_hand(state, player):
        return []
    margin = context["margin"]
    granted = _granted(context["pending"])
    target = _caller_vampire(state, context)
    if target is None or target.instance_id in granted or SUPERIOR not in target.card.disciplines:
        return []

    def _cost(s: GameState) -> None:
        play_from_hand(s, player, KRCG_ID)

    def _apply(s: GameState, target_id: str = target.instance_id) -> int:
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

    return [
        HookOption(
            choice=Choice(
                f"voter_captivation:superior:{target.instance_id}",
                f"Voter Captivation [PRE]: {target.card.name} gains blood "
                "(move up to 2 to your pool instead)",
            ),
            apply=_apply,
            cost=_cost,
            played_card_type=CARD_TYPE,
        )
    ]


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
