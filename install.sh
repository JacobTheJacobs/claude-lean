#!/usr/bin/env bash
# Claude Lean installer. Wires everything into ~/.claude for you (backup first, idempotent).
#   ./install.sh               lean skill + long-session guard + output budget + output filter + cache guard +
#                              web search, read, MCP, retry-loop and compaction hooks
#   ./install.sh --reader      also the Haiku reader agent (adds ~550 tokens per request; pays off on bulky lookups)
#   ./install.sh --no-filter   skip the output filter (hooks/squeeze_hook.py)
#   ./install.sh --no-terse    skip the output rules (smallest change, 1-3 line answers); keeps the no-subagent-fan-out rule
#   ./install.sh --no-deny     let Claude read node_modules, minified files and source maps (denied by default: they
#                              are large, generated, and almost never what Claude needs)
#   ./install.sh --no-statusline  don't add the cost status line (it's only added when you have no status line)
#   ./install.sh --no-slim     keep Claude Code's Artifact, Workflow, cron, background-task and advisor tools, the
#                              Explore/Plan agents, the ListAgents tool and full skill descriptions in every request
#   ./install.sh --dry-run     show every change, write nothing
#   ./install.sh --uninstall   remove everything Claude Lean added
# Env: CLAUDE_DIR (default $CLAUDE_CONFIG_DIR, else ~/.claude), LEAN_DAY_USD=N adds the daily dollar cap hook (N dollars per day).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 - "$HERE" "$@" <<'PY'
import json, os, re, shlex, shutil, sys, time
from pathlib import Path

here, args = Path(sys.argv[1]), set(sys.argv[2:])
unknown = args - {"--reader", "--no-filter", "--no-slim", "--no-terse", "--no-deny", "--no-statusline", "--dry-run", "--uninstall", "-h", "--help"}
if unknown or args & {"-h", "--help"}:
    print(open(here / "install.sh").read().split("set -euo")[0].replace("# ", "").strip())
    sys.exit(1 if unknown else 0)
dry, un = "--dry-run" in args, "--uninstall" in args
cdir = Path(os.environ.get("CLAUDE_DIR") or os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
settings_f = cdir / "settings.json"
py = lambda p: f"python3 {shlex.quote(str(here / p))}"    # quoted: home folders can contain spaces

hooks = {"UserPromptSubmit": [("", py("hooks/session_guard.py"))],
         "SessionStart": [("", py("hooks/handoff_hook.py"))],
         # output budget: a few standing rules so Claude writes less (output costs several times input)
         "PreToolUse": [("Edit|Write|MultiEdit", py("hooks/cache_guard.py")),
                        ("WebSearch|WebFetch", py("hooks/web_guard.py")),    # web search budget: ~$0.07 per search
                        ("Read|Bash", py("hooks/read_guard.py"))],  # large-file read or cat: ask for a range first
         "PostToolUse": [("Read", py("hooks/read_guard.py")),       # identical re-read -> one-line note
                         ("mcp__.*", py("hooks/mcp_compact.py"))],  # MCP JSON: drop nulls/empties, minify
         "PostToolUseFailure": [("Bash|Edit|MultiEdit", py("hooks/loop_guard.py"))],  # same failure 3x -> change approach
         "PreCompact": [("", py("hooks/compact_hook.py"))]}         # what the compaction summary keeps
# --no-terse keeps only the no-subagent-fan-out rule (slim alone made Claude fan out to 9-10 subagents)
hooks["SessionStart"].append(("startup|clear|compact", ("LEAN_TERSE=0 " if "--no-terse" in args else "") + py("hooks/terse_hook.py")))
if "--no-filter" not in args:
    hooks["PreToolUse"].append(("Bash", py("hooks/squeeze_hook.py")))
if os.environ.get("LEAN_DAY_USD"):
    cap = float(os.environ["LEAN_DAY_USD"])          # baked into the hook command: hooks don't see your shell env
    hooks["UserPromptSubmit"].append(("", f"LEAN_DAY_USD={cap:g} " + py("hooks/budget.py")))
allow = [f"Bash({py('tools/squeeze.py')} *)"] if "--no-filter" not in args else []
DENY = ["Read(**/node_modules/**)", "Read(**/*.min.js)", "Read(**/*.min.css)", "Read(**/*.map)"]
DENY_MARK = "CLAUDE_LEAN_DENY"            # env key recording which deny rules we added, so uninstall removes only those
sys.path.insert(0, str(here / "tools"))
import slim                       # SLIM switches and how they are added/removed (also /lean:slim in the plugin)
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
if bad := slim.bad_shape(s):
    sys.exit(f"{settings_f}: {bad}; fix it first.")
before = json.dumps(s, sort_keys=True)
# ours: this copy's files, or the same file in another Lean folder (.claude-lean, claude-lean, a claude-boost clone)
# left by an earlier install; else every hook runs twice and the status line points at the old copy
names = "|".join(re.escape(p.name) for p in (here / "hooks").glob("*.py"))
def mine(cmd, sub=f"hooks/(?:{names})"):
    return (str(here) in cmd and re.search(sub, cmd) is not None) or \
        re.search(rf"(?:^|[/'\"])\.?claude-(?:lean|boost)/{sub}\b", cmd) is not None

# always strip our old entries first, so re-running updates paths and options cleanly
for ev, groups in list(s.get("hooks", {}).items()):
    for g in groups:
        g["hooks"] = [h for h in g.get("hooks", []) if not mine(h.get("command", ""))]
    s["hooks"][ev] = [g for g in groups if g["hooks"]]
    if not s["hooks"][ev]:
        del s["hooks"][ev]
if "hooks" in s and not s["hooks"]:
    del s["hooks"]
slim.strip(s)
ours = (s.get("env", {}).pop(DENY_MARK, "") or "").split("|")
if "env" in s and not s["env"]:
    del s["env"]
if mine(json.dumps(s.get("statusLine", "")), r"tools/statusline\.py"):
    del s["statusLine"]                     # ours: re-added below unless uninstalling or --no-statusline
perm = s.get("permissions", {})
if "deny" in perm:
    perm["deny"] = [r for r in perm["deny"] if r not in ours]
    if not perm["deny"]:
        del perm["deny"]
if "allow" in perm:
    perm["allow"] = [r for r in perm["allow"] if not mine(r, r"tools/squeeze\.py")]
    if not perm["allow"]:
        del perm["allow"]
if "permissions" in s and not s["permissions"]:
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
        if (added := slim.add(s)):
            say(f"slim   {', '.join(added)}")
    for r in allow:
        s.setdefault("permissions", {}).setdefault("allow", []).append(r)
        say(f"allow  {r}")
    if "--no-statusline" not in args and "statusLine" not in s:
        s["statusLine"] = {"type": "command", "command": py("tools/statusline.py")}
        say("status line: session cost, context, cache hit rate")
    if "--no-deny" not in args:
        have = s.setdefault("permissions", {}).setdefault("deny", [])
        added = [r for r in DENY if r not in have]
        have.extend(added)
        if added:
            s.setdefault("env", {})[DENY_MARK] = "|".join(added)
            say(f"deny   {', '.join(added)}")

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
            dst.write_text(src.read_text().replace("${CLAUDE_PLUGIN_ROOT}", str(here)))
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
