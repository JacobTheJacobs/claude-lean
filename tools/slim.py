#!/usr/bin/env python3
"""Slim: turn off Claude Code features most sessions never use, whose definitions ride along in every request.

    python3 slim.py on      add the switches to ~/.claude/settings.json "env" (backup first)
    python3 slim.py off     remove only the switches slim added
    python3 slim.py         show which switches are set

Measured per request: Artifact 13.5K, Workflows 8.1K, git instructions 2.4K, background tasks 1.1K, cron 0.3K,
advisor 0.2K tokens; short tasks -32%. Also drops the per-session attribution header, which made every new session
and subagent re-write ~6K tokens of cache. Your MCP servers, skills, web tools and subagents stay. Applies to new sessions.
Env: CLAUDE_DIR, else CLAUDE_CONFIG_DIR, else ~/.claude."""
import json
import os
import shutil
import sys
import time
from pathlib import Path

SLIM = {f"CLAUDE_CODE_DISABLE_{k}": "1" for k in
        ("ARTIFACT", "WORKFLOWS", "GIT_INSTRUCTIONS", "BACKGROUND_TASKS", "CRON", "ADVISOR_TOOL")}
# The per-session attribution header is the first system block and differs per session, so every new session and
# subagent re-writes ~6K tokens of cache that would otherwise be read (measured on 2.1.330: 6,262 written -> 0).
SLIM["CLAUDE_CODE_ATTRIBUTION_HEADER"] = "false"
MARK = "CLAUDE_LEAN_SLIM"      # records which env keys slim set, so `off` removes only those


def strip(s):
    """Remove the switches slim added (per MARK). Returns s."""
    env = s.get("env", {})
    for k in (env.pop(MARK, "") or "").split(","):
        if k and env.get(k) == SLIM.get(k, "1"):
            del env[k]
    if "env" in s and not env:
        del s["env"]
    return s


def add(s):
    """Add the switches that are not set yet. Returns the keys added."""
    env = s.setdefault("env", {})
    added = [k for k in SLIM if k not in env]
    env.update({k: SLIM[k] for k in added})
    if added:
        env[MARK] = ",".join(added)
    elif not env:
        del s["env"]
    return added


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd not in ("on", "off", "status"):
        sys.exit(__doc__)
    f = Path(os.environ.get("CLAUDE_DIR") or os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "settings.json"
    try:
        s = json.loads(f.read_text()) if f.exists() else {}
    except ValueError:
        sys.exit(f"{f} is not valid JSON; fix it first.")
    if cmd == "status":
        env = s.get("env", {})
        on = [k for k in SLIM if env.get(k) == SLIM[k]]
        print(f"slim: {len(on)}/{len(SLIM)} switches set in {f}" + "".join(f"\n  {k}" for k in on))
        return
    before = json.dumps(s, sort_keys=True)
    strip(s)
    added = add(s) if cmd == "on" else []
    if json.dumps(s, sort_keys=True) == before:
        print(f"slim: nothing to change in {f}")
        return
    if f.exists():
        bak = f.with_suffix(f".json.lean-{time.strftime('%Y%m%d-%H%M%S')}.bak")
        shutil.copy2(f, bak)
        print(f"backup {bak}")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(s, indent=2) + "\n")
    print(f"slim {'on: added ' + ', '.join(added) if cmd == 'on' else 'off'} in {f}\n"
          "Applies to new Claude Code sessions.")


if __name__ == "__main__":
    main()
