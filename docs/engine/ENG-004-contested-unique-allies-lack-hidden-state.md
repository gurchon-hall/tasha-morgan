---
status: resolved
date: 2026-10-10
cards:
---

# ENG-004 - Contested unique allies lack hidden state

- Situation: `AllyView`/`build_observation` showed every in-play ally
  unconditionally to both players — correct for a non-unique ally but
  not for a contested unique one.
- Rules & interactions: Rulebook §4 Advanced Rules > Contested Cards is
  one unified mechanism for every unique card, crypt or not (face
  down, out of play, 1 pool/unlock-phase or yield); the 2P variant's
  "stays in play, usable" override is scoped to crypt cards only (by
  its own title and aside) — so a contested ally follows the
  unmodified rulebook rule. A recruited ally is itself played face up,
  so unlike an uncontrolled vampire a contested ally's identity is
  never actually secret — no anonymization branch is needed, only a
  zone/usability marker.
- Solution: added `AllyInPlay.contested_with` and a `"contested"` zone
  value; `engine/allies.py::detect_contest_on_recruit` (mirrors the
  vampire-side function), wired into `_perform_recruit_ally`;
  `AllyView.contested: bool`. A pool sweep found six more unique
  allies plus one unique Equipment (Shilmulo Tarot) sharing this gap.
  The resolution loop itself (pay/yield) was deliberately left to
  ENG-009; Equipment-side tracking is left open (no card needs it yet).
