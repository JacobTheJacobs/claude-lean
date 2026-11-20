#!/usr/bin/env python3
"""Claude Lean vs other token optimizers, on the same graded tasks, with per-step cost accounting.

    python3 evals/compare.py --arms plain,lean,lite,caveman,rtk --rtk-home DIR --caveman-dir DIR --reps 2

Suites (all graded by script):
  short:  5 quick jobs, each a single fresh call (bug fix, new function, code lookup, log count, find a definition)
  long:   the 10 tasks of tasks.json in ONE continuous session per arm (each step resumes the last)
  noisy:  run a 400-test pytest suite / a noisy `make` build and name the one failure, single call each
Arms (every arm: --setting-sources project,local, so this machine's own settings never leak in):
  plain    Claude Code, nothing added
  lean     what `claude-lean init` installs that touches requests: slim env switches + the output filter hook
  lite     `claude-lean lite`: core tools only, no MCP, no skills, slim env
  caveman  JuliusBrussee/caveman Claude Code plugin, loaded with --plugin-dir (its hooks write only its own flag files)
  rtk      rtk-ai/rtk as `rtk init -g` set it up in --rtk-home: its hooks (run with HOME=--rtk-home) and its
           CLAUDE.md/RTK.md instructions (appended to the system prompt, as a global CLAUDE.md would be)
Each session stops at --budget dollars (default 2). Results: evals/compare-results.jsonl, summary printed."""
import argparse
import collections
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from run import CLAUDE, HERE, ISOLATE, ROOT, RUNS, TOOLS, step_usd
from vs import NOISY

SLIM = {f"CLAUDE_CODE_DISABLE_{k}": "1" for k in
        ("ARTIFACT", "WORKFLOWS", "GIT_INSTRUCTIONS", "BACKGROUND_TASKS", "CRON", "ADVISOR_TOOL")}
FILTER = {"PreToolUse": [{"matcher": "Bash", "hooks": [
    {"type": "command", "command": f"python3 {ROOT / 'hooks' / 'squeeze_hook.py'}"}]}]}
LITE = ["--tools", "Read,Edit,Write,Bash,Grep,Glob,Agent,TodoWrite", "--strict-mcp-config",
        "--mcp-config", '{"mcpServers":{}}', "--disable-slash-commands"]
SHORT = ["bugfix", "feature", "lookup", "logcount", "whereis"]


def rtk_setup(home):
    """Hooks and instructions that `rtk init -g` wrote into home/.claude, re-pointed to keep using that HOME."""
    c = home / ".claude"
    s = json.loads((c / "settings.json").read_text())
    binp = home / ".local" / "bin"
    prefix = f"HOME={shlex.quote(str(home))} PATH={shlex.quote(str(binp))}:$PATH "
    for groups in s.get("hooks", {}).values():
        for g in groups:
            for h in g.get("hooks", []):
                if h.get("type") == "command":
                    h["command"] = prefix + h["command"]
    rules = "\n\n".join(p.read_text() for p in (c / "CLAUDE.md", c / "RTK.md") if p.is_file())
    return s.get("hooks", {}), rules


def arm_args(arm, a, extra_allow=""):
    """(extra CLI args, extra env) for one arm."""
    allow = TOOLS + (f",{extra_allow}" if extra_allow else "")
    args, env, hooks = ["--allowedTools", allow, *ISOLATE], {}, {}
    if arm in ("lean", "lite"):
        env.update(SLIM)
    if arm == "lean":
        hooks = FILTER
    if arm == "lite":
        args += LITE
    if arm == "caveman":
        args += ["--plugin-dir", str(a.caveman_dir)]
    if arm == "rtk":
        hooks, rules = a.rtk
        # the rewritten `rtk ...` commands run in Claude's own shell, so rtk must be on its PATH; telemetry stays off
        env.update({"PATH": f"{a.rtk_home.resolve() / '.local' / 'bin'}:{os.environ['PATH']}", "RTK_TELEMETRY_DISABLED": "1"})
        args[1] += ",Bash(rtk *)"
        if rules:
            args += ["--append-system-prompt", rules]
    if hooks:
        args += ["--settings", json.dumps({"hooks": hooks})]
    return args, env


def call(cmd, cwd, env):
    t0 = time.time()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=900, env={**os.environ, **env})
    try:
        r = json.loads(p.stdout.splitlines()[0])
    except (ValueError, IndexError):
        r = {"is_error": True}
    u = r.get("usage") or {}
    return r, round(time.time() - t0, 1), (u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                                           + u.get("input_tokens", 0))


def graded(task_id, d):
    out = subprocess.run([sys.executable, str(HERE / "check.py"), task_id, str(d)], capture_output=True, text=True)
    return json.loads(out.stdout or '{"pass": false}')["pass"]


def short(arm, rep, a):
    tasks = {t["id"]: t for t in json.loads((HERE / "tasks.json").read_text())}
    rows = []
    for tid in SHORT:
        d = RUNS / f"cmp-short-{arm}-{tid}-{rep}"
        shutil.rmtree(d, ignore_errors=True)
        shutil.copytree(HERE / "fixture", d)
        args, env = arm_args(arm, a)
        r, sec, prompt = call([CLAUDE, "-p", tasks[tid]["prompt"], "--output-format", "json", "--model", a.model,
                               "--no-session-persistence", "--max-budget-usd", f"{a.budget:.2f}", *args], d, env)
        rows.append({"suite": "short", "arm": arm, "rep": rep, "step": 0, "task": tid, "pass": graded(tid, d),
                     "usd": r.get("total_cost_usd") or 0, "seconds": sec, "prompt": prompt, "error": r.get("is_error")})
        print(json.dumps(rows[-1]), flush=True)
    return rows


def long(arm, rep, a):
    d = RUNS / f"cmp-long-{arm}-{rep}"
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(HERE / "fixture", d)
    sid, rows, spent, total = None, [], 0.0, 0.0
    for step, task in enumerate(json.loads((HERE / "tasks.json").read_text())):
        row = {"suite": "long", "arm": arm, "rep": rep, "step": step, "task": task["id"]}
        left = a.budget - spent
        if left < 0.01:
            rows.append({**row, "pass": False, "usd": 0, "error": "budget"})
            continue
        args, env = arm_args(arm, a)
        resumed = bool(sid)
        cmd = [CLAUDE, "-p", task["prompt"], "--output-format", "json", "--model", a.model,
               "--max-budget-usd", f"{left:.2f}", *args] + (["--resume", sid] if resumed else [])
        r, sec, prompt = call(cmd, d, env)
        sid = r.get("session_id") or sid
        usd, total = step_usd(r, resumed, total)
        spent += usd
        rows.append({**row, "pass": graded(task["id"], d), "usd": usd, "usd_reported": r.get("total_cost_usd"),
                     "seconds": sec, "prompt": prompt, "error": r.get("is_error")})
        print(json.dumps(rows[-1]), flush=True)
        for f in ("ANSWER.txt", "ANSWER.json"):
            (d / f).unlink(missing_ok=True)
    return rows


def noisy(arm, rep, a):
    rows = []
    for task in NOISY:
        d = RUNS / f"cmp-{task['id']}-{arm}-{rep}"
        task["build"](d)
        args, env = arm_args(arm, a, task["allow"])
        r, sec, prompt = call([CLAUDE, "-p", task["prompt"], "--output-format", "json", "--model", a.model,
                               "--no-session-persistence", "--max-budget-usd", f"{a.budget:.2f}", *args], d, env)
        f = d / "ANSWER.txt"
        ok = f.is_file() and f.read_text().strip() == task["answer"]
        rows.append({"suite": "noisy", "arm": arm, "rep": rep, "step": 0, "task": task["id"], "pass": ok,
                     "usd": r.get("total_cost_usd") or 0, "seconds": sec, "prompt": prompt, "error": r.get("is_error")})
        print(json.dumps(rows[-1]), flush=True)
    return rows


def summary(rows, arms):
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["suite"], r["arm"])].append(r)
    for suite, unit in (("short", "task"), ("long", "session"), ("noisy", "task")):
        if not any(s == suite for s, _ in by):
            continue
        print(f"\n{suite:<6} {'arm':<9} {'passed':>8} {'$ per ' + unit:>16}")
        base = None
        for arm in arms:
            rs = by.get((suite, arm))
            if not rs:
                continue
            n = len({r["rep"] for r in rs}) if suite == "long" else len(rs)
            usd = sum(r["usd"] or 0 for r in rs) / n
            base = base if base is not None else (usd if arm == "plain" else None)
            rel = f"{100 * (usd / base - 1):+.0f}%" if base and arm != "plain" else ""
            print(f"{'':<6} {arm:<9} {sum(r['pass'] for r in rs):>3}/{len(rs):<4} {usd:>16.4f}  {rel}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="plain,lean,lite,caveman,rtk")
    ap.add_argument("--suites", default="short,long,noisy")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--budget", type=float, default=2.0)
    ap.add_argument("--rtk-home", type=Path)
    ap.add_argument("--caveman-dir", type=Path)
    a = ap.parse_args()
    arms, suites = a.arms.split(","), a.suites.split(",")
    if "rtk" in arms:
        if not (a.rtk_home and (a.rtk_home / ".claude" / "settings.json").is_file()):
            sys.exit("rtk: pass --rtk-home, the HOME where `rtk init -g` ran (see the README's comparison section)")
        a.rtk = rtk_setup(a.rtk_home.resolve())
    if "caveman" in arms and not (a.caveman_dir and (a.caveman_dir / ".claude-plugin" / "plugin.json").is_file()):
        sys.exit("caveman: pass --caveman-dir, a checkout of github.com/JuliusBrussee/caveman")
    run = {"short": short, "long": long, "noisy": noisy}
    jobs = [(run[s], arm, rep) for rep in range(a.reps) for arm in arms for s in suites]
    with ThreadPoolExecutor(min(len(jobs), 8)) as ex:
        rows = [r for rs in ex.map(lambda j: j[0](j[1], j[2], a), jobs) for r in rs]
    with (HERE / "compare-results.jsonl").open("a") as f:
        for r in rows:
            f.write(json.dumps({**r, "model": a.model, "at": time.strftime("%Y-%m-%d")}) + "\n")
    summary(rows, arms)


if __name__ == "__main__":
    main()
