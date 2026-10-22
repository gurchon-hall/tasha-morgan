---
status: resolved
date: 2026-10-10
cards: Dust Up
---

# ENG-012 - Dust Up - no sect, no dodge/extra strike

- Situation: Dust Up (100597, "Requires an Anarch", three discipline
  clauses) was blocked by two independent gaps: (1) the engine had no
  vampire-sect concept at all, and (2) the `[cel]` clause ("dodge,
  with 1 additional strike (limited)") needed dodge and same-round
  additional-strike mechanics `engine/combat.py` didn't have.
- Rules & interactions: Rulebook §6 Vampire Sects + §7 (Laibon) name the
  five sects; §4 Combat's Choose Strike / Additional Strikes sections
  cover dodge and repeat strikes; [LSJ 20030902-2]/[LSJ 20060808-1]
  confirm a dodge-proof strike ("cannot be dodged") still lets the
  opponent dodge, it just has no effect against that one strike.
- Solution: added `Sect` enum + `CryptCard.sect` + `derive_sect
  (card_text)` (a regex classifier over the printed sect preamble,
  100% hit rate across the full krcg crypt dataset; raises
  `UnresolvedRulingError` rather than guessing on a non-match). Added
  `COMBAT_DODGE_OPTION_HOOK` (zeroes the opponent's simultaneous
  damage unless the attacking strike is flagged
  `StrikeDamage(ignore_dodge=True)`) and
  `COMBAT_ADDITIONAL_STRIKE_HOOK` (re-enters the full strike-choice
  machinery). Dust Up was then implemented (all three clauses, gated
  on `sect is Sect.ANARCH`); the `[cel]` "(limited)" cap was initially
  enforced per-vampire-forever rather than per-round (stricter than
  the rule, never looser) until ENG-013 fixed this properly with shared
  round-scoped state. `Status.IMPLEMENTED`.
