#!/usr/bin/env python3
"""Load a handoff note into a fresh session (SessionStart hook).

After /clear (or a new session in the same folder), if the handoff skill saved a note in the last 12 hours, the note is
added to the new session's context once and then deleted. No note: prints nothing, adds nothing."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))


def main():
    d = json.load(sys.stdin)
    if d.get("source") not in ("clear", "startup", None):
        return
    import handoff
    note = handoff.load(d.get("cwd"))
    if not note:
        return
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext":
                      "Handoff note from the previous session in this folder (written before /clear). "
                      "Continue from it; re-read files only where it is not enough:\n\n" + note}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
