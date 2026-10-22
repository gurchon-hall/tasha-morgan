---
status: superseded
superseded_by: DES-016
date: 2026-10-11
cards:
---

# DES-006 - Single capped rules-docs file with archive

- Context: rules questions and their resolutions accumulated long
  histories, making a single file expensive to read for routine work.
- Decision: one file holding at most 25 entries, older resolved entries
  moved to numbered archive files with an index; a resolved entry is
  trimmed to Situation / Rules & interactions / Solution.
- Consequence: superseded by DES-016 (one file per entry, no cap). The
  closing trim rule carries over unchanged.
