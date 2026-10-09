# Open questions

Rules or card interactions that the official sources do not settle.
Nothing listed here may be implemented by guessing. Format and
procedure: see `.claude/skills/vtes-rules-reference/SKILL.md`.

## OQ-1: Prey/predator wording in a duel   (status: open)

- Situation: with two players, each Methuselah is the other's prey
  and predator (Rulebook §5). Some card texts distinguish prey from
  predator, or refer to "other Methuselahs" in a way written for
  4–5 players.
- Sources read: Rulebook v1.1 §5; 2P variant page (modified
  2025-05-20); 2P updates page (2026-10-03). No dedicated
  clarification found.
- Candidate readings: to be listed per card when encountered.
- Impacted cards: to be listed.

## OQ-2: Interface target   (status: resolved — digital first)

- Decision: digital-first. The engine owns the full game state and
  exposes explicit legal choices; the first implementation target
  is a CLI interface.
- Rationale: the project is built around deterministic state
  tracking, legal-action decision points, and engine-driven play,
  which are natural to a digital interface and easier to validate
  than a physical-table workflow.
- Scope: the physical-table workflow remains out of scope unless a
  concrete requirement appears. The project will proceed with
  digital play and CLI-first tooling by default.

## OQ-3: Combat "press" step — exact turn order   (status: resolved)

- Situation: Rulebook SS4 Combat describes each round ending with a "press"
  step ("alternating") before the round either ends or another begins. The
  `vtes-rules-reference` skill's condensed mapping names the step and that
  it alternates, but did not spell out which combatant is consulted first.
- Resolution: `rules-auditor` fetched the primary rulebook page directly and
  quoted it verbatim: "The acting minion always gets first opportunity to
  use cards or effects before the opposing minion" — stated as applying at
  every stage of combat, including press. This matches the project's own
  impulse invariant (CLAUDE.md SS5 / Rulebook SS2 Sequencing): the acting
  minion's controller is always asked to press first, every round, never
  alternating by round parity.
- Fix applied: `src/vtesbot/engine/combat.py` (`run_combat`, press step) now
  always orders `[(acting_player, acting_vampire), (blocking_player,
  blocking_vampire)]`, with no round-parity alternation.

## OQ-4: 2P contested crypt cards — exact contest trigger moment   (status: resolved)

- Situation: the 2P variant's contested-crypt-card rule (per the
  `vtes-rules-reference` skill's condensed mapping) gave the *resolution*
  cost (1 pool per unlock phase, or yield/burn) but the mapping did not
  state the precise moment a contest begins.
- Resolution: `rules-auditor` fetched the primary 2P variant page directly
  (<https://www.vekn.net/two-player-format/655-two-player-variant-for-vampire-the-eternal-struggle>)
  and quoted it verbatim: "If more than one unique crypt card with the same
  name is brought into play, that means control of the card is being
  contested" / "A second copy brought in later is immediately contested,
  and can still be used as normal." This confirms the implemented reading
  (contest triggers on reveal into play, not while both copies are merely
  face down/uncontrolled) is correct.
- Code: `src/vtesbot/engine/contests.py` (`detect_contest_on_reveal`) — no
  change needed, reading A was already implemented.

## OQ-5: Does a failed block attempt lock the blocker?   (status: resolved)

- Situation: `src/vtesbot/engine/action.py::attempt_block` locks the
  blocking vampire only when the block *succeeds* (intercept >= stealth,
  leading to combat), not when an attempt is made but fails to connect
  (stealth exceeds intercept).
- Resolution: confirmed by `rules-auditor` on a follow-up pass, re-fetching
  the rulebook's "Resolve the Action" step verbatim: "If the action is
  blocked, then any card played to perform the action is burned and the
  block is resolved with these two simultaneous consequences: the blocking
  minion is locked and enters combat with the acting minion... The effects
  of the action do not take place when the action is blocked." Locking is
  stated as a consequence tied strictly to the action *being blocked*, i.e.
  a successful block — combined with "If one attempt to block fails,
  another can be made as often as the blocking Methuselah wishes" (a locked
  minion could not retry), this confirms reading A (implemented) over
  reading B.
- No code change needed: `attempt_block` already implements reading A
  correctly.
- Impacted code: `src/vtesbot/engine/action.py` (`attempt_block`).

## OQ-6: Referendum vote-tally/pass-fail for two Methuselahs (status: resolved)

- Situation: the `vtes-rules-reference` skill's condensed mapping of
  Rulebook §4 Politics gives *where votes come from* ("1 from a political
  action card (max 1 per Methuselah), titles (primogen 1, prince/baron 2,
  justicar 3, Inner Circle 4; Sabbat and other sects per §6–7), burning the
  Edge = 1. Only ready minions vote. Ties fail.") and *when terms are
  chosen* ("Terms chosen only after success"), but does not state what a
  referendum's cast votes are compared against to decide pass/fail, nor what
  "ties fail" is relative to. This pool's own three Political Action cards
  additionally surfaced a related, unexplained state: card rulings for
  Perfect Paragon and Scalpel Tongue both read "[c]annot be used during a
  referendum that is automatically passing" [PIB 20150105] [LSJ 19980107],
  raising the question of whether that's a duel-specific mechanic (only one
  possible opposing voter).
- Resolution: `rules-auditor` re-fetched both primary sources directly
  (<https://www.vekn.net/rulebook/4-detailed-turn-sequence>, Politics/
  Referendum subsection, and the 2P variant page) and settled all three
  bundled questions:
  1. **What are votes compared against, what does "ties fail" mean?**
     Quoted verbatim: "all Methuselahs may now cast any votes and ballots
     they have... in any order... there is no obligation to cast"; "Each
     vote or ballot cast is cast either 'for' or 'against' the referendum";
     "If there are more votes for the referendum than against, it passes...
     Otherwise, the referendum fails... Tied referendums fail." Votes are a
     straight for/against tally across whatever sources each Methuselah
     chooses to use (political-action card, titled ready vampires,
     burning the Edge, other cards — "Methuselahs have no inherent votes or
     ballots") — not "Methuselah vs Methuselah". This degrades cleanly to
     two players: an uncontested referendum is simply 0-for/0-against,
     which ties, which fails, same as with any player count. **Reading A
     confirmed.**
  2. **Does the 2P variant override this?** No — re-fetched directly;
     confirmed no referendum-procedure override exists, only the
     already-known title-contest exception.
  3. **Is "automatically passing" a duel-specific mechanic?** No —
     **reading B was wrong.** The actual General Ruling [PIB 20150105],
     fetched from the forum post krcg cites
     (<https://www.vekn.net/forum/rules-questions/68465-voting-is-complicated#68493>):
     "If a referendum will pass automatically (e.g., Cryptic Rider,
     Charming Lobby, Malkavian Rider Clause, Día de los Muertos), then no
     casting votes or ballots occurs during the automatic referendum." This
     is a card-text-triggered category (specific cards whose own printed
     text declares their called referendum passes automatically), entirely
     unrelated to player count. Confirmed via krcg that none of this
     pool's three Political Action cards (Disputed Territory, Kine
     Resources Contested, Parity Shift) carry this text themselves, so the
     mechanic does not apply to any card in the current pool.
- Remaining work is engineering, not a ruling: `political_action` should
  gain a real polling step (enumerate each Methuselah's available vote
  sources, let each commit for/against, tally, apply ties-fail) to replace
  the current `UnresolvedRulingError("OQ-6")`; once built, the cards below
  can move from `blocked` to implementation.
- Note for later: if a card entering the 2P pool ever prints its own
  "this referendum passes automatically" text (none currently do), that
  card's own text is authoritative per the Golden Rule for Cards (CLAUDE.md
  §2) and needs no new Open Question — it's a plain card-text clause, not
  an unsettled ruling.
- Impacted code: `src/vtesbot/engine/politics.py::political_action` raises
  `UnresolvedRulingError("OQ-6")` immediately once a political action goes
  unblocked, rather than guessing. Impacted cards (all registered `blocked`,
  reason `OQ-6`): Disputed Territory, Kine Resources Contested, Parity Shift
  (call a referendum); Perfect Paragon, Scalpel Tongue, Voter Captivation,
  Oxford University, England (only usable during/after a referendum's
  polling step or resolution); crypt-vampire printed abilities Alexa
  Draper, Diana Iadanza, Fiorenza Savona, Marcos Belegrad, Modius, Queen
  Anne (each reads or modifies a referendum's polling step or who called
  it).
