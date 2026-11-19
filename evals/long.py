#!/usr/bin/env python3
"""Long-session eval: all tasks in tasks.json, one after another, on one copy of fixture/.

    python3 evals/long.py --reps 2

plain:  one continuous session (each task resumes the last), so the context keeps growing.
lean:    a fresh session per task (what /clear does) plus the reader agent.
filter: lean + the output filter hook (hooks/squeeze_hook.py).
Each session stops at --budget dollars (default 2); tasks past the cap count as failed.
Each task is checked right after it runs. Results: evals/long-results.jsonl."""
import argparse
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from run import CLAUDE, HERE, TOOLS, reader_json


SQUEEZE = json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
    {"type": "command", "command": f"python3 {HERE.parent / 'hooks' / 'squeeze_hook.py'}"}]}]}})


def session(arm, rep, model, budget):
    d = HERE / "runs" / f"long-{arm}-{rep}"
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(HERE / "fixture", d)
    sid, out, spent = None, [], 0.0
    for step, task in enumerate(json.loads((HERE / "tasks.json").read_text())):
        left = budget - spent
        if left < 0.01:
            row = {"arm": arm, "rep": rep, "step": step, "task": task["id"], "pass": False, "usd": 0, "prompt": 0,
                   "seconds": 0, "error": "budget", "models": None}
            print(json.dumps({k: row[k] for k in ("arm", "rep", "step", "task", "pass", "error")}), flush=True)
            out.append(row)
            continue
        cmd = [CLAUDE, "-p", task["prompt"], "--output-format", "json", "--allowedTools", TOOLS,
               "--max-budget-usd", f"{left:.2f}", "--model", model]
        if arm == "plain" and sid:
            cmd += ["--resume", sid]
        if arm in ("lean", "filter"):
            cmd += ["--agents", reader_json(), "--no-session-persistence"]
        if arm == "filter":
            cmd += ["--settings", SQUEEZE]
        t0 = time.time()
        p = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=900)
        try:
            r = json.loads(p.stdout.splitlines()[0])
        except (ValueError, IndexError):
            r = {"is_error": True}
        sid = r.get("session_id") or sid
        ok = json.loads(subprocess.run([sys.executable, str(HERE / "check.py"), task["id"], str(d)],
                                       capture_output=True, text=True).stdout)["pass"]
        u = r.get("usage") or {}
        spent += r.get("total_cost_usd") or 0
        row = {"arm": arm, "rep": rep, "step": step, "task": task["id"], "pass": ok, "usd": r.get("total_cost_usd"),
               "prompt": u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("input_tokens", 0),
               "seconds": round(time.time() - t0, 1), "error": r.get("is_error"), "models": r.get("modelUsage")}
        print(json.dumps({k: row[k] for k in ("arm", "rep", "step", "task", "pass", "usd", "prompt")}), flush=True)
        out.append(row)
        (d / "ANSWER.txt").unlink(missing_ok=True)
        (d / "ANSWER.json").unlink(missing_ok=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--budget", type=float, default=2.0, help="dollar cap per session")
    ap.add_argument("--arms", default="plain,lean,filter")
    ap.add_argument("--out", default="long-results.jsonl")
    a = ap.parse_args()
    jobs = [(arm, r) for r in range(a.reps) for arm in a.arms.split(",")]
    with ThreadPoolExecutor(len(jobs)) as ex, (HERE / a.out).open("a") as f:
        for rows in ex.map(lambda j: session(*j, a.model, a.budget), jobs):
            for row in rows:
                f.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    main()
