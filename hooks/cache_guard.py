#!/usr/bin/env python3
"""Warn before an edit that breaks the prompt cache (PreToolUse hook, matcher Edit|Write|MultiEdit).

CLAUDE.md files and Claude Code settings sit at the start of every request. Editing one mid-session changes that
prefix, so the next request writes the full context to cache again instead of reading it at 10% of the price.
It only warns you; the edit goes ahead."""
import json
import sys
from pathlib import Path

WATCH = ("CLAUDE.md", "CLAUDE.local.md", "AGENTS.md")
SETTINGS = ("settings.json", "settings.local.json")   # only Claude Code's own: inside a .claude folder


def main():
    f = (json.load(sys.stdin).get("tool_input") or {}).get("file_path") or ""
    p = Path(f)
    if p.name in WATCH or (p.name in SETTINGS and p.parent.name == ".claude"):
        print(json.dumps({"systemMessage": f"Claude Lean: editing {Path(f).name} changes the start of the cached prompt; the "
                          "next request re-writes the whole context to cache. If it can wait, make it between sessions."}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
