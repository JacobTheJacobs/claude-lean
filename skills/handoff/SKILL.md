---
name: handoff
description: Save a short handoff note so work continues after /clear without re-reading. Use when the user says handoff, or wants a fresh session but is mid-task.
---

# Handoff

A fresh session is far cheaper than a long one, but it forgets. Write what the next session needs, nothing more.

Run this, filling in the note (max ~15 lines, plain facts, no narration):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/tools/handoff.py" save <<'NOTE'
Goal: <one line: what the user wants>
Done: <what is finished, with file:line where it matters>
State: <what is in progress, uncommitted changes, branch>
Decisions: <choices made and why, only ones a newcomer would get wrong>
Next: <the next 1-3 concrete steps>
Watch out: <gotchas, failing tests, things not to touch>
NOTE
```

Then tell the user in one line: "Handoff saved. Run /clear; the next session picks it up."
