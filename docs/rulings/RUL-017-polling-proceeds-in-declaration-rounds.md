---
status: resolved
date: 2026-10-23
cards:
---

# RUL-017 - Polling proceeds in declaration rounds

- Situation: RUL-006 had both Methuselahs alternate one step at a time
  (cast one source or pass). A card played mid-cast (ENG-051) then passed
  the turn before its new votes could be cast, and RUL-006 left open how a
  card play fits the casting order. Found by `rules-auditor` reviewing
  ENG-051.
- Rules & interactions: Rulebook §4 The Referendum, Polling: Methuselahs
  "cast any votes and ballots they have ... in any order. They call out
  their votes and ballots freely"; "The polling stage is completed only
  when all Methuselahs are finished casting votes and ballots." Rulebook
  §2 Sequencing: the acting Methuselah has the impulse and "may play
  another and another" before it passes on.
- Solution (user ruling, 2026-10-23, table practice): polling runs in
  rounds. In each round the caller, then each other Methuselah in seating
  order, declares as many casts and card plays as they want before handing
  on. Rounds repeat while anyone cast or played anything in the last
  round; a round where nobody does closes polling. Supersedes RUL-006. Who
  goes first in the Blood Hunt referendum stays RUL-014. Implementation:
  ENG-055.
