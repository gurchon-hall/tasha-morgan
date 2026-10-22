---
status: resolved
date: 2026-10-09
cards:
---

# RUL-004 - Failed block attempt locking

- Situation: whether a blocking vampire locks when a block attempt is
  merely made but fails to connect (stealth exceeds intercept), vs.
  only when the block actually succeeds.
- Rules & interactions: the rulebook's "Resolve the Action" step ties
  locking strictly to the action *being blocked* (a successful block):
  "the blocking minion is locked and enters combat with the acting
  minion." Combined with "If one attempt to block fails, another can
  be made as often as the blocking Methuselah wishes" (a locked minion
  could not retry), this confirms locking happens only on success.
- Solution: `src/vtesbot/engine/action.py::attempt_block` already
  implements this correctly — no code change needed.
