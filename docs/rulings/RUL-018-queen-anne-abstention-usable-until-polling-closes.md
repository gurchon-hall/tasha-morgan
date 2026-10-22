---
status: resolved
date: 2026-10-23
cards: Queen Anne
---

# RUL-018 - Queen Anne abstention usable until polling closes

- Situation: `cards/queen_anne.py` offers her abstention only in the
  before-cast window (`pending["forced_abstain"]`), so she cannot target a
  vampire once casting has begun. Found by `rules-auditor` reviewing
  ENG-051.
- Rules & interactions: Queen Anne (201647, `data/cards/201647.json`):
  "During the polling step of a referendum called by Anne, she can burn 1
  blood to force a younger Camarilla vampire to abstain." Rulebook §4
  Polling: "Once a vote or a ballot has been cast, however, it cannot be
  changed." Scalpel Tongue makes an abstention cancel cast votes (RUL-016).
- Solution (user ruling, 2026-10-23): her ability can be used until the
  polling step closes, with the same timing and effect as Scalpel Tongue:
  a target who already cast has those votes cancelled (RUL-016).
  Implementation: ENG-056.
