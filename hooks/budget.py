#!/usr/bin/env python3
"""Daily dollar cap for Claude Code (UserPromptSubmit hook).

Env: LEAN_DAY_USD (cap, e.g. 10; unset = off), LEAN_PROJECT (only count projects whose log folder name contains
this; unset = all). Today's spend comes from tools/report.py (list prices, subagents included), re-measured at most every
LEAN_EVERY seconds (default 300) and kept in ~/.cache/claude-lean/. At 80% it warns; at 100% it blocks the prompt.
Set LEAN_DAY_USD higher, or unset it, to go on. Any error: it lets the prompt through."""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))


def main():
    try:
        json.load(sys.stdin)
    except ValueError:
        pass
    cap = float(os.environ.get("LEAN_DAY_USD") or 0)
    if cap <= 0:
        return
    proj = os.environ.get("LEAN_PROJECT") or None
    cache = Path.home() / ".cache" / "claude-lean" / f"today-{proj or 'all'}.json"
    now = time.time()
    day = time.strftime("%Y-%m-%d")
    try:
        c = json.loads(cache.read_text())
    except (OSError, ValueError):
        c = {}
    if c.get("day") != day or now - c.get("at", 0) > float(os.environ.get("LEAN_EVERY", 300)):
        import report
        c = {"day": day, "at": now, "usd": report.today_usd(proj)}
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(c))
    usd = c["usd"]
    if usd >= cap:
        print(json.dumps({"decision": "block", "reason": f"Claude Lean: today ${usd:.2f} of the ${cap:.2f} cap{' for ' + proj if proj else ''}. Raise LEAN_DAY_USD or unset it to go on."}))
    elif usd >= 0.8 * cap:
        print(json.dumps({"systemMessage": f"Claude Lean: today ${usd:.2f} of ${cap:.2f} ({usd / cap:.0%}). Cheaper from here: /model sonnet, the reader agent for lookups, /clear between tasks."}))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # never block work because the meter broke
        pass
