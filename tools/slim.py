#!/usr/bin/env python3
"""Slim: turn off Claude Code features most sessions never use, whose definitions ride along in every request.

    python3 slim.py on      add the switches to ~/.claude/settings.json "env" (backup first)
    python3 slim.py off     remove only the switches slim added
    python3 slim.py         show which switches are set

Measured per request on Claude Code 2.1.239: Artifact 13.5K, Workflows 8.1K, background tasks 1.1K, cron 0.3K,
advisor 0.2K tokens; short tasks -32%. From 2.1.330 those tools are gone or loaded on demand and the switches save
nothing. There slim denies ListAgents (messaging other sessions, 0.5K, always loaded), hides the Explore/Plan agent
listing, and caps each skill description in the skill listing at 200 characters (Claude Code's default is 1,536; the
skills themselves are unchanged and still run): 20.5K -> 16.4K tokens per request with Lean's own rules included. Also drops the per-session
attribution header, which made every new session and subagent re-write ~6K tokens of cache. Your MCP servers, skills,
web tools and other subagents stay. Applies to new sessions.
Env: CLAUDE_DIR, else CLAUDE_CONFIG_DIR, else ~/.claude."""
import json
import os
import shutil
import sys
import time
from pathlib import Path

SLIM = {f"CLAUDE_CODE_DISABLE_{k}": "1" for k in
        ("ARTIFACT", "WORKFLOWS", "BACKGROUND_TASKS", "CRON", "ADVISOR_TOOL", "EXPLORE_PLAN_AGENTS")}
# Git instructions stay on: turning them off lost SWE-bench django-13297 0/6 vs 6/6 with them (2026-11-23), for 2.4K tokens.
# The per-session attribution header is the first system block and differs per session, so every new session and
# subagent re-writes ~6K tokens of cache that would otherwise be read (measured on 2.1.330: 6,262 written -> 0).
SLIM["CLAUDE_CODE_ATTRIBUTION_HEADER"] = "false"
MARK = "CLAUDE_LEAN_SLIM"      # records which env keys slim set, so `off` removes only those
# Always-loaded tool definition few sessions use. Denying a tool removes it from the request.
DENY = ["ListAgents"]
DENY_MARK = "CLAUDE_LEAN_SLIM_DENY"
# Skill descriptions ride in every request; the first 200 characters carry the "use when" part.
DESC = ("skillListingMaxDescChars", 200)
DESC_MARK = "CLAUDE_LEAN_SLIM_DESC"


def strip(s):
    """Remove the switches slim added (per MARK). Returns s."""
    env = s.get("env", {})
    for k in (env.pop(MARK, "") or "").split(","):
        if k and env.get(k) == SLIM.get(k, "1"):
            del env[k]
    if env.pop(DESC_MARK, None) and s.get(DESC[0]) == DESC[1]:
        del s[DESC[0]]
    ours = (env.pop(DENY_MARK, "") or "").split(",")
    perm = s.get("permissions", {})
    if "deny" in perm:
        perm["deny"] = [r for r in perm["deny"] if r not in ours]
        if not perm["deny"]:
            del perm["deny"]
        if not perm:
            del s["permissions"]
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
    have = s.setdefault("permissions", {}).setdefault("deny", [])
    denied = [t for t in DENY if t not in have]
    have.extend(denied)
    if denied:
        env[DENY_MARK] = ",".join(denied)
    capped = DESC[0] not in s
    if capped:
        s[DESC[0]] = DESC[1]
        env[DESC_MARK] = "1"
    if not have:
        del s["permissions"]["deny"]
        if not s["permissions"]:
            del s["permissions"]
    if not env:
        del s["env"]
    return added + denied + ([f"{DESC[0]}={DESC[1]}"] if capped else [])


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
