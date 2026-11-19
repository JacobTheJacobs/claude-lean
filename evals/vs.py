#!/usr/bin/env python3
"""Head to head: plain Claude Code vs JFrog Boost vs Claude Lean vs both, on the same graded tasks.

    # 1. install JFrog Boost into a throwaway HOME (your real ~/.claude is not touched)
    J=/tmp/jfrog-test; mkdir -p $J/home $J/bin
    curl -fsSL https://github.com/jfrog/boost/releases/latest/download/boost-linux-amd64.tar.gz | tar -xz -C $J/bin
    HOME=$J/home $J/bin/boost init --claude --accept-terms
    # 2. run
    python3 evals/vs.py --jfrog-home $J/home --jfrog-bin $J/bin --reps 2

Two suites, both graded by script:
  long:  the 10 tasks of long.py in one sitting (bug fix, feature, 8 lookups over code and a 20K-line log)
  noisy: run a 400-test pytest suite / a noisy `make` build and name the one failure
Arms:
  plain       one continuous session, nothing added
  jfrog       one continuous session + JFrog Boost's Claude Code hooks and rule, as `boost init --claude` set them up
  lean        Claude Lean: fresh session per task + reader agent + output filter
  lean+jfrog  both
Every session is capped at --budget dollars (default 2). JFrog's hooks run with HOME set to --jfrog-home, so its
history and config stay in the throwaway folder. Note JFrog Boost sends usage metadata to JFrog (their README).
Results: evals/vs-results.jsonl; summary printed at the end."""
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

from run import CLAUDE, HERE, TOOLS, reader_json
from filter import build as build_tests, BAD as BAD_TEST

LEAN_HOOK = {"matcher": "Bash", "hooks": [{"type": "command",
                                           "command": f"python3 {HERE.parent / 'hooks' / 'squeeze_hook.py'}"}]}
BAD_FILE = "src/net/retry.c"


def build_make(d):
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    lines = [f"cc -O2 -c src/mod{i:03d}.c -o build/mod{i:03d}.o" for i in range(250)]
    lines[173:173] = [f"{BAD_FILE}:88:5: error: use of undeclared identifier 'backoff_ms'"]
    lines += [f"[{p:3d}%] Linking CXX object build/part{p}.o" for p in range(0, 101, 1)]
    script = "import sys\n" + "\n".join(f"print({l!r})" for l in lines) + "\nsys.exit(2)\n"
    (d / "build_log.py").write_text(script)
    (d / "Makefile").write_text("all:\n\t@python3 build_log.py\n")


NOISY = [
    {"id": "pytest", "build": build_tests, "answer": BAD_TEST, "allow": "Bash(pytest *)",
     "prompt": "Run the test suite with `pytest -v`. Exactly one test fails. Write its node id "
               "(like tests/test_x.py::test_name) to ANSWER.txt, nothing else."},
    {"id": "make", "build": build_make, "answer": BAD_FILE, "allow": "Bash(make),Bash(make *)",
     "prompt": "Run `make`. The build fails in exactly one source file. Write that file's path (like src/x/y.c) "
               "to ANSWER.txt, nothing else."},
]


def jfrog_settings(home, binary):
    """JFrog's Claude Code hooks from the throwaway HOME, re-pointed so they keep using that HOME."""
    s = json.loads((home / ".claude" / "settings.json").read_text())
    env = f"HOME={shlex.quote(str(home))} PATH={shlex.quote(str(binary))}:$PATH "
    for groups in s.get("hooks", {}).values():
        for g in groups:
            for h in g.get("hooks", []):
                if h.get("type") == "command":
                    h["command"] = env + h["command"]
    rule = "\n\n".join(p.read_text() for p in sorted((home / ".claude").rglob("*.md")))
    return json.dumps({"hooks": s.get("hooks", {})}), rule


def flags(arm, jf, extra_allow=""):
    allow = TOOLS + (f",{extra_allow}" if extra_allow else "")
    hooks, out = {}, ["--allowedTools", allow]
    if "jfrog" in arm:
        jh, rule = jf
        for ev, groups in json.loads(jh)["hooks"].items():
            hooks.setdefault(ev, []).extend(groups)
        if rule:
            out += ["--append-system-prompt", rule]
        out[1] += ",Bash(boost *)"
    if arm.startswith("lean"):
        hooks.setdefault("PreToolUse", []).append(LEAN_HOOK)
        out += ["--agents", reader_json()]
    if hooks:
        out += ["--settings", json.dumps({"hooks": hooks})]
    return out


def call(cmd, cwd):
    t0 = time.time()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=900)
    try:
        r = json.loads(p.stdout.splitlines()[0])
    except (ValueError, IndexError):
        r = {"is_error": True}
    u = r.get("usage") or {}
    return r, {"usd": r.get("total_cost_usd") or 0, "seconds": round(time.time() - t0, 1), "error": r.get("is_error"),
               "prompt": u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("input_tokens", 0)}


def long_session(arm, rep, a, jf):
    d = HERE / "runs" / f"vs-long-{arm}-{rep}"
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(HERE / "fixture", d)
    sid, rows, spent = None, [], 0.0
    for step, task in enumerate(json.loads((HERE / "tasks.json").read_text())):
        left = a.budget - spent
        row = {"suite": "long", "arm": arm, "rep": rep, "step": step, "task": task["id"]}
        if left < 0.01:
            rows.append({**row, "pass": False, "usd": 0, "error": "budget"})
            continue
        cmd = [CLAUDE, "-p", task["prompt"], "--output-format", "json", "--model", a.model,
               "--max-budget-usd", f"{left:.2f}", *flags(arm, jf)]
        fresh = arm.startswith("lean")
        if fresh:
            if not os.environ.get("LEAN_KEEP_SESSIONS"):           # set it to keep transcripts for a post-mortem
                cmd += ["--no-session-persistence"]
        elif sid:
            cmd += ["--resume", sid]
        r, m = call(cmd, d)
        sid = r.get("session_id") or sid
        spent += m["usd"]
        ok = json.loads(subprocess.run([sys.executable, str(HERE / "check.py"), task["id"], str(d)],
                                       capture_output=True, text=True).stdout)["pass"]
        ans = next((f.read_text()[:300] for f in (d / "ANSWER.txt", d / "ANSWER.json") if f.is_file()), None)
        rows.append({**row, "pass": ok, **m, "answer": None if ok else ans, "session": r.get("session_id")})
        print(json.dumps(rows[-1]), flush=True)
        (d / "ANSWER.txt").unlink(missing_ok=True)
        (d / "ANSWER.json").unlink(missing_ok=True)
    return rows


def noisy_task(arm, rep, a, jf, task):
    d = HERE / "runs" / f"vs-{task['id']}-{arm}-{rep}"
    task["build"](d)
    cmd = [CLAUDE, "-p", task["prompt"], "--output-format", "json", "--model", a.model, "--no-session-persistence",
           "--max-budget-usd", f"{a.budget:.2f}", *flags(arm, jf, task["allow"])]
    r, m = call(cmd, d)
    f = d / "ANSWER.txt"
    ok = f.is_file() and f.read_text().strip() == task["answer"]
    row = {"suite": "noisy", "arm": arm, "rep": rep, "step": 0, "task": task["id"], "pass": ok, **m}
    print(json.dumps(row), flush=True)
    return [row]


def summary(rows):
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["suite"], r["arm"])].append(r)
    print(f"\n{'suite':<6} {'arm':<11} {'passed':>7} {'$ per run':>10}")
    for suite in ("long", "noisy"):
        base = None
        for arm in ("plain", "jfrog", "lean", "lean+jfrog"):
            rs = by.get((suite, arm))
            if not rs:
                continue
            runs = len({(r["rep"], r["task"]) for r in rs}) if suite == "noisy" else len({r["rep"] for r in rs})
            usd = sum(r.get("usd") or 0 for r in rs) / runs
            base = base or usd
            print(f"{suite:<6} {arm:<11} {sum(r['pass'] for r in rs):>3}/{len(rs):<3} {usd:>10.3f}  "
                  f"{'' if arm == 'plain' else f'{100 * (usd / base - 1):+.0f}%'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jfrog-home", type=Path)
    ap.add_argument("--jfrog-bin", type=Path, help="folder holding the boost binary")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--budget", type=float, default=2.0, help="dollar cap per session")
    ap.add_argument("--arms", default="plain,jfrog,lean,lean+jfrog")
    ap.add_argument("--suites", default="long,noisy")
    a = ap.parse_args()
    arms, suites = a.arms.split(","), a.suites.split(",")
    jf = None
    if any("jfrog" in x for x in arms):
        if not (a.jfrog_bin and (a.jfrog_bin / "boost").is_file()
                and a.jfrog_home and (a.jfrog_home / ".claude" / "settings.json").is_file()):
            sys.exit("JFrog Boost not found: see the setup lines at the top of this file, or pass --arms plain,lean.")
        jf = jfrog_settings(a.jfrog_home.resolve(), a.jfrog_bin.resolve())
    jobs = []
    for rep in range(a.reps):
        for arm in arms:
            if "long" in suites:
                jobs.append(lambda arm=arm, rep=rep: long_session(arm, rep, a, jf))
            if "noisy" in suites:
                jobs += [lambda arm=arm, rep=rep, t=t: noisy_task(arm, rep, a, jf, t) for t in NOISY]
    with ThreadPoolExecutor(min(len(jobs), 8)) as ex:
        rows = [r for rs in ex.map(lambda j: j(), jobs) for r in rs]
    with (HERE / "vs-results.jsonl").open("a") as f:
        for r in rows:
            f.write(json.dumps({**r, "model": a.model, "at": time.strftime("%Y-%m-%d")}) + "\n")
    summary(rows)


if __name__ == "__main__":
    main()
