#!/usr/bin/env python3
"""Handoff notes: carry the state of a task across /clear, so a fresh (cheap) session continues without re-reading.

    python3 handoff.py save  < note.md     save a note for the current folder (the handoff skill does this)
    python3 handoff.py load                print and consume the note (hooks/handoff_hook.py does this on /clear)
    python3 handoff.py show                print it without consuming

One note per folder, kept in ~/.cache/claude-lean/handoff. A note is used once and expires after LEAN_HANDOFF_HOURS
(default 12), so an old note never leaks into unrelated work."""
import hashlib
import os
import sys
import time
from pathlib import Path

DIR = Path(os.environ.get("LEAN_CACHE", Path.home() / ".cache" / "claude-lean")) / "handoff"
HOURS = float(os.environ.get("LEAN_HANDOFF_HOURS", 12))
MAX_CHARS = 4000  # ~1K tokens: a handoff is a note, not a transcript


def path(cwd=None):
    cwd = os.path.realpath(cwd or os.getcwd())
    return DIR / (hashlib.sha1(cwd.encode()).hexdigest()[:16] + ".md")


def save(text, cwd=None):
    text = text.strip()
    if not text:
        sys.exit("empty note")
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n[cut at ~1K tokens]"
    DIR.mkdir(parents=True, exist_ok=True)
    f = path(cwd)
    f.write_text(f"<!-- {os.path.realpath(cwd or os.getcwd())} -->\n{text}\n")
    return f


def load(cwd=None, consume=True):
    f = path(cwd)
    if not f.is_file():
        return None
    if time.time() - f.stat().st_mtime > HOURS * 3600:
        f.unlink(missing_ok=True)
        return None
    text = f.read_text().split("\n", 1)[1].strip()
    if consume:
        f.unlink(missing_ok=True)
    return text


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "save":
        f = save(sys.stdin.read())
        print(f"Handoff saved ({f.stat().st_size} bytes). Now /clear: the next session in this folder starts with it.")
    elif cmd in ("load", "show"):
        text = load(consume=cmd == "load")
        print(text if text else "no handoff note for this folder")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
