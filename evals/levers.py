#!/usr/bin/env python3
"""Measure Claude Code cost levers on the 10-task long session (tasks.json), graded by check.py.

    python3 evals/levers.py --reps 2

Arms (name: model, session style, extra flags/env):
  haiku            Haiku 5.5, one continuous session
  haiku-compact    same, auto-compact at ~50K tokens (CLAUDE_CODE_AUTO_COMPACT_WINDOW + CLAUDE_AUTOCOMPACT_PCT_OVERRIDE)
  haiku-fresh      Haiku 5.5, fresh session per task (Claude Lean)
  sonnet-fresh     Sonnet 5.5, fresh session per task
  sonnet-advisor   same + --advisor claude-opus-5-5
  opus-fresh       Opus 5.5, fresh session per task (effort from your settings)
  opus-subhaiku    same, subagents on Haiku 5.5 (CLAUDE_CODE_SUBAGENT_MODEL)
  opus-low         same, --effort low
All arms run with Claude Lean's slim switches (advisor left on). Every session is capped at --budget dollars (default 2). Results: evals/levers-results.jsonl."""
import argparse
import collections
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from run import CLAUDE, HERE, TOOLS

SLIM = {k: "1" for k in ("CLAUDE_CODE_DISABLE_ARTIFACT", "CLAUDE_CODE_DISABLE_WORKFLOWS",
                         "CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS",
                         "CLAUDE_CODE_DISABLE_CRON")}          # Claude Lean's default; advisor stays available
COMPACT = {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "100000", "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50"}
ARMS = {
    "haiku": ("claude-haiku-5-5", False, [], {}),
    "haiku-compact": ("claude-haiku-5-5", False, [], COMPACT),
    "haiku-fresh": ("claude-haiku-5-5", True, [], {}),
    "sonnet-fresh": ("claude-sonnet-5-5", True, [], {}),
    "sonnet-advisor": ("claude-sonnet-5-5", True, ["--advisor", "claude-opus-5-5"], {}),
    "opus-fresh": ("claude-opus-5-5", True, [], {}),
    "opus-subhaiku": ("claude-opus-5-5", True, [], {"CLAUDE_CODE_SUBAGENT_MODEL": "claude-haiku-5-5"}),
    "opus-low": ("claude-opus-5-5", True, ["--effort", "low"], {}),
}


def session(arm, rep, budget):
    model, fresh, extra, env = ARMS[arm]
    d = HERE / "runs" / f"levers-{arm}-{rep}"
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(HERE / "fixture", d)
    sid, rows, spent = None, [], 0.0
    for step, task in enumerate(json.loads((HERE / "tasks.json").read_text())):
        row = {"arm": arm, "rep": rep, "step": step, "task": task["id"]}
        left = budget - spent
        if left < 0.01:
            rows.append({**row, "pass": False, "usd": 0, "error": "budget"})
            continue
        cmd = [CLAUDE, "-p", task["prompt"], "--output-format", "json", "--model", model, "--allowedTools", TOOLS,
               "--max-budget-usd", f"{left:.2f}", *extra]
        if fresh:
            cmd += ["--no-session-persistence"]
        elif sid:
            cmd += ["--resume", sid]
        t0 = time.time()
        p = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=900, env={**os.environ, **SLIM, **env})
        try:
            r = json.loads(p.stdout.splitlines()[0])
        except (ValueError, IndexError):
            r = {"is_error": True, "stderr": p.stderr[-300:]}
        sid = r.get("session_id") or sid
        usd = r.get("total_cost_usd") or 0
        spent += usd
        ok = json.loads(subprocess.run([sys.executable, str(HERE / "check.py"), task["id"], str(d)],
                                       capture_output=True, text=True).stdout)["pass"]
        rows.append({**row, "pass": ok, "usd": usd, "seconds": round(time.time() - t0, 1), "error": r.get("is_error"),
                     "models": {k: round(v.get("costUSD", 0), 5) for k, v in (r.get("modelUsage") or {}).items()},
                     "stderr": r.get("stderr")})
        print(json.dumps({k: rows[-1][k] for k in ("arm", "rep", "step", "pass", "usd")}), flush=True)
        (d / "ANSWER.txt").unlink(missing_ok=True)
        (d / "ANSWER.json").unlink(missing_ok=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--budget", type=float, default=2.0)
    ap.add_argument("--arms", default=",".join(ARMS))
    a = ap.parse_args()
    jobs = [(arm, r) for r in range(a.reps) for arm in a.arms.split(",")]
    with ThreadPoolExecutor(len(jobs)) as ex:
        rows = [x for rs in ex.map(lambda j: session(*j, a.budget), jobs) for x in rs]
    with (HERE / "levers-results.jsonl").open("a") as f:
        for r in rows:
            f.write(json.dumps({**r, "at": time.strftime("%Y-%m-%d")}) + "\n")
    by = collections.defaultdict(list)
    for r in rows:
        by[r["arm"]].append(r)
    print(f"\n{'arm':<15} {'passed':>7} {'$ per session':>14}  by model")
    for arm in a.arms.split(","):
        rs = by[arm]
        reps = len({r["rep"] for r in rs})
        m = collections.Counter()
        for r in rs:
            m.update(r.get("models") or {})
        print(f"{arm:<15} {sum(r['pass'] for r in rs):>3}/{len(rs):<3} {sum(r.get('usd') or 0 for r in rs) / reps:>14.3f}  "
              + ", ".join(f"{k.replace('claude-', '')} ${v / reps:.3f}" for k, v in m.items()))


if __name__ == "__main__":
    main()
