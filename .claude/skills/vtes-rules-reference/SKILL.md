---
name: vtes-rules-reference
description: >-
  Condensed VtES rules (VEKN rulebook v1.1 + two-player variant) with
  section pointers, and the mandatory procedure when a rule is
  unclear. Load before implementing, testing or reviewing any game
  mechanic.
---

# VtES rules reference for the duel bot

This is a **map**, not a substitute for the sources. Before
implementing a mechanism, open the cited section and read it in
full.

A local, versioned cache of the rulebook and 2P-variant pages
(verbatim text, fetched directly — not paraphrased) lives at
`data/sources/rulebook/<date>/<n>-<slug>.md` and
`data/sources/2p-variant/<date>/{variant,updates}.md`; read the cache
first for routine implementation/testing work instead of fetching
live every time. **`rules-auditor`, and anyone resolving an Open
Question, must still re-fetch the live page** — both depend on
independent verification that a trusted cache would undermine.
See `data/sources/rulebook/CHANGELOG.md` for a caveat: individual
rulebook sections get edited without the cover "v1.1" label changing,
so the cache's per-page `dateModified` header is the real freshness
signal, not the v1.1 date.

- Rulebook v1.1 (October 2023): <https://www.vekn.net/rulebook>
  (sections 1–9 + Imbued appendix)
- Detailed play summary:
  <https://www.vekn.net/detailed-play-summary>
- General rulings: <https://www.vekn.net/general-rulings> — Card
  rulings: <https://www.vekn.net/card-rulings>
- 2P variant:
  <https://www.vekn.net/two-player-format/655-two-player-variant-for-vampire-the-eternal-struggle>
- 2P updates:
  <https://www.vekn.net/two-player-format/675-two-player-format-updates>

## Precedence

Card text > official card rulings > 2P variant > rulebook. ("Golden
Rule for Cards", Rulebook §3.)

## Setup (§3 Game Setup, 2P variant)

- 30 pool each; blood bank unlimited; the Edge starts uncontrolled.
- Shuffle crypt and library; predator cuts. Draw 7 library cards;
  deal 4 crypt cards face down to the uncontrolled region.
- Deck: crypt ≥ 12, one group or two consecutive groups (§1, §2).
  Library **40–60** in 2P (60–90 in the rulebook). Any number of
  copies.

## Turn sequence (§4)

1. **Unlock**: unlock all your cards, then unlock-phase effects in
   the order you choose; Edge holder may gain 1 pool. Contests paid
   here (1 pool per contested card; 1 blood per contested title).
2. **Master**: 1 master phase action by default; trifles grant one
   extra (max one per phase); an out-of-turn master played earlier
   removes one; unused actions are lost.
3. **Minion**: actions by ready unlocked minions; mandatory actions
   first (a ready vampire with no blood must hunt). Each action
   fully resolves before the next.
4. **Influence**: 4 transfers. Rulebook ramp-up 1/2/3 is **replaced
   in 2P**: first player gets **3** on their first influence phase,
   then 4 for all. Costs: 1 transfer = 1 pool → uncontrolled vampire;
   2 transfers = 1 blood from uncontrolled vampire → pool; 4
   transfers + burn 1 pool = move a crypt card to the uncontrolled
   region. A vampire with blood ≥ capacity may be revealed into the
   ready region, unlocked, any time in this phase.
5. **Discard**: 1 discard phase action (discard + replace, or play
   one event).

## Cards in general (§2)

- Play = announce, show, resolve; replace from library after play
  (hand size 7 by default; adjust immediately when hand size
  changes).
- Costs are paid from own resources only. Blood cost (vampire) / pool
  cost (Methuselah).
- Same minion: same action modifier or reaction card at most once
  per action; same action card at most once per turn.
- Reaction cards: only by ready unlocked minions of a Methuselah
  other than the acting one; they do not lock.
- Reflex cards cancel a card "as it is played".
- Cancelled action card: minion does not lock, may play it again.
  Cancelled non-action card: cost is still paid.

## Sequencing / impulse (§2 Advanced rules — Sequencing)

Acting Methuselah has the impulse first and may chain effects. Then
the impulse passes (to the defending Methuselah first in combat or
for an action directed at them; for an undirected action, prey then
predator). If anyone uses an effect, the impulse returns to the
acting Methuselah. The window ends when everyone passes.

## Course of an action (§4 Minion phase)

1. Announce (all terms fixed now, except referendum terms), lock the
   acting minion. "As announced" cards come before other modifiers.
2. Block attempts: **directed** action → only the targeted
   Methuselah may block; **undirected** → prey first, then
   predator. In 2P the opponent is both. Block succeeds if intercept
   ≥ stealth. Stealth may be added only when needed (an ongoing
   block would succeed); intercept only when needed (acting stealth
   exceeds it). Declining to block is final unless the target
   changes.
3. If unblocked → pay cost, resolve. If blocked → action card
   burned, cost not paid, blocker locks, combat.

"Cost not paid when blocked" scopes to the **action card's own**
printed cost (Action, Political Action, Equipment, Retainer, Ally,
...) — the card played to perform the action itself. It does NOT
apply to an Action Modifier played during that same action: an Action
Modifier resolves immediately when played (not deferred to the
action's own resolve step), so its own cost (card discarded + any
printed blood/pool/etc.) is paid in full the instant it is played,
regardless of whether the action later turns out blocked or
unblocked. Model this as: an action card's `HookOption`/equivalent
pays its cost only inside the unblocked `resolve()` branch; an Action
Modifier's `HookOption.cost` pays unconditionally at the moment it is
chosen (same mechanism `apply_chosen_option` already uses for
cancel-as-played, OQ-32).

Three states to model: no current block attempt / ongoing block
attempt / blocks declined by all.

Default actions: bleed (directed, 0 stealth, bleed 1, one bleed per
minion per turn, successful bleed ≥1 takes the Edge; bleed modifiers
are "(limited)"), hunt (undirected, +1 stealth, +1 blood), equip /
employ retainer / recruit ally (undirected, +1 stealth; recruited
ally cannot act this turn), political action (undirected, +1
stealth, one per vampire per turn), leave torpor (2 blood, +1
stealth, blocked → diablerie opportunity, no combat), rescue from
torpor, diablerise, become Anarch.

## Politics (§4)

Terms chosen only after success. Votes: 1 from a political action
card (max 1 per Methuselah), titles (primogen 1, prince/baron 2,
justicar 3, Inner Circle 4; Sabbat and other sects per §6–7), burning
the Edge = 1. Only ready minions vote. Ties fail.

## Combat (§4 Combat)

Rounds of 7 steps: before range → determine range (maneuvers
alternate, no two in a row) → before strikes → strike (acting
minion chooses first; simultaneous resolution) → damage resolution
(prevent, then mend) → press (alternating) → end of round. Combat
ends at once if a combatant is no longer ready.

- Hand strike = strength (default 1), close range only. Ranged
  strikes / "R" damage any range.
- Dodge, combat ends (resolves first, before first strike), steal
  blood (not damage, before mend), destroy/steal equipment, first
  strike, additional strikes (limited, one card per round).
- Damage: 1 blood mends 1 damage; unmended → wounded → torpor.
  **Aggravated** cannot be mended; on a wounded vampire each point
  burns 1 blood or the vampire is burned. Normal damage is handled
  before aggravated. Allies/retainers lose life for any damage.
- Retainers can be targeted only by a ranged strike at long range,
  announced with the strike.

## Torpor, diablerie, blood hunt (§4)

Torpor: controlled but not ready; can only leave torpor; cannot
block, react or vote. Diablerie: blood moves to diablerist, may take
equipment, victim burned, optional discipline if victim older, then
automatic blood-hunt referendum (not an action).

## Contests (§4 Unlock + 2P variant)

Rulebook: contested cards go face down, out of play. **2P: contested
crypt cards stay in play and usable**; 1 pool each unlock phase or
yield (burn). You cannot contest with yourself. 2P exception for
titles on two copies of the same vampire: not contested.

## Ending (§5)

Pool 0 → ousted. Prey ousted → predator gets 1 VP + 6 pool. Last
Methuselah gets +1 VP. With two players left, each is the other's
prey. Withdrawal rules exist (§5 Advanced).

## Procedure when something is unclear (mandatory)

Rules docs are one file per entry, in three kinds with their own
numbering (CLAUDE.md §2, DES-016):

- `RUL` -- `docs/rulings/`: how a rule or card text is read.
- `ENG` -- `docs/engine/`: an engine mechanism a card needs, a gap in
  one, or an engine bug found in review.
- `DES` -- `docs/design/`: a project, architecture or bot choice (not
  a VtES fact).

1. Re-read the card text, its rulings, the 2P variant page and the
   rulebook section.
2. Still unclear or conflicting → do **not** choose. Create
   `docs/rulings/RUL-<nnn>-<slug>.md` (or `docs/engine/ENG-...` when
   the gap is a missing engine mechanism rather than a reading of the
   rules). `<nnn>` is the next free number in that folder (zero-padded
   to 3 digits; numbers are never reused or renumbered):

   ```markdown
   ---
   status: open
   date: <YYYY-MM-DD>
   cards: <Card Name>; <Other Card>
   ---

   # RUL-<nnn> - <Card or Topic name> - <short description>

   - Situation:
   - Sources read: (with URL/section)
   - Candidate readings: A / B      (ENG: Needed mechanism:)
   - Impacted code:
   ```

   Then run `python scripts/docs_index.py` to regenerate the folder's
   `README.md` index.
3. Make the code path raise `UnresolvedRulingError("RUL-<nnn>")`, or
   mark the card `blocked` with `blocked_reason="RUL-<nnn>"` (or
   `"ENG-<nnn>"`).
4. Mention the entry id in your final report so the user can decide
   (or ask a VEKN judge).

## Closing an entry (mandatory trim)

The instant an entry's status flips to `resolved`, set `status:
resolved` in its front matter and rewrite its body down to exactly
three bullets — drop everything else (audit-round play-by-play,
rejected alternatives, full "impacted code" file lists, test-file
enumerations, pass counts): this is an editorial trim of the same
entry, not a re-litigation, so no fact may change, only its length.

```text
- Situation:
- Rules & interactions:
- Solution:
```

- **Title**: `<ID> - <Card or Topic name, if one exists> - <short
  description>`. Tie the title to the specific card that was blocked
  wherever one exists (e.g. `ENG-022 - Diana Iadanza - no "cancel as
  played" hook`); fall back to a plain topic description only for an
  entry with no associated card.
- **Situation**: the problem found, in enough detail to stand alone —
  what card/text/rule prompted it, why it blocked something.
- **Rules & interactions**: the sourced reading that settles it — the
  governing rule/ruling/citation, condensed to what it actually says,
  not the research narrative that led there.
- **Solution**: what was built or decided, and what (if anything) is
  deliberately still left open for a future pass. Name the lasting
  pointers (new hooks, modules, functions) a future implementer needs;
  drop the rest.
- An entry still `open` is never trimmed this way.

A `DES` entry uses `Context` / `Decision` / `Consequence`. A decision
replaced by a later one gets `status: superseded` plus
`superseded_by: DES-<nnn>`; it is never deleted. Regenerate the index
(`python scripts/docs_index.py`) after any front-matter or title
change.
