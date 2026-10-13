"""Political actions and referenda: announce -> block -> polling -> tally.

Source: Rulebook SS4 Minion Phase (per the `vtes-rules-reference` skill
condensed mapping): political action is one of the default minion actions --
"political action (undirected, +1 stealth, one per vampire per turn)" -- so
it follows the same generic "announce -> block attempt -> resolve" course as
any other action (Rulebook SS4 Minion Phase, see `engine/action.py`):
announcing locks the acting vampire, the opponent gets a block attempt
(undirected: in 2P, the sole opponent, as both prey and predator -- CLAUDE.md
SS3 / `engine/action.py` module docstring), and if blocked, combat happens
and the referendum never occurs at all ("the action card is burned ... the
effects of the action do not take place", per OQ-5's verbatim rulebook
quote). `political_action` below implements exactly that much, then (once
unblocked) the referendum's polling step and vote tally, resolving OQ-6
(`docs/OPEN_QUESTIONS.md`).

OQ-6 resolution (verbatim, re-fetched by `rules-auditor` directly from
<https://www.vekn.net/rulebook/4-detailed-turn-sequence>, Politics/
Referendum subsection, cached locally at
`data/sources/rulebook/2026-10-09/4-detailed-turn-sequence.md`):

  "2. Polling: Cards that are usable 'during the polling step' but 'before
  votes and ballots are cast' are used at this time. Then, all Methuselahs
  may now cast any votes and ballots they have (see below) at this time, in
  any order. They call out their votes and ballots freely, and there is no
  obligation to cast votes or ballots. Once a vote or a ballot has been
  cast, however, it cannot be changed. [...]

  3. Resolve the Referendum: If there are more votes for the referendum than
  against, it passes, and the effects take place. Otherwise, the referendum
  fails and has no effect. Tied referendums fail."

  "Each vote or ballot cast is cast either 'for' or 'against' the
  referendum, and a Methuselah may cast some of their votes and ballots in
  favour and some against, as they choose, with the restriction that all of
  the votes and ballots from any given vampire or other source must be cast
  in agreement as a group."

  "Political Action Cards: Each Methuselah may gain 1 vote by using a
  political action card. These cards say '1 vote' to indicate this. If a
  political action card was used to call the referendum, that card provides
  1 vote for the acting vampire's controller. Other political action cards
  used for votes are simply burned without regard to the text on the cards.
  Each Methuselah can gain no more than 1 vote from political action
  cards." (re-fetched live by this pass, same URL/local cache as above --
  two independent clauses, not one: the first sentence pair is the acting
  Methuselah's own vote from the card that called the referendum (already
  implemented, below); the next sentence is a *separate* source -- a
  Methuselah, including the one who did not call the referendum, may burn a
  different political action card from their own hand during polling purely
  to gain 1 vote, with no regard to that card's own printed text. The
  acting Methuselah's calling card already supplies their one
  political-action-card vote per the clause above, so this second clause
  is, in practice, only ever a source for the *other* Methuselah -- not a
  shared 1-vote cap the caller could choose either clause to fill, since the
  caller's only political-action-card vote source is the first clause's
  automatic one. The trailing cap sentence applies per Methuselah across
  both clauses in the general case; for the caller specifically it is moot,
  since only the first clause ever applies to them.)

  "Titled Vampires: For each ready titled vampire a Methuselah controls,
  they gain extra votes. [...] A Methuselah gains: 1 vote for each ready
  primogen 2 votes for each ready prince or baron 3 votes for each ready
  justicar 4 votes for each ready Inner Circle member. [...] A minion's
  votes and ballots can be used only when the minion is ready. Whether or
  not a minion is locked or unlocked does not have any impact on their
  ability to vote." (a vampire's `zone == "ready"` is therefore the only
  gate; `VampireInPlay.locked` is irrelevant to voting, unlike to acting or
  blocking.)

  "The Edge: The Methuselah who has the Edge can burn it (return it,
  uncontrolled, to the central area) to gain 1 vote."

  A vampire in torpor "cannot cast any votes or ballots (they must
  abstain)" -- consistent with the `zone == "ready"` gate above.

The acting Methuselah's own political-action-card vote (`"If a political
action card was used to call the referendum, that card provides 1 vote for
the acting vampire's controller"`, quoted above) is modeled as an ordinary
`VoteSource`, exactly like a titled vampire's or the Edge-holder's (see
`_collect_vote_sources` below): it is offered through the same cast-or-
abstain `Decision` machinery in `_cast_votes`, and the acting Methuselah may
decline it or cast it against their own referendum, matching the verbatim
"no obligation to cast... cast either for or against" rule with no special
case.

The *other* Methuselah's own political-action-card vote ("Other political
action cards used for votes are simply burned without regard to the text on
the cards", quoted above) is modeled the same way, as an ordinary
`VoteSource` (`_collect_vote_sources` below,
`source_id` = `f"political_action_card_hand:{other_player}"`), gated purely
on "this player did not call the referendum" -- `caller_player` never gets
this source at all, not because of a shared 1-vote cap the two clauses
compete for, but because the caller's only political-action-card vote source
is their own calling card's automatic one (see the quote discussion above);
building cap-sharing logic between the two clauses for the caller's side
would be modeling a case the rules text does not actually present. The
source is only offered when `other_player` actually holds at least one
"Political Action"-type card in hand (`PlayerState.hand`, `LibraryCard.
card_type` -- both already modeled by the engine, confirmed by grep before
building this; no new data model needed, unlike OQ-7/8/9/10's "missing
representation" pattern). Casting it burns one such card from hand straight
to the ash heap (`_cast_votes`'s `burns_pac_from_hand` handling, mirroring
`burns_edge`'s zone-mutation-on-cast pattern) -- *which* card, specifically,
is never a meaningful choice (the rule is explicit the card is burned "without
regard to the text on the cards"), so no extra `Decision` is raised for it;
the engine picks the first matching card in hand order, deterministically.

`User Ruling` (OQ-6): the rules text's only textual tie between clause 1
(the calling card's automatic vote) and clause 2 (burning a different
political-action card from hand) is the shared cap sentence ("Each
Methuselah can gain no more than 1 vote from political action cards"), not
an explicit "the caller may only ever use clause 1" statement -- leaving
open whether a caller who *declines* their clause-1 vote (legal -- "no
obligation to cast") could then use clause 2 instead, still capped at 1
total. Settled by the project's user: **no** -- the calling card consumes
the Methuselah's one political-action-card-vote slot the moment it is used
to call the referendum, independent of whether the automatic vote it
grants is subsequently cast or declined; the vote and the slot are not the
same event. This confirms the existing code (gating `political_action_card_
hand:{other_player}` to `other_player` only, never `caller_player`) is
correct as-is. See `docs/OPEN_QUESTIONS.md` OQ-6's addendum and `tests/
rules/test_politics.py::
test_the_calling_methuselah_is_never_offered_the_burn_from_hand_political_
action_card_source`.

Polling-step hook wiring (`POLLING_STEP_HOOK`, `cards/registry.py::
Hook.POLLING_STEP`): "Cards that are usable 'during the polling step' but
'before votes and ballots are cast' are used at this time" names a window
*before* casting begins, separate from casting itself -- `_run_pre_cast_hook_
window` below dispatches it as a two-sided impulse window (CLAUDE.md rule 4
/ Rulebook SS2 Sequencing, `hooks.resolve_impulse_window`), exactly like
every other hook-gated window in this engine. Two of this pool's own
(currently `blocked`, OQ-6) cards need exactly this shape:
  (a) Perfect Paragon ("[pre] ... This vampire gets +3 votes.") -- a
      provider appends a new vote-source descriptor
      (`{"source_id", "player", "votes", "label"}`) to
      `pending["extra_sources"]`.
  (b) Queen Anne ("... she can burn 1 blood to force a younger Camarilla
      vampire to abstain.") -- a provider adds the target source's
      `source_id` (format: see `_collect_vote_sources`) to
      `pending["forced_abstain"]`.
Both mutate the same `pending` dict threaded into the hook's own context
(mirrors `engine/phases/minion.py::_perform_bleed`'s `amount_box`/`pending`
pattern for `BLEED_AMOUNT_MODIFIER_HOOK`); `HookOption.apply(state)` returns
`None` for both (an effect hook, per `engine/hooks.py::HookOption`'s own
convention), since the actual data is written to `pending` via closure, not
via the return value.

A third shape, Marcos Belegrad's "Methuselahs casting [...] votes or ballots
against a referendum called by Marcos burn 1 pool once results are
tallied," needs a *mandatory*, non-chosen reaction dispatched *after* the
tally is known, which fits neither `HookOption`/`Decision` (nothing for a
player to choose) nor `hooks.sum_modifiers`/`union_modifiers` (both
aggregate a *value* a caller then applies itself). `hooks.run_effects`
(`engine/hooks.py`, added for exactly this case) fills that gap: a plain
`Callable[[GameState, Mapping], None]` provider that may mutate `state`
directly, with no return value consumed. `resolve_referendum` now dispatches
`REFERENDUM_TALLIED_HOOK` (`cards/registry.py::Hook.REFERENDUM_TALLIED`)
through it, immediately after `_cast_votes` returns and before the
`(votes_for, votes_against, casts)` tuple is handed back to `political_
action` -- i.e. before any pass/fail effect of the referendum itself takes
place, matching the card's own "once results are tallied" timing. No
provider is registered against this hook yet (no card module targets it in
this pass), so `hooks.run_effects` is a no-op today and this dispatch
changes no behaviour -- it only makes Marcos Belegrad's own reaction
buildable by a future `card-implementer` pass, which has everything it
needs in `context["casts"]` (who cast against, and how many votes) without
re-deriving it. This is a materially *earlier* moment than Voter
Captivation's own trigger, which needs the referendum's pass/fail outcome
(and any pass effects, and any combat from a blocked attempt) already
settled -- `cards/registry.py::Hook.REFERENDUM_RESOLVED` is reserved for
that later moment but has no dispatch call site yet (no card in this pass
needs one built; see `voter_captivation.py`'s own docstring).

`resolve_referendum` threads the identity of `caller_vampire`, the
`VampireInPlay` instance that announced the political action (not just
`caller_player`'s id), into both hook contexts it builds -- needed by any
card whose own trigger names a *specific* titled vampire's referendum rather
than any referendum its controller happens to call (e.g. Queen Anne's "a
referendum called by Anne" or Marcos Belegrad's "a referendum called by
Marcos": a Methuselah could control both Marcos and some other titled
vampire, and only Marcos's own referenda should trigger his ability). The
two hook contexts carry this identity differently, by design, not by
oversight:

- `_dispatch_referendum_tallied`'s `REFERENDUM_TALLIED_HOOK` context (fired
  via `hooks.run_effects`, never surfaced as a `Decision`, read only by
  trusted provider code already running with the live `state` in hand --
  the same architectural tier as `sum_modifiers`/`union_modifiers`
  providers elsewhere) carries the live `caller_vampire` object itself
  (`context["caller_vampire"]`). A provider checks it against its own
  tracked instance (by identity or `krcg_id`) rather than only
  `context["caller"]`/`context["other"]`, which only identify controllers.
- `_run_pre_cast_hook_window`'s `POLLING_STEP_HOOK` context is different in
  kind: it is dispatched through `hooks.resolve_impulse_window`, which
  raises a real `Decision` whenever a provider offers an option, and
  `Decision.context` is handed straight to `agent.decide(observation,
  decision)` -- i.e. to agent-visible code, not just trusted engine-internal
  provider code (CLAUDE.md "Information hiding": agents receive an
  `Observation`, never the raw, mutable `GameState` graph). Putting the live
  `VampireInPlay` object there would leak a mutable reference into the same
  object graph `Observation` is built specifically to hide (`rules-auditor`
  finding; reproduced live with a fake `POLLING_STEP_HOOK` provider and a
  real `Decision`). So this context instead carries
  `context["caller_vampire_id"]`, the plain `str` `caller_vampire.
  instance_id` -- the same convention every other hook/decision context in
  this engine already uses to reference a vampire without handing out the
  object itself (`engine/contests.py`'s `"vampire"` key, `engine/combat.py`'s
  `"vampire"`/`"opponent"` keys, `engine/damage.py`'s `"vampire"` key -- all
  instance ids, never the `VampireInPlay`). A provider that needs the actual
  instance looks it up from `state` via that id (`state.players[player].
  vampires[instance_id]`, or a small lookup helper), exactly like every other
  hook provider in the engine already does; none does today (no card module
  registers against `POLLING_STEP_HOOK` yet).

A fourth `POLLING_STEP_HOOK` shape, found implementing OQ-23 (`docs/
OPEN_QUESTIONS.md`): Oxford University, England ("Unique location. You can
lock this card and burn X pool during the polling step of a political
action to get +2X votes.") needs an `HookOption` *per legal X*, not a single
fixed-vote option like Perfect Paragon's -- the controller picks how much
pool to burn, and the vote count scales with that choice. This does not need
a new kind of engine-level window (each `HookOption` already becomes one
choice of the same `POLLING_STEP_HOOK` `Decision` `resolve_impulse_window`
already raises; a provider offering several `HookOption`s for the same
ability, each for a different X, already works today with no change here),
but the enumerate-X/burn-X-pool/append-to-`pending["extra_sources"]`
bookkeeping would otherwise be duplicated by every future card with this
same "burn X pool for Y*X votes" shape (The Barrens and Chantry, both
already in the pool and unimplemented, print unrelated "lock this card to
<fixed effect>" abilities with no variable X, so they do not need this
helper -- but nothing rules out a future card reusing exactly this shape).
`variable_pool_burn_vote_options` below is that reusable primitive: a
`POLLING_STEP_HOOK` provider calls it from inside its own `offer()`
implementation and returns what it gives back (optionally chained with its
own, unrelated `HookOption`s, e.g. for a card with more than one ability).
X = 0 is deliberately never offered (burning 0 pool for 0 votes is not a
meaningful choice, CLAUDE.md "only when needed"); the upper bound is
`player`'s current pool (a Methuselah cannot burn more pool than they have).

Vote/ballot *casting order* for exactly two Methuselahs was an open question
(`docs/OPEN_QUESTIONS.md` OQ-20, now resolved): the quoted rule above only
says casting happens "in any order," with no turn structure specified by the
rulebook itself. `User Ruling` (OQ-20, settled by the project's user from
real-table play experience): votes are cast in table order (seating order)
-- each Methuselah decides, on their turn in that fixed rotation, which
vampire(s)/source(s) contribute votes for/against, or passes, and the table
goes around for a second and (if needed) third lap, continuing until a full
lap completes with nobody casting anything. In this 2P engine that is
strict alternation, `caller_player` first each lap (they called the
referendum) then `other_player`, repeating laps until one full lap passes
with no casts from either side -- not the impulse-returns-to-the-acting-
player model used elsewhere in this engine, which would give the caller an
unsourced tactical edge (casting every one of their own sources back-to-back
before the other Methuselah gets a look). `_cast_votes` below implements
exactly that; see its own docstring for the loop's mechanics.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import hooks
from .action import ACTION_POLITICAL, attempt_block
from .combat import run_combat
from .decision import Choice, Decision
from .hooks import HookOption
from .pool import lose_pool

if TYPE_CHECKING:
    from .state import GameState, VampireInPlay

POLITICAL_ACTION_STEALTH = 1
"""Rulebook SS4 Minion Phase default action list: political action baseline stealth +1."""

POLLING_STEP_HOOK = "polling_step"
"""String value matches `cards/registry.py::Hook.POLLING_STEP` ("polling_step");
engine modules never import `cards/registry.py` (CLAUDE.md SS5/SS6: cards
depend on the engine, not the reverse), so the hook name is a plain string
constant here, the same convention `action.py`'s `STEALTH_MODIFIER_HOOK` and
`phases/master.py`'s `MASTER_PHASE_PLAY_HOOK` already use."""

REFERENDUM_TALLIED_HOOK = "referendum_tallied"
"""String value matches `cards/registry.py::Hook.REFERENDUM_TALLIED`. Fired
via `hooks.run_effects` (not `offer`/`resolve_impulse_window`: there is
nothing for a player to choose here, see module docstring) once
`resolve_referendum`'s tally is known, before its pass/fail effects take
place -- the hook site Marcos Belegrad's mandatory "burn 1 pool" reaction
needs (OQ-6)."""

POLITICAL_ACTION_CARD_TYPE = "Political Action"
"""`LibraryCard.card_type` value for a political action card (confirmed
against real 2P suggested-deck data, `data/decks/vekn-2p/*.json`, which all
use this exact string, e.g. `"type": "Political Action"` for Disputed
Territory/Kine Resources Contested/Parity Shift) -- used by
`_has_political_action_card_in_hand` to find clause 2's burn-from-hand
source (module docstring, "Political Action Cards")."""

TITLE_VOTES: dict[str, int] = {
    "Primogen": 1,
    "Prince": 2,
    "Baron": 2,
    "Justicar": 3,
    "Inner Circle": 4,
}
"""Rulebook SS4 Politics > Gaining Votes > Titled Vampires, verbatim: "A
Methuselah gains: 1 vote for each ready primogen 2 votes for each ready
prince or baron 3 votes for each ready justicar 4 votes for each ready Inner
Circle member." Keys match `CryptCard.title`'s expected plain-text
convention (the capitalized title keyword as it appears in the vampire's own
printed text, e.g. "Camarilla Prince of London" -> `title="Prince"`), the
same convention already used for sect preambles by `engine/cards.py::
derive_sect`. Sabbat and other-sect titles (Rulebook SS6-7) are
intentionally absent: this pool has no Sabbat cards (per this task's own
scoping), so no reading of their title->vote values has been sourced; a
`CryptCard.title` not present as a key here simply contributes 0 votes
(not an error -- most vampires have no title at all, `title=None`, which
also simply is not a key here)."""


@dataclass
class VoteSource:
    """One source of votes/ballots a specific Methuselah may cast, as a
    group, "for" or "against" a referendum (Rulebook SS4 Politics > Gaining
    Votes, see module docstring) -- never split across directions.

    `source_id` format is part of this module's public contract for
    `POLLING_STEP_HOOK` providers targeting an existing source (e.g. Queen
    Anne's forced-abstain clause): `f"political_action_card:{caller_player}"`
    for the acting Methuselah's own (calling-card) political-action-card
    vote, `f"political_action_card_hand:{other_player}"` for the *other*
    Methuselah's own (burn-from-hand) political-action-card vote (module
    docstring, "Political Action Cards" clause 2), `f"title:{vampire.
    instance_id}"` for a titled ready vampire, `f"edge:{player}"` for the
    Edge-burn source, or whatever a `POLLING_STEP_HOOK` provider itself
    picks for a source it adds via `pending["extra_sources"]` (e.g. a
    per-vampire id so a second provider could target it in turn).
    """

    source_id: str
    player: str
    votes: int
    label: str
    burns_edge: bool = False
    burns_pac_from_hand: bool = False
    """When cast, burn one "Political Action"-type `LibraryCard` from
    `player`'s hand to the ash heap (module docstring, "Other political
    action cards used for votes are simply burned without regard to the
    text on the cards") -- mirrors `burns_edge`'s cast-time state mutation."""


def variable_pool_burn_vote_options(
    state: GameState,
    player: str,
    *,
    source_id_prefix: str,
    label: str,
    votes_per_pool: int,
    pending: dict[str, Any],
    on_burn: Callable[[GameState], None] | None = None,
) -> list[HookOption]:
    """Build one `POLLING_STEP_HOOK` `HookOption` per legal pool-burn amount
    X (1..`player`'s current pool) for a "burn X pool during the polling
    step of a political action to get <votes_per_pool>*X votes" ability
    (module docstring, "A fourth `POLLING_STEP_HOOK` shape" -- Oxford
    University, England, OQ-23 `docs/OPEN_QUESTIONS.md`: "You can lock this
    card and burn X pool during the polling step of a political action to
    get +2X votes").

    `HookOption.played_card_type` is deliberately left at its default
    `None` on every option this builds (`docs/OPEN_QUESTIONS.md` OQ-33,
    resolved): every known caller (Oxford University, England) is a Master
    card's own already-in-play, repeatable ability, never a fresh card play
    -- see `played_card_type`'s own docstring, `engine/hooks.py`. A future
    caller whose own "burn X pool for votes" clause is instead the moment a
    *new* physical card is played must not reuse this helper as-is without
    re-checking that assumption.

    Choosing the X-pool option burns that much pool from `player`
    (`engine/pool.py::lose_pool`), then runs `on_burn(state)` if given --
    for Oxford's own shape, this is where a future card module locks the
    source card itself (`MasterCardInPlay.locked = True`), kept as a
    caller-supplied callback rather than built in here, since locking is
    specific to *this* ability's own cost, not a universal part of the
    "burn X pool for Y*X votes" shape -- then appends a `{"source_id",
    "player", "votes", "label"}` descriptor to `pending["extra_sources"]`
    (module docstring, Perfect Paragon shape) with `votes = votes_per_pool *
    X`. `source_id_prefix` must be unique per ability instance (e.g. a
    specific `MasterCardInPlay.instance_id`) so two simultaneous instances
    of this shape in the same game -- e.g. a contested-and-resolved pair of
    the same unique card, or two different "burn X pool for votes" cards --
    never collide on `pending["extra_sources"]` source ids; each X gets its
    own `f"{source_id_prefix}:{x}"`.

    X = 0 is deliberately never offered: burning 0 pool for 0 votes is a
    no-op, not a meaningful choice (CLAUDE.md "only when needed" -- no
    vacuous option). Capped at `player`'s current pool (a Methuselah cannot
    burn pool they do not have); if `player` has 0 pool, this returns an
    empty list.
    """
    pool = state.players[player].pool
    options: list[HookOption] = []
    for x in range(1, pool + 1):
        votes = votes_per_pool * x

        def _apply(s: GameState, x: int = x, votes: int = votes) -> None:
            lose_pool(s, player, x)
            if on_burn is not None:
                on_burn(s)
            pending["extra_sources"].append(
                {
                    "source_id": f"{source_id_prefix}:{x}",
                    "player": player,
                    "votes": votes,
                    "label": f"{label} (burn {x} pool for {votes} votes)",
                }
            )

        options.append(
            HookOption(
                choice=Choice(
                    f"{source_id_prefix}:{x}",
                    f"{label}: burn {x} pool for {votes} votes",
                ),
                apply=_apply,
            )
        )
    return options


def political_action(
    state: GameState,
    actor_player: str,
    vampire: VampireInPlay,
) -> bool | None:
    """Announce (lock) -> block attempt -> (blocked: combat) | (unblocked: referendum).

    Returns `None` if the action was blocked (no referendum ever occurs,
    per OQ-5's verbatim rulebook quote in the module docstring); otherwise
    returns the referendum's pass/fail result from `resolve_referendum`
    (`True` = passes, `False` = fails). "Terms chosen only after success"
    (Rulebook SS4 "The Political Action") is left to the caller (a future
    political-action card module): this function only resolves whether the
    referendum passes, not what a passing referendum's terms do.
    """
    defender_player = state.other_player(actor_player)
    vampire.locked = True
    blocker = attempt_block(
        state,
        actor_player,
        defender_player,
        POLITICAL_ACTION_STEALTH,
        vampire,
        action=ACTION_POLITICAL,
    )
    if blocker is not None:
        blocker.locked = True
        run_combat(state, actor_player, vampire, defender_player, blocker)
        return None
    votes_for, votes_against, _casts = resolve_referendum(
        state, actor_player, defender_player, vampire
    )
    return votes_for > votes_against


def resolve_referendum(
    state: GameState,
    caller_player: str,
    other_player: str,
    caller_vampire: VampireInPlay,
) -> tuple[int, int, list[tuple[str, str, int, str]]]:
    """Run an unblocked referendum's polling step and tally (Rulebook SS4
    "The Referendum", steps 2-3 -- see module docstring for the verbatim
    quotes this resolves, OQ-6).

    Returns `(votes_for, votes_against, casts)`: the final tally, and a log
    of every vote actually cast as `(player, source_id, votes, direction)`
    tuples (`direction` is `"for"` or `"against"`) -- including the acting
    Methuselah's own political-action-card vote whenever it was actually
    cast (it is now an ordinary, optional `VoteSource`, see module
    docstring, so it may be absent from this log if declined). This is
    exposed (not just the bool) so a hook built on top of it (e.g. Marcos
    Belegrad's after-tally reaction, `REFERENDUM_TALLIED_HOOK` below) has
    everything it needs without re-deriving it.

    `caller_player` is "the Methuselah who calls the referendum" throughout
    the quoted rules text; `caller_vampire` is the specific `VampireInPlay`
    that announced the political action -- threaded through so a provider
    can distinguish "a referendum called by *this specific titled vampire*"
    (e.g. Queen Anne, Marcos Belegrad) from "any referendum called by this
    vampire's controller" (see module docstring). `political_action` is this
    function's only caller today, always passing the acting Methuselah and
    vampire.
    """
    pending: dict[str, Any] = {"extra_sources": [], "forced_abstain": set()}
    _run_pre_cast_hook_window(state, caller_player, other_player, caller_vampire, pending)
    sources = _collect_vote_sources(state, caller_player, other_player, pending)
    votes_for, votes_against, casts = _cast_votes(state, caller_player, other_player, sources)
    _dispatch_referendum_tallied(
        state, caller_player, other_player, caller_vampire, votes_for, votes_against, casts
    )
    return votes_for, votes_against, casts


def _run_pre_cast_hook_window(
    state: GameState,
    caller_player: str,
    other_player: str,
    caller_vampire: VampireInPlay,
    pending: dict[str, Any],
) -> None:
    """Rulebook SS4 "The Referendum", step 2: "Cards that are usable 'during
    the polling step' but 'before votes and ballots are cast' are used at
    this time" -- before casting begins, dispatched as the engine's
    standard two-sided impulse window (CLAUDE.md rule 4, `hooks.
    resolve_impulse_window`). With no `POLLING_STEP_HOOK` providers
    registered (no card in this pass registers against it yet), `hooks.
    offer` returns an empty list for both players and this closes
    immediately, raising no `Decision` at all (the project's "only when
    needed" invariant) -- see module docstring for the two provider shapes
    this window is built to support.

    `context["caller_vampire_id"]` is a plain `str` (`caller_vampire.
    instance_id`), not the live `VampireInPlay` -- `resolve_impulse_window`
    may raise a real `Decision` here, and `Decision.context` reaches
    agent-visible code (`GameState.ask` -> `Agent.decide`), so nothing from
    the live, mutable `GameState` object graph may be put in it (CLAUDE.md
    "Information hiding"; module docstring). See module docstring for why
    this differs from `_dispatch_referendum_tallied`'s context, which does
    carry the live object.
    """
    hooks.resolve_impulse_window(
        state,
        POLLING_STEP_HOOK,
        caller_player,
        other_player,
        context={
            "caller": caller_player,
            "caller_vampire_id": caller_vampire.instance_id,
            "phase": "before_cast",
            "pending": pending,
        },
    )


def _dispatch_referendum_tallied(
    state: GameState,
    caller_player: str,
    other_player: str,
    caller_vampire: VampireInPlay,
    votes_for: int,
    votes_against: int,
    casts: list[tuple[str, str, int, str]],
) -> None:
    """Rulebook SS4 "The Referendum", step 3: a mandatory, non-chosen
    per-provider reaction fired once results are tallied -- before the
    referendum's own pass/fail effects take place, see module docstring.
    No `Decision` is raised (`hooks.run_effects`, not `offer`): there is
    nothing for a player to choose, only a provider mutating `state`
    directly (e.g. Marcos Belegrad's mandatory pool loss, OQ-6). No
    provider is registered against `REFERENDUM_TALLIED_HOOK` yet, so this
    call is a no-op today.
    """
    hooks.run_effects(
        REFERENDUM_TALLIED_HOOK,
        state,
        caller=caller_player,
        other=other_player,
        caller_vampire=caller_vampire,
        votes_for=votes_for,
        votes_against=votes_against,
        casts=casts,
    )


def _collect_vote_sources(
    state: GameState,
    caller_player: str,
    other_player: str,
    pending: dict[str, Any],
) -> list[VoteSource]:
    """Enumerate every vote source either Methuselah may cast this polling
    step (Rulebook SS4 Politics > Gaining Votes, see module docstring): the
    acting Methuselah's own 1-vote political-action-card source (clause 1),
    the other Methuselah's own 1-vote burn-a-political-action-card-from-hand
    source (clause 2, gated on actually holding one), titled ready vampires,
    the Edge (if held), and whatever a `POLLING_STEP_HOOK` provider added to
    `pending["extra_sources"]` -- minus any `pending["forced_abstain"]`
    source ids."""
    forced_abstain: set[str] = pending.get("forced_abstain", set())
    sources: list[VoteSource] = []
    pac_source_id = f"political_action_card:{caller_player}"
    if pac_source_id not in forced_abstain:
        sources.append(
            VoteSource(
                source_id=pac_source_id,
                player=caller_player,
                votes=1,
                label="Political action card",
            )
        )
    pac_hand_source_id = f"political_action_card_hand:{other_player}"
    if pac_hand_source_id not in forced_abstain and _has_political_action_card_in_hand(
        state, other_player
    ):
        sources.append(
            VoteSource(
                source_id=pac_hand_source_id,
                player=other_player,
                votes=1,
                label="Burn a political action card from hand",
                burns_pac_from_hand=True,
            )
        )
    for player in (caller_player, other_player):
        for vampire in state.players[player].vampires.values():
            if vampire.zone != "ready":
                continue  # torpor "must abstain" (module docstring); locked is irrelevant.
            title = vampire.card.title
            if title not in TITLE_VOTES:
                continue
            source_id = f"title:{vampire.instance_id}"
            if source_id in forced_abstain:
                continue
            sources.append(
                VoteSource(
                    source_id=source_id,
                    player=player,
                    votes=TITLE_VOTES[title],
                    label=f"{vampire.card.name} ({title})",
                )
            )
    if state.edge_holder is not None:
        source_id = f"edge:{state.edge_holder}"
        if source_id not in forced_abstain:
            sources.append(
                VoteSource(
                    source_id=source_id,
                    player=state.edge_holder,
                    votes=1,
                    label="Burn the Edge",
                    burns_edge=True,
                )
            )
    for extra in pending.get("extra_sources", ()):
        source_id = extra["source_id"]
        if source_id in forced_abstain:
            continue
        sources.append(
            VoteSource(
                source_id=source_id,
                player=extra["player"],
                votes=extra["votes"],
                label=extra["label"],
            )
        )
    return sources


def _has_political_action_card_in_hand(state: GameState, player: str) -> bool:
    """Clause 2 gate (module docstring, "Political Action Cards"): does
    `player` hold at least one `"Political Action"`-type `LibraryCard` in
    hand right now? Which specific card is irrelevant (the rule burns it
    "without regard to the text on the cards"), so only presence matters
    here; `_burn_one_political_action_card_from_hand` does the actual
    removal once a `VoteSource` with `burns_pac_from_hand=True` is cast.
    """
    return any(card.card_type == POLITICAL_ACTION_CARD_TYPE for card in state.players[player].hand)


def _burn_one_political_action_card_from_hand(state: GameState, player: str) -> None:
    """Cast-time effect of a `burns_pac_from_hand` `VoteSource` (module
    docstring): move exactly one `"Political Action"`-type `LibraryCard` from
    `player`'s hand to their ash heap. Which card, specifically, is never a
    meaningful choice (same rule text as `_has_political_action_card_in_hand`
    above), so no `Decision` is raised; the first match in hand order is
    burned, deterministically. `_collect_vote_sources` only ever offers this
    source when at least one such card is present, so the hand is not
    expected to have lost it between collection and casting (no provider in
    this pool removes hand cards during the pre-cast window) -- if it
    somehow has, that is an engine invariant violation, not a legal game
    state, hence the assertion rather than a silent no-op.
    """
    hand = state.players[player].hand
    for index, card in enumerate(hand):
        if card.card_type == POLITICAL_ACTION_CARD_TYPE:
            state.players[player].ash_heap.append(hand.pop(index))
            return
    raise AssertionError(
        f"{player} has no political action card left in hand to burn for a vote "
        "(engine invariant violation, not a legal game state)"
    )


def _cast_votes(
    state: GameState,
    caller_player: str,
    other_player: str,
    sources: list[VoteSource],
) -> tuple[int, int, list[tuple[str, str, int, str]]]:
    """Rulebook SS4 "The Referendum", step 2 casting + step 3 tally: "all
    Methuselahs may now cast any votes and ballots they have [...] in any
    order [...] there is no obligation to cast"; "all of the votes and
    ballots from any given vampire or other source must be cast in
    agreement as a group" (so each `VoteSource` is offered as one
    for/against/hold-back unit, never split); "[i]f there are more votes for
    the referendum than against, it passes [...] Tied referendums fail."

    Casting order for exactly two Methuselahs: `User Ruling` (OQ-20, see
    module docstring for the full ruling) -- table-order lapping collapses,
    for two players, to strict alternation with the caller going first each
    lap.

    Implemented as strict two-player alternation: `turn` flips between
    `caller_player` and `other_player` after *every* step, whether that step
    was a cast or a pass/no-sources-available skip -- unlike the project's
    former interim placeholder, the impulse never "returns to" whichever
    player just acted. Each player's own turn offers every `VoteSource` they
    still control, as one `Decision` (a player may cast at most one source
    per turn; casting a second source of theirs requires waiting for a full
    extra lap, exactly matching "repeat laps" above -- within a lap, each
    side gets exactly one opportunity, same as going around a table once).
    `consecutive_passes` counts consecutive turns (by either player) with no
    cast; because `turn` always alternates, any two consecutive turns are
    always one from each player, i.e. exactly one full lap -- so
    `consecutive_passes reaching 2` is precisely "a full lap completes with
    nobody casting anything," the quoted closing condition, regardless of
    which player the count happens to start on. A cast resets the counter to
    0, so a fresh full lap (both players, in order) is required to close the
    window after any cast. The loop also ends immediately once `remaining`
    is empty (no sources left for anyone to cast), without waiting out a
    final idle lap.
    """
    votes_for = 0
    votes_against = 0
    casts: list[tuple[str, str, int, str]] = []

    remaining = {source.source_id: source for source in sources}
    turn = caller_player
    consecutive_passes = 0
    while remaining and consecutive_passes < 2:
        mine = sorted(
            (source for source in remaining.values() if source.player == turn),
            key=lambda source: source.source_id,
        )
        if not mine:
            consecutive_passes += 1
        else:
            choices: tuple[Choice, ...] = ()
            for source in mine:
                choices += (
                    Choice(
                        f"for:{source.source_id}",
                        f"Cast {source.votes} vote(s) for ({source.label})",
                    ),
                    Choice(
                        f"against:{source.source_id}",
                        f"Cast {source.votes} vote(s) against ({source.label})",
                    ),
                )
            choices += (Choice("pass", "Pass (hold back remaining votes for now)"),)
            decision = Decision(
                player=turn,
                kind="polling_step_cast",
                choices=choices,
                context={
                    "caller": caller_player,
                    "votes_for": votes_for,
                    "votes_against": votes_against,
                },
            )
            answer = state.ask(decision).value
            if answer == "pass":
                consecutive_passes += 1
            else:
                consecutive_passes = 0
                direction, source_id = answer.split(":", 1)
                source = remaining.pop(source_id)
                if source.burns_edge:
                    state.edge_holder = None
                if source.burns_pac_from_hand:
                    _burn_one_political_action_card_from_hand(state, source.player)
                if direction == "for":
                    votes_for += source.votes
                else:
                    votes_against += source.votes
                casts.append((source.player, source.source_id, source.votes, direction))
        turn = other_player if turn == caller_player else caller_player
    return votes_for, votes_against, casts
