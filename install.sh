#!/usr/bin/env bash
# Claude Lean installer (backs up settings.json first; safe to re-run).
#   ./install.sh              turns off Claude Code's hidden background requests off (next-prompt suggestions, session titles,
#                             recaps, subagent progress summaries, idle compaction and check-ins), turns off the
#                             ListAgents tool, caps skill descriptions at 200 characters and warns before edits that
#                             break the prompt cache; fast mode (/fast) lasts only the session it was turned on in
#   ./install.sh --background-only   only the background requests (the env switches and idleCompaction): nothing
#                             Claude sees changes (tools, skill list, hooks and fast mode are left alone)
#   ./install.sh --pin        also turn off Claude Code auto-updates (an update changes the prompt and re-writes the cache)
#   ./install.sh --cache-1h   also keep the prompt cache 1 hour instead of 5 minutes (API keys only; a Claude
#                             subscription already gets 1 hour; 1-hour cache writes cost more, so it pays only if you
#                             often pause 5-60 minutes)
#   ./install.sh --uninstall  remove everything Claude Lean added
# Env: CLAUDE_CONFIG_DIR (default ~/.claude).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 - "$HERE" "$@" <<'PY'
import json, os, shlex, shutil, sys, time
from pathlib import Path

here, args = Path(sys.argv[1]), set(sys.argv[2:])
if args - {"--pin", "--cache-1h", "--background-only", "--uninstall"} or ("--uninstall" in args and len(args) > 1):
    sys.exit("usage: install.sh [--background-only] [--pin] [--cache-1h] | --uninstall")
un = "--uninstall" in args
f = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "settings.json"
try:
    s = json.loads(f.read_text()) if f.exists() else {}
except ValueError:
    sys.exit(f"{f} is not valid JSON; fix it first.")
if not isinstance(s, dict) or not all(isinstance(s.get(k, {}), dict) for k in ("hooks", "env", "permissions")) \
        or not isinstance(s.get("permissions", {}).get("deny", []), list):
    sys.exit(f"{f}: unexpected shape (hooks, env and permissions must be objects, permissions.deny a list); fix it first.")
before = json.dumps(s, sort_keys=True)
HOOKS = {"cache_guard.py": "Edit|Write|MultiEdit"}
OLD = ["agy_search.py", "web_guard.py"]   # hooks earlier versions installed
MARK = "CLAUDE_LEAN_V2_ADDED"   # env key listing the settings we added, so uninstall removes only those
OLD_MARK = "BOOSTV2_ADDED"       # same, written by earlier versions
TAG = "# claude-lean-v2"   # ends every hook command we write, so a re-install finds them wherever the folder was


def cmd(name):
    """Runs the hook if it is still there and never blocks the tool: a moved or deleted checkout would otherwise make
    python3 exit 2, which Claude Code reads as 'block this Edit/Write'."""
    p = shlex.quote(str(here / "hooks" / name))
    return f"test -f {p} && python3 {p}; exit 0 {TAG}"


# ours: commands carrying our tag, or an earlier install's (no tag; recognised by the boostv2 folder)
ours = lambda c: c.endswith(TAG) or any(f"boostv2/hooks/{n}" in c for n in [*HOOKS, *OLD])

# strip our previous install first, so re-running updates paths and options cleanly
pre = s.get("hooks", {}).get("PreToolUse", [])
for g in pre:
    g["hooks"] = [h for h in g.get("hooks", []) if not ours(h.get("command", ""))]
pre = [g for g in pre if g["hooks"]]
env = s.get("env", {})
deny = s.get("permissions", {}).get("deny", [])

# Measured 2026-11-25 (Claude Code 2.1.330, logging proxy):
#  - background requests off: a 3-prompt session sent 7 requests (~85K tokens), 4 (~50K) without them;
#    the extra ones were next-prompt suggestions (full context each) and a session-title request
#  - ListAgents denied: ~500 tokens off every request; skill descriptions capped at 200 chars: ~2,900 off every request
ENV = {"CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION": "false", "CLAUDE_CODE_ENABLE_AWAY_SUMMARY": "0",
       "CLAUDE_CODE_DISABLE_TERMINAL_TITLE": "1", "CLAUDE_CODE_DISABLE_AGENT_PROGRESS_SUMMARIES": "1",
       "CLAUDE_CODE_GOAL_CHECKIN_MINUTES": "0"}
SETTINGS = {"idleCompaction": False, "skillListingMaxDescChars": 200,
            "fastModePerSessionOptIn": True}   # /fast lasts one session, so a forgotten fast mode stops costing more
DENY = ["ListAgents"]

# remove what we added before, but only where it still holds our value: a value the user changed since is theirs now
ALL_ENV = {**ENV, "DISABLE_AUTOUPDATER": "1"}
ALL_SETTINGS = {**SETTINGS, "promptCacheTtl": "1h"}
for item in filter(None, ",".join([env.pop(OLD_MARK, ""), env.pop(MARK, "")]).split(",")):
    kind, _, key = item.partition(":")
    if kind == "env" and key in ALL_ENV and env.get(key) == ALL_ENV[key]:
        env.pop(key)
    elif kind == "setting" and key in ALL_SETTINGS and s.get(key) == ALL_SETTINGS[key]:
        s.pop(key)
    elif kind == "deny" and key in deny:
        deny.remove(key)

added = []
if "--background-only" in args:     # leave everything Claude itself sees untouched
    HOOKS, DENY = {}, []
    SETTINGS = {"idleCompaction": False}
if not un:
    pre += [{"matcher": m, "hooks": [{"type": "command", "command": cmd(n)}]} for n, m in HOOKS.items()]
    if "--pin" in args:
        ENV["DISABLE_AUTOUPDATER"] = "1"
    if "--cache-1h" in args:
        SETTINGS["promptCacheTtl"] = "1h"
    for k, v in ENV.items():          # never override a value the user set themselves
        if k not in env:
            env[k] = v
            added.append(f"env:{k}")
    for k, v in SETTINGS.items():
        if k not in s:
            s[k] = v
            added.append(f"setting:{k}")
    for r in DENY:
        if r not in deny:
            deny.append(r)
            added.append(f"deny:{r}")
    if added:
        env[MARK] = ",".join(added)
if deny:
    s.setdefault("permissions", {})["deny"] = deny
elif "permissions" in s:
    s["permissions"].pop("deny", None)
    if not s["permissions"]:
        del s["permissions"]

if pre:
    s.setdefault("hooks", {})["PreToolUse"] = pre
elif "hooks" in s:
    s["hooks"].pop("PreToolUse", None)
for k in ("hooks", "env"):
    if k in s and not s[k]:
        del s[k]
if env:
    s["env"] = env

if json.dumps(s, sort_keys=True) != before:
    f.parent.mkdir(parents=True, exist_ok=True)
    if f.exists():
        bak = f.with_suffix(f".json.claude-lean-{time.strftime('%Y%m%d-%H%M%S')}.bak")
        shutil.copy2(f, bak)
        print(f"backup {bak}")
    f.write_text(json.dumps(s, indent=2) + "\n")
print(("removed Claude Lean from" if un else "installed Claude Lean in") + f" {f}" + (f" (+ {', '.join(added)})" if added else ""))
PY
