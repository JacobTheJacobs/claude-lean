#!/usr/bin/env python3
"""Output filter for noisy commands (pytest, npm, pip, cargo, go, docker, make, ...).

    some-command 2>&1 | python3 squeeze.py filter <tool>   trims the output, keeps the full copy on disk
    python3 squeeze.py get <id>                             prints the full original
    python3 squeeze.py stats                                what was saved, per tool

hooks/squeeze_hook.py adds the pipe for you. Short outputs (under LEAN_SQUEEZE_MIN lines, default 40) pass through
untouched. Errors, failures, warnings, tracebacks and summaries are always kept; progress bars, download/compile chatter,
passed-test lines and repeats are dropped. Nothing is lost: every original is saved under ~/.cache/claude-lean/out.
If the agent fetches the original of one tool LEAN_SQUEEZE_GIVEUP times (default 3), that tool stops being filtered."""
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

CACHE = Path(os.environ.get("LEAN_CACHE", Path.home() / ".cache" / "claude-lean"))
OUT = CACHE / "out"
STATE = CACHE / "squeeze.json"
MIN = int(os.environ.get("LEAN_SQUEEZE_MIN", 40))
GIVEUP = int(os.environ.get("LEAN_SQUEEZE_GIVEUP", 3))
KEEP_FILES = 200
ME = Path(__file__).resolve()

ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07")
SIGNAL = re.compile(r"error|fail|panic|exception|traceback|warn|assert|denied|not found|cannot|fatal|"
                    r"^E\s|^\s*File \"|^\s*at |^-->|^={3,}|^-{3,}|(?-i:\d+ (passed|skipped|failed|errors?))|summary|total|"
                    r"^(ok|FAIL)\s|\d+ (tests?|examples?|specs?)\b", re.I)
NOISE = re.compile(
    r"^\s*$|"
    r"^\s*[\d.]+\s*%|\[[#=>\-. ]{5,}\]|[█▓▒░■□]{3,}|^[.sxFE]{8,}\s*(\[\s*\d+%\])?$|"     # bars, pytest dots
    r"^\s*(Collecting|Downloading|Using cached|Requirement already satisfied|Installing collected|Building wheel|"
    r"Created wheel|Stored in directory|Preparing metadata|Getting requirements|Attempting uninstall|"
    r"Found existing installation|Uninstalling|Successfully uninstalled)\b|"                # pip
    r"^npm (http|timing|sill|verb)|^npm warn deprecated|^(added|removed|changed) \d+ packages?.*audited|"
    r"^\s*(Compiling|Downloaded|Downloading|Fresh|Checking|Locking|Updating|Adding|Blocking)\s+\S+ v?\d|"  # cargo
    r"^go: (downloading|finding|extracting)|^ok\s+\S+\s+[\d.]+s$|^=== (RUN|PAUSE|CONT)\s|^--- PASS|"       # go
    r"^\S+ (PASSED|SKIPPED|XFAIL)|\sPASSED\s*(\[\s*\d+%\])?$|^\s*✓|^\s*√|^\s*PASS\s|"     # test runners
    r"^[0-9a-f]{12}: (Pulling|Waiting|Downloading|Verifying|Download complete|Extracting|Pull complete|Already exists)|"
    r"^#\d+ (\[internal\]|sha256:|extracting|DONE \d|CACHED)|^ ---> |^Step \d+/\d+ : |"     # docker
    r"^make(\[\d+\])?: (Entering|Leaving) directory",
    re.I)


def load():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {"tools": {}, "ids": {}}


def save(s):
    CACHE.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s))


def clean(text):
    lines = []
    for raw in ANSI.sub("", text).split("\n"):
        lines.append(raw.rsplit("\r", 1)[-1].rstrip())     # a \r progress line: keep its final state
    return lines


def squeeze(lines):
    kept, prev, reps = [], None, 0

    def flush():
        if reps:
            kept.append(f"  (previous line repeated {reps}x)")

    for ln in lines:
        if NOISE.search(ln) and not SIGNAL.search(ln):
            continue
        key = re.sub(r"\d+", "#", ln)
        if key == prev:
            reps += 1
            continue
        flush()
        prev, reps = key, 0
        kept.append(ln)
    flush()
    if len(kept) > 200:                                      # still huge: signal lines with context, plus head and tail
        mark = set(range(30)) | set(range(len(kept) - 40, len(kept)))
        for i, ln in enumerate(kept):
            if SIGNAL.search(ln):
                mark.update(range(i - 2, i + 6))
        out, last = [], -1
        for i in sorted(j for j in mark if 0 <= j < len(kept)):
            if i != last + 1:
                out.append(f"  ... {i - last - 1} lines cut ...")
            out.append(kept[i])
            last = i
        kept = out
    return kept


def cmd_filter(tool):
    data = sys.stdin.buffer.read().decode("utf-8", "replace")
    try:
        out = filtered(tool, data)
    except Exception:                                        # a broken filter must never cost the command's output
        out = data
    sys.stdout.write(out)


def filtered(tool, data):
    s = load()
    lines = clean(data)
    if tool in s.get("off", []) or len(lines) < MIN:
        return data
    kept = squeeze(lines)
    out = "\n".join(kept).strip("\n")
    if len(out) >= len(data) * 0.9:
        return data
    OUT.mkdir(parents=True, exist_ok=True)
    OUT.chmod(0o700)                                         # saved outputs can hold secrets: owner only
    rid = f"{int(time.time() * 1000) % 10**9:09d}"
    (OUT / f"{rid}.log").write_text(data)
    for old in sorted(OUT.glob("*.log"), key=lambda p: p.stat().st_mtime)[:-KEEP_FILES]:
        old.unlink(missing_ok=True)
    t = s.setdefault("tools", {}).setdefault(tool, {"runs": 0, "chars_in": 0, "chars_out": 0, "gets": 0})
    t["runs"] += 1
    t["chars_in"] += len(data)
    t["chars_out"] += len(out)
    s.setdefault("ids", {})[rid] = tool
    s["ids"] = dict(list(s["ids"].items())[-KEEP_FILES:])
    save(s)
    pct = round(100 * (1 - len(out) / max(len(data), 1)))
    return (f"{out}\n[Claude Lean trimmed {pct}% of this output ({len(lines)} -> {len(kept)} lines). "
            f"Full original: python3 {shlex.quote(str(ME))} get {rid}]\n")


def cmd_get(rid):
    if not rid.isdigit():
        sys.exit("id must be digits")
    f = OUT / f"{rid}.log"
    if not f.is_file():
        sys.exit(f"no saved output {rid}")
    sys.stdout.write(f.read_text())
    s = load()
    tool = s["ids"].get(rid)
    if tool:
        t = s["tools"].setdefault(tool, {"runs": 0, "chars_in": 0, "chars_out": 0, "gets": 0})
        t["gets"] += 1
        if t["gets"] >= GIVEUP and tool not in s.setdefault("off", []):
            s["off"].append(tool)
            print(f"\n[Claude Lean: the {tool} filter hid too much {t['gets']} times; it is now off. "
                  f"Re-enable: python3 {shlex.quote(str(ME))} on {tool}]")
        save(s)


def cmd_stats():
    s = load()
    rows = sorted(s["tools"].items(), key=lambda kv: kv[1]["chars_in"] - kv[1]["chars_out"], reverse=True)
    if not rows:
        print("nothing filtered yet")
        return
    print(f"{'tool':<10} {'runs':>5} {'~tokens in':>11} {'~tokens out':>12} {'saved':>6} {'gets':>5}")
    for tool, t in rows:
        saved = 100 * (1 - t["chars_out"] / max(t["chars_in"], 1))
        off = "  (off)" if tool in s.get("off", []) else ""
        print(f"{tool:<10} {t['runs']:>5} {t['chars_in'] // 4:>11} {t['chars_out'] // 4:>12} {saved:>5.0f}% {t['gets']:>5}{off}")
    print("Tokens are estimated at 4 characters each. Each trimmed output keeps saving on every later request "
          "until the session is cleared or compacted.")


def cmd_on(tool):
    s = load()
    s["off"] = [t for t in s.get("off", []) if t != tool]
    s["tools"].get(tool, {})["gets"] = 0
    save(s)
    print(f"{tool} filter on")


def main():
    a = sys.argv[1:]
    if a[:1] == ["filter"]:
        cmd_filter(a[1] if len(a) > 1 else "other")
    elif a[:1] == ["get"] and len(a) > 1:
        cmd_get(a[1])
    elif a[:1] == ["on"] and len(a) > 1:
        cmd_on(a[1])
    elif a[:1] == ["stats"]:
        cmd_stats()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
