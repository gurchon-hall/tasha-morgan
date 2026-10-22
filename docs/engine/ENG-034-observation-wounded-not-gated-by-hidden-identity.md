---
status: open
date: 2026-10-15
cards:
---

# ENG-034 - Observation - `wounded` not gated by hidden-identity

- Situation: `rules-auditor`, auditing `engine/observation.py` against
  CLAUDE.md §5's information-hiding invariant, found `build_observation`'s
  `vampire_view` gates only `blood`/`name`/`capacity` behind
  `visible_identity` (`zone != "uncontrolled" or controller == viewer`);
  `wounded` is read straight off `VampireInPlay` with no such gate.
  Currently inert: every `zone = "uncontrolled"` call site
  (`engine/setup.py`, `engine/phases/influence.py`, `cards/
  wider_view.py`) only ever sets it on a freshly-constructed
  `VampireInPlay` (`wounded=False` by dataclass default); no code path
  moves an already-revealed, possibly-wounded vampire back to
  `"uncontrolled"`.
- Sources read: CLAUDE.md §5 ("agents receive an `Observation`... never
  the raw `GameState`. A bot must not read... face-down uncontrolled
  vampires.") -- a project invariant, not an external VEKN source.
- Candidate readings: N/A -- missing explicit gate, not a ruling
  question. A future card effect returning a vampire face-down to the
  crypt while it carries `wounded`/`locked` state would leak that state
  through this exact path, with no test positioned to catch it.
- Impacted code/cards: `src/vtesbot/engine/observation.py`
  (`build_observation`/`vampire_view`). No card blocked yet.
