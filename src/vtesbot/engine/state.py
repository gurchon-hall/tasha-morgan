"""Game state: the single source of truth, plus the `ask()` decision gateway.

Pure core (CLAUDE.md SS5): no I/O, no printing, no network. All randomness
goes through `GameState.rng`. `GameState.ask` is the only way engine code
may obtain a player's choice; it builds the restricted `Observation`, calls
the player's `Agent`, and rejects any answer not in `decision.choices`
(CLAUDE.md "legality by construction").
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .agent import Agent
from .cards import CardAttachment, CryptCard, LibraryCard
from .errors import GameOverError, IllegalChoiceError
from .format import FormatConfig
from .log import ReplayLog
from .observation import build_observation
from .rng import GameRNG

if TYPE_CHECKING:
    from .decision import Choice, Decision

Zone = str  # "uncontrolled" | "ready" | "torpor" | "burned" | "removed_from_game"


@dataclass
class VampireInPlay:
    """One controlled vampire instance (a dealt/drawn crypt card in a player's crypt area).

    `zone == "removed_from_game"` (OQ-24, `docs/OPEN_QUESTIONS.md`): a crypt
    card physically removed from the game by an effect (e.g. Wider View,
    krcg id 102180, "...remove a crypt card in your uncontrolled region from
    the game") -- deliberately a distinct value from `"burned"`, not reused
    for it, because the general ruling on file for that exact clause ("Cards
    removed from the game are public." [LSJ 20080314]) only matters, and
    only needed stating at all, for a card that may still be face-down and
    unrevealed (`"uncontrolled"`) at the moment it is removed: a `"burned"`
    vampire is always already-revealed (torpor/diablerie/contest-yield), so
    its own public status was never in question the way a still-secret
    uncontrolled card's is. No `Observation` change is needed to honour this
    ruling: `build_observation`'s own `visible_identity = v.zone !=
    "uncontrolled" or v.controller == viewer` already treats every zone
    other than `"uncontrolled"` (this one included) as fully public to both
    players, exactly like `"burned"` already is -- confirmed by reading that
    function, not assumed."""

    instance_id: str
    card: CryptCard
    controller: str
    blood: int = 0
    zone: Zone = "uncontrolled"
    locked: bool = False
    wounded: bool = False
    contested_with: str | None = None  # instance_id of the opposing copy, if 2P-contested
    attachments: list[CardAttachment] = field(default_factory=list)
    """Cards physically on this vampire (discipline/archetype master cards,
    equipment, retainers -- CLAUDE.md SS5/SS6 "equipment"/"retainer" hook
    categories; see `engine/cards.py::CardAttachment`)."""
    ability_used_turn: dict[str, int] = field(default_factory=dict)
    """Generic "once per X" scratch for a printed ability capped by Rulebook
    SS3 "Wording templates" > "During X, do Y" ("only one Y can be done per
    X with this card") when X is a whole turn -- e.g. Maila (krcg id 201633,
    `src/vtesbot/cards/maila.py`), "If Maila is ready during your turn, you
    can discard a political action card to give a minion you control +1
    stealth for the current action," capped "once during each of your
    turns" [RBK wording-templates] [ANK 20230122]. Keyed by a provider-chosen
    string (e.g. `"maila_discard_for_stealth"`), storing the
    `GameState.turn_number` the ability was last used on; a provider checks
    `vampire.ability_used_turn.get(key) == state.turn_number`. Neither of the
    engine's two existing scratch containers is turn-scoped: `pending`
    (`engine/action.py::perform_minion_action`) spans one *action*, and
    `apply_chosen_option`'s `cancel_context["pending"]` spans one
    *referendum* -- so this is a new, minimal, generic field, not a
    repurposing of either. Default-valued like every other field here
    (`blood`/`zone`/`locked`/`wounded`/`contested_with`); adding it changes
    no existing behaviour."""
    woken: bool = False
    """Transient, action-scoped eligibility override (OQ-46, `docs/
    OPEN_QUESTIONS.md`, resolved -- Reading A): On the Qui Vive (krcg id
    101321), "This minion wakes (they ignore the requirement to be unlocked
    for playing reaction cards and attempting to block until the end of the
    action)." While `True`, `is_ready_unlocked` below reports `True` even
    though `locked` stays `True` -- "while remaining structurally locked"
    per that card's own module docstring -- so this vampire is offered as an
    ordinary block candidate (`ready_unlocked_vampires`, `engine/action.py::
    attempt_block`) and passes every existing reaction-card provider's own
    hardcoded `vampire.is_ready_unlocked` eligibility check (`cards/
    telepathic_counter.py`, `cards/protection_racket.py`, `cards/
    scalpel_tongue.py`, ...), with no per-card change needed. Cleared
    unconditionally for every vampire of both players at every exit point of
    one minion action (`engine/action.py::clear_woken_vampires`, called from
    `perform_minion_action`) -- "until the end of the action" (the
    vampire that played On the Qui Vive is always the *non*-acting
    Methuselah's own, per the general Reaction-card rule this card's own
    "Only usable by a locked minion" clause only relaxes the lock
    requirement of, never the "other than the acting Methuselah" one; see
    that card's own module docstring)."""

    qui_vive_played_since_unlock: bool = False
    """Per-vampire cap for On the Qui Vive's (krcg id 101321) own second
    sentence: "A minion can play only one On the Qui Vive between their
    unlock phases" -- a window strictly wider than one action (unlike
    `woken` above, cleared at the end of the action that triggered it) and
    not aligned to `GameState.turn_number` either (this card is a Reaction,
    almost always played on the *other* Methuselah's turn, so the window
    spans that whole intervening turn plus whatever is left of this
    vampire's controller's own) -- `ability_used_turn`'s "store the turn
    number, compare for equality" convention does not fit a multi-turn
    window, so this is instead a plain one-shot flag. Set `True` by `cards/
    on_the_qui_vive.py`'s own provider; cleared back to `False`
    unconditionally for every vampire (any zone) by `engine/phases/
    unlock.py::_unlock_own_vampires`, once per this vampire's controller's
    own unlock phase -- the literal "between their unlock phases"
    boundary."""

    @property
    def is_ready_unlocked(self) -> bool:
        return self.zone == "ready" and (not self.locked or self.woken)


@dataclass
class AllyInPlay:
    """One controlled ally instance (OQ-7, `docs/OPEN_QUESTIONS.md`; Rulebook
    SS4 "Recruit Ally").

    Mirrors `VampireInPlay`'s shape: `zone` takes the three values
    `engine/allies.py` and `engine/phases/unlock.py` need -- `"ready"`
    (played face up, usable), `"burned"` (removed from play) and
    `"contested"` (Rulebook SS4 Advanced Rules > Contested Cards, OQ-10) --
    and `locked`/`is_ready_unlocked` follow the same "ready and not locked"
    convention as a vampire's.
    """

    instance_id: str
    krcg_id: int
    name: str
    controller: str
    life: int
    strength: int = 0
    bleed: int = 0
    zone: str = "ready"
    locked: bool = False
    contested_with: str | None = None  # instance_id of the opposing copy, if contested
    skip_next_unlock: bool = False
    """One-shot override consumed by `engine/phases/unlock.py::
    _unlock_own_allies`'s own unconditional unlock step (OQ-46, `docs/
    OPEN_QUESTIONS.md`, resolved): On the Qui Vive's own ally footnote, "If
    this minion is an ally, they do not unlock as normal during their next
    unlock phase." Distinct from `VampireInPlay.woken` above (which is
    cleared at the end of the *current* action) -- this flag instead reaches
    forward to this ally's own *next* unlock phase specifically, independent
    of whatever `woken` is doing meanwhile. Set `True` by a future On the
    Qui Vive provider's own `apply` when the playing minion is an ally;
    `_unlock_own_allies` consumes it (skips that one unlock, then resets it
    to `False`) rather than leaving it set forever."""

    @property
    def is_ready_unlocked(self) -> bool:
        return self.zone == "ready" and not self.locked


@dataclass
class MasterCardInPlay:
    """One controlled standalone Master card in play -- i.e. a Master-type
    library card whose own printed text is not an attachment (contrast
    `CardAttachment`, "put this card on a vampire") but instead keeps the
    card itself in a player's own play area, persisting across turns (OQ-23,
    `docs/OPEN_QUESTIONS.md`).

    krcg has no `Type.LOCATION` at all -- "Unique location." (e.g. Oxford
    University, England, "You can lock this card and burn X pool during the
    polling step of a political action to get +2X votes.") is free text on
    an ordinary `Master`-type card, no different in kind from "Unique." or
    "Trifle." on any other Master card. The real, broader gap is a
    standalone Master card in play *at all*, Unique or not -- found to cover
    at least 18 Master-type library cards in the active 2P allowed list
    (`data/formats/2p/2026-10-03.json`) whose own printed text keeps the
    card itself in play rather than attaching it to a vampire or resolving
    once and going to the ash heap: four "Unique location." cards (Oxford
    University England 101341, The Barrens 100135, Chantry 100329, Cursed
    Abattoir 102313), several further "Unique." standalone Master cards
    (e.g. Tension in the Ranks 101958), and several *non*-unique persistent
    Master cards with no "Unique" text at all (e.g. Wider View 102180, a
    "Trifle." with no uniqueness clause) -- all sharing exactly this same
    `instance_id`/`krcg_id`/`name`/`controller`/`zone`/`locked`/
    `contested_with` shape, none needing a vampire host the way
    `CardAttachment` does.

    Mirrors `AllyInPlay`'s shape as far as this card category actually needs:
    this kind of card is not a minion -- it never acts, blocks, bleeds or
    fights -- so unlike `AllyInPlay` it carries no `life`/`strength`/
    `bleed`. What it does need is a `locked` flag (Rulebook SS3 "Locking and
    Unlocking": "you will turn cards sideways... indicating the card has
    been used for some particular purpose"; a card other than a minion can
    be locked by its own printed "lock this card to..." ability exactly as a
    minion can) and -- for the subset of these 18 cards that are actually
    printed "Unique" -- the same Contested Cards tracking a unique crypt
    card/ally/attachment already has (OQ-10/OQ-15/OQ-22): covered by the
    identical unmodified Rulebook SS4 Advanced Rules > Contested Cards
    mechanism those three resolutions already quote in full, not overridden
    by the 2P variant (whose own "Contested crypt cards" section is scoped
    to crypt cards only).

    `contested_with` only ever becomes non-`None` for an instance a card
    module actually ran through `detect_contest_on_bring_into_play`
    (`engine/master_cards.py`) -- which only makes sense, and must only ever
    be called, for a card printed "Unique" (the rulebook's own Contested
    Cards mechanism is scoped to unique cards; two players independently
    playing their own copy of the *same non-unique* card, e.g. Wider View,
    is ordinary, unremarkable deck construction, never a contest). A
    non-unique card's own module simply never calls that function, so its
    `contested_with` stays `None` for the instance's whole lifetime -- no
    extra field, branch, or "is this card unique" flag is needed on this
    dataclass itself to support that; it falls out of which functions a
    future card module chooses to call, exactly like `CardAttachment`
    (OQ-22) already works the same way for an attached master card.

    `zone` takes three values, mirroring `AllyInPlay.zone`'s own convention:
    `"in_play"` (the default -- in play, usable, this entity's analogue of
    an ally's `"ready"`), `"contested"` (Rulebook SS4: "turned face down and
    are out of play" for the contest's duration -- reachable only via
    `detect_contest_on_bring_into_play`, so never reached by a non-unique
    card) and `"burned"` (yielded/removed from play, or any future card's
    own "burn this card" cost).

    Unlike a recruited `AllyInPlay` (which Rulebook SS4 "Recruit Ally"
    explicitly enters locked, "cannot act this turn"), nothing in the
    generic Master Phase play rule (`engine/phases/master.py`'s own module
    docstring; no "enters locked" clause anywhere in that rule) locks a
    newly-played Master card -- and Rulebook SS3 "Locking and Unlocking"
    only ever describes locking as something an effect *does* to a card
    ("you will turn cards sideways... indicating that the cards have been
    used for some particular purpose or effect"), never as a default state a
    card starts in. So `locked` defaults to `False`: a freshly-played
    instance starts unlocked, available for its own "lock this card to..."
    ability (if it has one) the moment it enters play, exactly like
    `CardAttachment.zone` defaulting to `"attached"` (in play, usable) with
    no analogous starting lock either.
    """

    instance_id: str
    krcg_id: int
    name: str
    controller: str
    zone: str = "in_play"
    locked: bool = False
    contested_with: str | None = None  # instance_id of the opposing copy, if contested

    @property
    def is_unlocked_in_play(self) -> bool:
        return self.zone == "in_play" and not self.locked


@dataclass
class TurnCardInPlay:
    """One non-unique library card whose own printed text puts it into play
    for the rest of the turn it was played, until burned -- either by its
    own printed trigger or by the generic end-of-turn sweep (`engine/
    turn_cards.py::clear_turn_cards_at_end_of_turn`) -- OQ-34 (`docs/
    OPEN_QUESTIONS.md`), the first-needed example being Loup (krcg id
    102273, `types == ["Action Modifier"]`, `clans == ["Toreador"]`): "Put
    this card in play. Toreador get +1 stealth. Burn this card at the end
    of the turn or after a Toreador performs a successful action."

    Distinct from `MasterCardInPlay` (OQ-23): that entity models a
    *persistent, cross-turn* standalone Master card (no built-in expiry,
    and -- for the Unique subset -- real Contested Cards tracking). A
    `TurnCardInPlay` by contrast self-destructs by the end of the turn it
    was played in at the latest, by construction, and -- per every known
    instance of this shape so far -- is never itself printed "Unique" (a
    future card that is both "Unique" and turn-scoped would need its own
    look, not an assumed fit here, CLAUDE.md "no guessing"), so it carries
    no `contested_with`/`controller`-pair contest machinery at all.

    `zone` takes only two values: `"in_play"` (the default) and `"burned"`.
    The per-card "only one X can be played each turn" cap some cards in
    this shape print (e.g. Loup) is deliberately not modeled here -- it is
    a provider-side play-offer eligibility check (whether to offer the play
    at all), not a property of an already-in-play instance, and no card
    module exists yet to need it (see `docs/OPEN_QUESTIONS.md` OQ-34's own
    resolution for what is, and is not, built here).
    """

    instance_id: str
    krcg_id: int
    name: str
    controller: str
    zone: str = "in_play"

    @property
    def is_in_play(self) -> bool:
        return self.zone == "in_play"


@dataclass
class PlayerState:
    player_id: str
    pool: int = 0
    hand: list[LibraryCard] = field(default_factory=list)
    library: list[LibraryCard] = field(default_factory=list)
    ash_heap: list[LibraryCard] = field(default_factory=list)
    crypt_deck: list[CryptCard] = field(default_factory=list)
    vampires: dict[str, VampireInPlay] = field(default_factory=dict)
    allies: dict[str, AllyInPlay] = field(default_factory=dict)
    master_cards: dict[str, MasterCardInPlay] = field(default_factory=dict)
    turn_cards: dict[str, TurnCardInPlay] = field(default_factory=dict)
    """OQ-34 (`docs/OPEN_QUESTIONS.md`): every `TurnCardInPlay` this player
    controls, keyed by `instance_id` -- mirrors `master_cards`'s own shape."""
    card_played_turn: dict[int, int] = field(default_factory=dict)
    """Generic "only one X can be played each turn" scratch, keyed by
    `krcg_id`, storing the `GameState.turn_number` that card was last
    played on -- added implementing Loup (krcg id 102273, `src/vtesbot/
    cards/loup.py`), "Only one Loup can be played each turn." Mirrors
    `VampireInPlay.ability_used_turn`'s own "store the turn number, compare
    on next check" shape, but scoped to the controller rather than to one
    vampire: this cap is a plain card-play restriction (any copy, played by
    any of the controller's vampires), not a printed ability tied to a
    specific minion, so per-vampire scoping would not fit. A provider
    checks `player_state.card_played_turn.get(krcg_id) == state.turn_number`
    before offering its own "play this card" option."""
    _next_instance_seq: int = 0
    _next_ally_instance_seq: int = 0
    _next_attachment_instance_seq: int = 0
    _next_master_card_instance_seq: int = 0
    _next_turn_card_instance_seq: int = 0

    def new_instance_id(self) -> str:
        self._next_instance_seq += 1
        return f"{self.player_id}-V{self._next_instance_seq}"

    def new_ally_instance_id(self) -> str:
        """Mints an ally instance id in its own namespace, distinct from a
        vampire's `"...-V<n>"` ids (OQ-7, `docs/OPEN_QUESTIONS.md`;
        `engine/allies.py::recruit_ally`)."""
        self._next_ally_instance_seq += 1
        return f"{self.player_id}-A{self._next_ally_instance_seq}"

    def new_attachment_instance_id(self) -> str:
        """Mints a card-attachment instance id in its own namespace,
        distinct from a vampire's `"...-V<n>"` and an ally's `"...-A<n>"`
        ids (OQ-22, `docs/OPEN_QUESTIONS.md`; `engine/attachments.py::
        attach_card`)."""
        self._next_attachment_instance_seq += 1
        return f"{self.player_id}-AT{self._next_attachment_instance_seq}"

    def new_master_card_instance_id(self) -> str:
        """Mints a standalone master-card instance id in its own namespace,
        distinct from a vampire's `"...-V<n>"`, an ally's `"...-A<n>"` and an
        attachment's `"...-AT<n>"` ids (OQ-23, `docs/OPEN_QUESTIONS.md`;
        `engine/master_cards.py::bring_master_card_into_play`)."""
        self._next_master_card_instance_seq += 1
        return f"{self.player_id}-M{self._next_master_card_instance_seq}"

    def new_turn_card_instance_id(self) -> str:
        """Mints a turn-scoped card instance id in its own namespace,
        distinct from every other card category's own (OQ-34, `docs/
        OPEN_QUESTIONS.md`; `engine/turn_cards.py::
        bring_turn_card_into_play`)."""
        self._next_turn_card_instance_seq += 1
        return f"{self.player_id}-T{self._next_turn_card_instance_seq}"


@dataclass
class GameState:
    format: FormatConfig
    rng: GameRNG
    log: ReplayLog
    agents: dict[str, Agent]
    players: dict[str, PlayerState]
    turn_order: list[str]
    active_player: str
    phase: str = "setup"
    turn_number: int = 1
    edge_holder: str | None = None
    first_influence_phase_used: bool = False
    eliminated: set[str] = field(default_factory=set)
    victory_points: dict[str, float] = field(default_factory=dict)
    game_over: bool = False
    winner: str | None = None
    oust_deferral_depth: int = 0
    pending_ousts: list[str] = field(default_factory=list)
    """OQ-44: while `oust_deferral_depth > 0` (`engine/pool.py::
    simultaneous_pool_losses`) `check_oust` only queues the player here; the
    queue is resolved once, together, when the outermost deferral exits."""
    combat_range: str | None = None
    """Current combat round's range ("close"/"long"), set by `engine/
    combat.py`'s Determine Range step each round (Rulebook SS4 Combat >
    Combat Sequence step 2) -- `None` whenever no combat is in progress.
    Exposed on `GameState`, not just as a local variable inside `run_combat`,
    so a future card hook that needs to gate a strike/effect by range
    (Rulebook SS4 Combat > Determine Range: "Some effects can only be used at
    close range, some only at long range") can read it without an engine
    signature change -- no consumer reads it yet, building that gating is
    deliberately out of scope for the pass that added this field (see
    `engine/combat.py` module docstring)."""

    def other_player(self, player: str) -> str:
        """2P structural fact (Rulebook SS5; CLAUDE.md SS3): with exactly two
        Methuselahs, the sole opponent is always both prey and predator."""
        others = [p for p in self.turn_order if p != player]
        return others[0]

    def ask(self, decision: Decision) -> Choice:
        """The single gateway between the engine and a player's agent.

        CLAUDE.md "Decision points are explicit": builds the `Observation`
        for `decision.player`, calls their `Agent.decide`, and enforces that
        the returned `Choice` is one of `decision.choices` -- never letting
        the engine or the agent silently invent an illegal option.

        Rulebook SS5 Ending the Game: "The game continues until only one
        Methuselah is left" (2P: any oust leaves one), so asking after
        `game_over` is an engine bug (a phase/hook loop missing its
        `state.game_over` guard); raises `GameOverError` as a safety net.
        """
        if self.game_over:
            raise GameOverError(
                f"decision {decision.kind!r} for {decision.player} requested after game over"
            )
        observation = build_observation(self, decision.player)
        agent = self.agents[decision.player]
        answer = agent.decide(observation, decision)
        legal = {c.value: c for c in decision.choices}
        if answer.value not in legal:
            raise IllegalChoiceError(
                f"{decision.player} chose {answer.value!r} for decision kind "
                f"{decision.kind!r}; legal choices were {sorted(legal)}"
            )
        canonical = legal[answer.value]
        self.log.record_decision(decision, canonical)
        return canonical

    def ask_unless_forced(self, decision: Decision) -> Choice:
        """`ask`, except a lone legal choice is taken without a `Decision`
        (decision.py: "only when needed"; no agent call). The taken choice is
        logged as a `"forced"` entry (engine/log.py), not a `"decision"`."""
        if len(decision.choices) == 1:
            self.log.record_forced(decision, decision.choices[0])
            return decision.choices[0]
        return self.ask(decision)

    def ready_unlocked_vampires(self, player: str) -> list[VampireInPlay]:
        return [v for v in self.players[player].vampires.values() if v.is_ready_unlocked]

    def is_eliminated(self, player: str) -> bool:
        return player in self.eliminated
