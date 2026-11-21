#!/usr/bin/env python3
"""Compaction summary instructions (PreCompact hook).

When Claude Code compacts a long conversation, this hook's output becomes extra instructions for the summary. It asks
the summary to keep what is expensive to find again (exact paths, commands, errors, decisions, the next step) and drop
what can be re-read cheaply (file contents, full logs). A summary that keeps the right facts saves the re-reads and
repeated searches that usually follow a compaction. Your own /compact instructions still apply."""
import json
import sys

RULES = """Claude Lean, for this summary:
- Keep exactly: file paths touched, commands that worked, the last error of anything still failing, decisions made and why, the user's stated preferences, and the next step.
- Drop: file contents and full logs (they can be read again), tool output that led nowhere, and repeated attempts.
- Keep it short: a list, not prose."""


def main():
    try:
        json.load(sys.stdin)
    except ValueError:
        pass
    print(RULES)


if __name__ == "__main__":
    main()
