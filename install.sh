#!/usr/bin/env bash
# Claude Lean installer. Wires everything into ~/.claude for you (backup first, idempotent).
#   ./install.sh               lean skill + long-session guard + output filter + cache guard
#   ./install.sh --reader      also the Haiku reader agent (adds ~550 tokens per request; pays off on bulky lookups)
#   ./install.sh --no-filter   skip the output filter (hooks/squeeze_hook.py)
#   ./install.sh --no-slim     keep Claude Code's Artifact, Workflow, cron, background-task and advisor tools and git
#                              instructions in every request (slim drops ~24K tokens per request: short tasks -32%)
#   ./install.sh --dry-run     show every change, write nothing
#   ./install.sh --uninstall   remove everything Claude Lean added
# Env: CLAUDE_DIR (default ~/.claude), LEAN_DAY_USD=N adds the daily dollar cap hook (N dollars per day).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 - "$HERE" "$@" <<'PY'
import json, os, shlex, shutil, sys, time
from pathlib import Path

here, args = Path(sys.argv[1]), set(sys.argv[2:])
unknown = args - {"--reader", "--no-filter", "--no-slim", "--dry-run", "--uninstall", "-h", "--help"}
if unknown or args & {"-h", "--help"}:
    print(open(here / "install.sh").read().split("set -euo")[0].replace("# ", "").strip())
    sys.exit(1 if unknown else 0)
dry, un = "--dry-run" in args, "--uninstall" in args
cdir = Path(os.environ.get("CLAUDE_DIR", Path.home() / ".claude"))
settings_f = cdir / "settings.json"
py = lambda p: f"python3 {shlex.quote(str(here / p))}"    # quoted: home folders can contain spaces

hooks = {"UserPromptSubmit": [("", py("hooks/session_guard.py"))],
         "SessionStart": [("", py("hooks/handoff_hook.py"))],
         "PreToolUse": [("Edit|Write|MultiEdit", py("hooks/cache_guard.py"))]}
if "--no-filter" not in args:
    hooks["PreToolUse"].append(("Bash", py("hooks/squeeze_hook.py")))
if os.environ.get("LEAN_DAY_USD"):
    cap = float(os.environ["LEAN_DAY_USD"])          # baked into the hook command: hooks don't see your shell env
    hooks["UserPromptSubmit"].append(("", f"LEAN_DAY_USD={cap:g} " + py("hooks/budget.py")))
allow = [f"Bash({py('tools/squeeze.py')} *)"] if "--no-filter" not in args else []
# Slim: Claude Code features most sessions never use, whose definitions ride along in every request.
# Measured per request: Artifact 13.5K, Workflows 8.1K, git instructions 2.4K, background tasks 1.1K, cron 0.3K,
# advisor 0.2K tokens. Your MCP servers, skills, web tools and subagents stay.
SLIM = {k: "1" for k in ("CLAUDE_CODE_DISABLE_ARTIFACT", "CLAUDE_CODE_DISABLE_WORKFLOWS",
                         "CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS",
                         "CLAUDE_CODE_DISABLE_CRON", "CLAUDE_CODE_DISABLE_ADVISOR_TOOL")}
MARK = "CLAUDE_LEAN_SLIM"          # records which env keys we set, so uninstall removes only those
copies = [(here / "skills/lean/SKILL.md", cdir / "skills/lean/SKILL.md"),
          (here / "skills/handoff/SKILL.md", cdir / "skills/handoff/SKILL.md")]
if "--reader" in args:
    copies.append((here / "agents/reader.md", cdir / "agents/reader.md"))

def say(msg):
    print(("[dry-run] " if dry else "") + msg)

try:
    s = json.loads(settings_f.read_text()) if settings_f.exists() else {}
except ValueError:
    sys.exit(f"{settings_f} is not valid JSON; fix it first.")
before = json.dumps(s, sort_keys=True)
mine = lambda cmd: str(here) in cmd and ("/hooks/" in cmd)

# always strip our old entries first, so re-running updates paths and options cleanly
for ev, groups in list(s.get("hooks", {}).items()):
    for g in groups:
        g["hooks"] = [h for h in g.get("hooks", []) if not mine(h.get("command", ""))]
    s["hooks"][ev] = [g for g in groups if g["hooks"]]
    if not s["hooks"][ev]:
        del s["hooks"][ev]
if "hooks" in s and not s["hooks"]:
    del s["hooks"]
env = s.get("env", {})
for k in (env.pop(MARK, "") or "").split(","):
    if k and env.get(k) == "1":
        del env[k]
if "env" in s and not env:
    del s["env"]
perm = s.get("permissions", {})
if "allow" in perm:
    perm["allow"] = [r for r in perm["allow"] if f"{here}/tools/squeeze.py" not in r]
    if not perm["allow"]:
        del perm["allow"]
    if not perm:
        del s["permissions"]

if not un:
    for ev, items in hooks.items():
        for matcher, cmd in items:
            g = {"hooks": [{"type": "command", "command": cmd}]}
            if matcher:
                g = {"matcher": matcher, **g}
            s.setdefault("hooks", {}).setdefault(ev, []).append(g)
            say(f"hook   {ev:<17} {matcher or '*':<20} {cmd.split('/')[-1]}")
    if "--no-slim" not in args:
        env = s.setdefault("env", {})
        added = [k for k in SLIM if k not in env]
        env.update({k: SLIM[k] for k in added})
        if added:
            env[MARK] = ",".join(added)
            say(f"env    {len(added)} slim switches (CLAUDE_CODE_DISABLE_ARTIFACT, _WORKFLOWS, ...)")
    for r in allow:
        s.setdefault("permissions", {}).setdefault("allow", []).append(r)
        say(f"allow  {r}")

if json.dumps(s, sort_keys=True) != before:
    if not dry:
        cdir.mkdir(parents=True, exist_ok=True)
        if settings_f.exists():
            bak = settings_f.with_suffix(f".json.lean-{time.strftime('%Y%m%d-%H%M%S')}.bak")
            shutil.copy2(settings_f, bak)
            print(f"backup {bak}")
        settings_f.write_text(json.dumps(s, indent=2) + "\n")
    say(f"wrote  {settings_f}")

for src, dst in copies:
    if un:
        if dst.exists():
            say(f"remove {dst}")
            if not dry:
                dst.unlink()
                if dst.parent.name in ("lean", "handoff") and not any(dst.parent.iterdir()):
                    dst.parent.rmdir()
    else:
        say(f"copy   {dst}")
        if not dry:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text().replace("LEAN_TOOLS", str(here / "tools")))
if un and (cdir / "agents/reader.md").exists() and "--reader" not in args:
    print(f"left   {cdir / 'agents/reader.md'} (pass --reader to remove it too)")

if not un and os.environ.get("LEAN_VIA_NPX"):
    print("\nDone. Hooks apply to new Claude Code sessions.\n"
          "  savings report:  npx claude-lean report --days 7\n"
          "  filter stats:    npx claude-lean stats\n"
          "  undo:            npx claude-lean uninstall")
elif not un:
    print(f"\nDone. Hooks apply to new Claude Code sessions.\n"
          f"  savings report:  {py('tools/report.py')} --days 7\n"
          f"  filter stats:    {py('tools/squeeze.py')} stats\n"
          f"  undo:            {here}/install.sh --uninstall")
PY
