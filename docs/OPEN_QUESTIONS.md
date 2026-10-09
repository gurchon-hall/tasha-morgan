# Open questions

Rules or card interactions that the official sources do not settle. Nothing listed here may be implemented by guessing. Format and procedure: see `.claude/skills/vtes-rules-reference/SKILL.md`.

## OQ-1: Prey/predator wording in a duel   (status: open)

- Situation: with two players, each Methuselah is the other's prey and predator (Rulebook §5). Some card texts distinguish prey from predator, or refer to "other Methuselahs" in a way written for 4–5 players.
- Sources read: Rulebook v1.1 §5; 2P variant page (modified 2025-05-20); 2P updates page (2026-10-03). No dedicated clarification found.
- Candidate readings: to be listed per card when encountered.
- Impacted cards: to be listed.

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

## OQ-5: Block attempt — does a *failed* (evaded) attempt lock the blocker?   (status: resolved — no, only a successful block locks)

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

## OQ-2: Interface target   (status: resolved — digital first)

- Decision: digital-first. The engine owns the full game state and exposes explicit legal choices; the first implementation target is a CLI interface.
- Rationale: the project is built around deterministic state tracking, legal-action decision points, and engine-driven play, which are natural to a digital interface and easier to validate than a physical-table workflow.
- Scope: the physical-table workflow remains out of scope unless a concrete requirement appears. The project will proceed with digital play and CLI-first tooling by default.
