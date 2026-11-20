#!/usr/bin/env python3
"""Output-filter eval: a repo with 400 passing tests and 1 failing one, task "run the suite, find the failure".

    python3 evals/filter.py --reps 3

lean:    fresh session + reader agent.   filter: same + hooks/squeeze_hook.py.
Pass = ANSWER.txt names the failing test. Results: evals/filter-results.jsonl."""
import argparse
import json
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

from run import CLAUDE, HERE, ISOLATE, TOOLS, reader_json, RUNS
from long import SQUEEZE

PROMPT = ("Run the test suite with `pytest -v`. Exactly one test fails. Write its node id "
          "(like tests/test_x.py::test_name) to ANSWER.txt, nothing else.")
BAD = "tests/test_calc_07.py::test_sum_33"


def build(d):
    shutil.rmtree(d, ignore_errors=True)
    (d / "tests").mkdir(parents=True)
    (d / "pytest.ini").write_text("[pytest]\npythonpath = .\n")
    (d / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    for f in range(10):
        body = ["from calc import add\n"]
        for t in range(40):
            want = f + t if (f, t) != (7, 33) else f + t + 1
            body.append(f"\ndef test_sum_{t:02d}():\n    assert add({f}, {t}) == {want}\n")
        (d / "tests" / f"test_calc_{f:02d}.py").write_text("".join(body))


def one(arm, rep, model):
    d = RUNS / f"filter-{arm}-{rep}"
    build(d)
    cmd = [CLAUDE, "-p", PROMPT, "--output-format", "json", "--no-session-persistence", "--model", model,
           "--allowedTools", TOOLS + ",Bash(pytest *)", "--max-budget-usd", "2", "--agents", reader_json(), *ISOLATE]
    if arm == "filter":
        cmd += ["--settings", SQUEEZE]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=900)
    try:
        r = json.loads(p.stdout.splitlines()[0])
    except (ValueError, IndexError):
        r = {"is_error": True}
    a = d / "ANSWER.txt"
    ok = a.is_file() and a.read_text().strip() == BAD
    u = r.get("usage") or {}
    row = {"arm": arm, "rep": rep, "pass": ok, "usd": r.get("total_cost_usd"), "turns": r.get("num_turns"),
           "prompt": u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("input_tokens", 0),
           "seconds": round(time.time() - t0, 1), "error": r.get("is_error")}
    print(json.dumps(row), flush=True)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--model", default="claude-haiku-5-5")
    a = ap.parse_args()
    jobs = [(arm, r) for r in range(a.reps) for arm in ("lean", "filter")]
    with ThreadPoolExecutor(len(jobs)) as ex, (HERE / "filter-results.jsonl").open("a") as f:
        for row in ex.map(lambda j: one(*j, a.model), jobs):
            f.write(json.dumps(row) + "\n")


if __name__ == "__main__":
    main()
