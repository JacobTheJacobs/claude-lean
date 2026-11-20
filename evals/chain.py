#!/usr/bin/env python3
"""Dependent-task eval: 6 short follow-up prompts that build one feature step by step, like real work.

    python3 evals/chain.py --reps 3

Each prompt is terse and leans on the earlier ones ("now add...", "make it survive save/load"), and one convention is
set only in step 1 (prices are integer cents) and needed again in step 6. So a fresh session has to recover it from the
code, and a session that forgets it fails.

plain:    one continuous session (each step resumes the last)
fresh:    a new session per step, nothing carried over (what /clear alone does)
handoff:  a new session per step, but before each new one the previous session saves a handoff note
          (skills/handoff) and hooks/handoff_hook.py loads it at start (what "handoff" + /clear does)
After every step a hidden test checks that step and everything before it (regressions count as a fail).
Each session stops at --budget dollars (default 2). Results: evals/chain-results.jsonl."""
import argparse
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from run import CLAUDE, HERE, ISOLATE, ROOT, step_usd, RUNS

TOOLS = "Read,Edit,Write,Grep,Glob,Skill,Bash(python3 *),Bash(ls *),Bash(cat *)"
HANDOFF_HOOK = json.dumps({"hooks": {"SessionStart": [{"hooks": [
    {"type": "command", "command": f"python3 {ROOT / 'hooks' / 'handoff_hook.py'}"}]}]}})
STEPS = [
    "Create inventory.py with an Inventory class: add(name, qty, price) and total_value(). Prices are integer cents, "
    "never floats. Adding a name that already exists increases its qty and keeps the newest price.",
    "Now add remove(name, qty). Taking more than is in stock must raise ValueError and change nothing.",
    "Add low_stock(threshold): the names whose qty is below it, sorted.",
    "Make it persist: inv.save(path) writes JSON, and Inventory.load(path) returns a new Inventory with the same items.",
    "Keep an audit trail: a list attribute `log` of (action, name, qty) tuples, action 'add' or 'remove', one per call. "
    "It has to survive save/load too.",
    "Last thing: summary() returns '<number of distinct items> items, total $<dollars with 2 decimals>', "
    "for example '3 items, total $12.50'.",
]

CHECK = r'''
import importlib, json, os, sys, tempfile
sys.path.insert(0, os.getcwd())
step = int(sys.argv[1])
ok = True
def need(c):
    global ok
    ok = ok and bool(c)
try:
    m = importlib.import_module("inventory")
    I = m.Inventory
    inv = I()
    inv.add("apple", 3, 150); inv.add("pear", 2, 99); inv.add("apple", 2, 175)
    need(inv.total_value() == 5 * 175 + 2 * 99)
    if step >= 2:
        inv.remove("pear", 1)
        try:
            inv.remove("apple", 99); need(False)
        except ValueError:
            pass
        need(inv.total_value() == 5 * 175 + 1 * 99)
    if step >= 3:
        inv.add("fig", 1, 300)
        need(inv.low_stock(2) == ["fig", "pear"])
    if step >= 4:
        p = os.path.join(tempfile.mkdtemp(), "inv.json")
        inv.save(p)
        inv2 = I.load(p)
        need(inv2.total_value() == inv.total_value() and inv2.low_stock(2) == inv.low_stock(2))
    if step >= 5:
        want = [("add", "apple", 3), ("add", "pear", 2), ("add", "apple", 2), ("remove", "pear", 1), ("add", "fig", 1)]
        need([tuple(x) for x in inv.log] == want)
        need([tuple(x) for x in I.load(p).log] == want)
    if step >= 6:
        need(inv.summary() == "3 items, total $%.2f" % ((5 * 175 + 99 + 300) / 100))
except Exception as e:
    ok = False
print(json.dumps({"pass": ok}))
'''


def call(cmd, d):
    p = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=900)
    try:
        return json.loads(p.stdout.splitlines()[0])
    except (ValueError, IndexError):
        return {"is_error": True}


def session(arm, rep, model, budget):
    d = RUNS / f"chain-{arm}-{rep}"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    (d / "check_step.py").write_text(CHECK)
    if arm == "handoff":   # project-level skill: user skills are not loaded under ISOLATE
        sk = d / ".claude" / "skills" / "handoff" / "SKILL.md"
        sk.parent.mkdir(parents=True)
        sk.write_text((ROOT / "skills" / "handoff" / "SKILL.md").read_text().replace("LEAN_TOOLS", str(ROOT / "tools")))
    sid, out, spent, total = None, [], 0.0, 0.0
    base = ["--output-format", "json", "--model", model, "--allowedTools", TOOLS, *ISOLATE]
    for step, prompt in enumerate(STEPS, 1):
        left = budget - spent
        row = {"arm": arm, "rep": rep, "step": step}
        if left < 0.01:
            out.append({**row, "pass": False, "usd": 0, "error": "budget"})
            continue
        cmd = [CLAUDE, "-p", prompt, *base, "--max-budget-usd", f"{left:.2f}"]
        resumed = arm == "plain" and bool(sid)
        if resumed:
            cmd += ["--resume", sid]
        if arm == "handoff":
            cmd += ["--settings", HANDOFF_HOOK]
        t0 = time.time()
        r = call(cmd, d)
        usd, total = step_usd(r, resumed, total)
        sid = r.get("session_id") or sid
        if arm == "handoff" and step < len(STEPS) and r.get("session_id"):
            # the user says "handoff" before /clear: same session writes the note for the next one
            h = call([CLAUDE, "-p", "handoff", *base, "--resume", r["session_id"],
                      "--max-budget-usd", f"{max(left - usd, 0.01):.2f}"], d)
            usd += step_usd(h, True, r.get("total_cost_usd") or 0)[0]   # h's total includes the step itself
        spent += usd
        ok = json.loads(subprocess.run([sys.executable, "check_step.py", str(step)], cwd=d,
                                       capture_output=True, text=True).stdout or '{"pass": false}')["pass"]
        out.append({**row, "pass": ok, "usd": usd, "seconds": round(time.time() - t0, 1), "error": r.get("is_error")})
        print(json.dumps(out[-1]), flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--budget", type=float, default=2.0)
    ap.add_argument("--arms", default="plain,fresh,handoff")
    a = ap.parse_args()
    jobs = [(arm, r) for r in range(a.reps) for arm in a.arms.split(",")]
    with ThreadPoolExecutor(min(len(jobs), 6)) as ex, (HERE / "chain-results.jsonl").open("a") as f:
        for rows in ex.map(lambda j: session(*j, a.model, a.budget), jobs):
            for row in rows:
                f.write(json.dumps({**row, "model": a.model, "at": time.strftime("%Y-%m-%d")}) + "\n")
    import collections
    by = collections.defaultdict(list)
    rows = [json.loads(l) for l in (HERE / "chain-results.jsonl").read_text().splitlines()
            if json.loads(l).get("at") == time.strftime("%Y-%m-%d") and json.loads(l).get("model") == a.model]
    for r in rows:
        by[r["arm"]].append(r)
    print(f"\n{'arm':<8} {'passed':>8} {'final step':>11} {'$ per session':>14}")
    for arm in a.arms.split(","):
        rs = by[arm]
        reps = len({r["rep"] for r in rs}) or 1
        final = [r for r in rs if r["step"] == len(STEPS)]
        print(f"{arm:<8} {sum(r['pass'] for r in rs):>3}/{len(rs):<4} {sum(r['pass'] for r in final):>5}/{len(final):<5} "
              f"{sum(r['usd'] or 0 for r in rs) / reps:>14.4f}")


if __name__ == "__main__":
    main()
