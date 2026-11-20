#!/usr/bin/env python3
"""Output-filter eval in a long session: 10 fix-and-rerun steps in one session, each running a 400-test suite.

    python3 evals/pileup.py --reps 2

The suite has 10 wrong expected values, one per test file. Step i: run `pytest -v`, fix the failing test in
tests/test_calc_0i.py, write its node id to ANSWER.txt. Every run prints ~410 lines, and in one long session they pile
up: each later request re-sends all of them. This is where the output filter is supposed to pay off.

plain:   one continuous session, nothing added
filter:  the same + hooks/squeeze_hook.py
Pass = the right node id, that test now passes, calc.py untouched. Results: evals/pileup-results.jsonl."""
import argparse
import collections
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from run import CLAUDE, HERE, ISOLATE, step_usd, RUNS
from long import SQUEEZE

TOOLS = "Read,Edit,Write,Grep,Glob,Bash(pytest *),Bash(python3 *),Bash(ls *)"
BAD = {f: (f * 7 + 3) % 40 for f in range(10)}        # the broken test in each file
CALC = "def add(a, b):\n    return a + b\n"


def build(d):
    shutil.rmtree(d, ignore_errors=True)
    (d / "tests").mkdir(parents=True)
    (d / "pytest.ini").write_text("[pytest]\npythonpath = .\n")
    (d / "calc.py").write_text(CALC)
    for f in range(10):
        body = ["from calc import add\n"]
        for t in range(40):
            want = f + t + (1 if t == BAD[f] else 0)
            body.append(f"\ndef test_sum_{t:02d}():\n    assert add({f}, {t}) == {want}\n")
        (d / "tests" / f"test_calc_{f:02d}.py").write_text("".join(body))


def prompt(i):
    return (f"Run the whole suite with `pytest -v`. One test in tests/test_calc_{i:02d}.py fails because its expected "
            f"value is wrong. Fix that test's expected value (do not change calc.py), then write its node id "
            f"(like tests/test_x.py::test_name) to ANSWER.txt, nothing else.")


def check(d, i):
    node = f"tests/test_calc_{i:02d}.py::test_sum_{BAD[i]:02d}"
    a = d / "ANSWER.txt"
    if not a.is_file() or a.read_text().strip() != node or (d / "calc.py").read_text() != CALC:
        return False
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", node], cwd=d, capture_output=True, text=True)
    return r.returncode == 0


def session(arm, rep, model, budget):
    d = RUNS / f"pileup-{arm}-{rep}"
    build(d)
    sid, out, spent, total = None, [], 0.0, 0.0
    for i in range(10):
        left = budget - spent
        row = {"arm": arm, "rep": rep, "step": i}
        if left < 0.01:
            out.append({**row, "pass": False, "usd": 0, "error": "budget"})
            continue
        cmd = [CLAUDE, "-p", prompt(i), "--output-format", "json", "--model", model, "--allowedTools", TOOLS,
               "--max-budget-usd", f"{left:.2f}", *ISOLATE]
        resumed = bool(sid)
        if resumed:
            cmd += ["--resume", sid]
        if arm == "filter":
            cmd += ["--settings", SQUEEZE]
        t0 = time.time()
        p = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=900)
        try:
            r = json.loads(p.stdout.splitlines()[0])
        except (ValueError, IndexError):
            r = {"is_error": True}
        sid = r.get("session_id") or sid
        usd, total = step_usd(r, resumed, total)
        spent += usd
        u = r.get("usage") or {}
        out.append({**row, "pass": check(d, i), "usd": usd, "seconds": round(time.time() - t0, 1),
                    "prompt": u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                    + u.get("input_tokens", 0), "error": r.get("is_error")})
        print(json.dumps(out[-1]), flush=True)
        (d / "ANSWER.txt").unlink(missing_ok=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--budget", type=float, default=2.0)
    ap.add_argument("--arms", default="plain,filter")
    a = ap.parse_args()
    jobs = [(arm, r) for r in range(a.reps) for arm in a.arms.split(",")]
    with ThreadPoolExecutor(len(jobs)) as ex:
        results = list(ex.map(lambda j: session(*j, a.model, a.budget), jobs))
    rows = [r for rs in results for r in rs]
    with (HERE / "pileup-results.jsonl").open("a") as f:
        for r in rows:
            f.write(json.dumps({**r, "model": a.model, "at": time.strftime("%Y-%m-%d")}) + "\n")
    by = collections.defaultdict(list)
    for r in rows:
        by[r["arm"]].append(r)
    print(f"\n{'arm':<7} {'passed':>8} {'$ per session':>14}")
    base = None
    for arm in a.arms.split(","):
        rs = by[arm]
        usd = sum(r["usd"] or 0 for r in rs) / a.reps
        base = base or usd
        print(f"{arm:<7} {sum(r['pass'] for r in rs):>3}/{len(rs):<4} {usd:>14.4f}  {100 * (usd / base - 1):+.0f}%")


if __name__ == "__main__":
    main()
