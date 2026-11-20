#!/usr/bin/env python3
"""Claude Lean usage report: where your Claude Code tokens and dollars went, from the local session logs.

    python3 tools/report.py                 last 7 days, all projects
    python3 tools/report.py --days 1        today and yesterday
    python3 tools/report.py --project NAME  only projects whose folder name contains NAME
    python3 tools/report.py --today-usd     print today's list-price dollars only (used by hooks/budget.py)

Reads ~/.claude/projects/*/*.jsonl and each session's subagents/*.jsonl. Each API message is counted once, at its last
logged usage. Dollars are list prices (below); a subscription is billed differently, so treat them as relative weight.
Standard library only."""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path.home() / ".claude" / "projects"
# $ per 1M tokens: input, output, cache read, 5m cache write, 1h cache write. Anthropic pricing page, 2026-11-10.
RATES = {
    "fable-5-2": (8.00, 40.00, 0.20, 10.00, 16.00),
    "fable-5-1": (10.00, 50.00, 0.25, 12.50, 20.00),
    "opus-5-5": (4.00, 20.00, 0.20, 5.00, 8.00),
    "sonnet-5-5": (2.00, 10.00, 0.10, 2.50, 4.00),
    "haiku-5-5": (0.10, 0.50, 0.01, 0.125, 0.20),
    "haiku-5-5-long": (0.50, 2.50, 0.05, 0.625, 1.00),  # whole request, prompt over 100K tokens
    "opus": (5.00, 25.00, 0.50, 6.25, 10.00),  # older Opus 4.x / 5
    "sonnet": (3.00, 15.00, 0.30, 3.75, 6.00),  # older Sonnet 4.x
    "haiku": (1.00, 5.00, 0.10, 1.25, 2.00),  # Haiku 4.5
}


def rate(model: str, prompt: int):
    m = model.lower()
    for k in ("fable-5-2", "fable-5-1", "opus-5-5", "sonnet-5-5", "haiku-5-5"):
        if k in m:
            return RATES[k + "-long"] if k == "haiku-5-5" and prompt > 100_000 else RATES[k]
    for k in ("opus", "sonnet", "haiku"):
        if k in m:
            return RATES[k]
    return None


def messages(path: Path):
    """Last usage snapshot per API message id in one transcript."""
    last = {}
    try:
        lines = path.open("rb")          # bytes: transcripts reach gigabytes, and decoding every line is the slow part
    except OSError:
        return []
    with lines:
        for line in lines:
            if b'"usage"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            m = d.get("message") or {}
            u = m.get("usage")
            if not isinstance(u, dict) or not m.get("model") or m["model"].startswith("<"):
                continue
            last[m.get("id") or d.get("uuid")] = (d.get("timestamp", ""), m["model"], u)
    return last.values()


def cost(model: str, u: dict) -> float:
    i, o, cr = u.get("input_tokens", 0), u.get("output_tokens", 0), u.get("cache_read_input_tokens", 0)
    cc = u.get("cache_creation") or {}
    w5 = cc.get("ephemeral_5m_input_tokens", 0)
    w1 = cc.get("ephemeral_1h_input_tokens", 0)
    if not cc:
        w5 = u.get("cache_creation_input_tokens", 0)
    r = rate(model, i + cr + w5 + w1)
    if not r:
        return 0.0
    return (i * r[0] + o * r[1] + cr * r[2] + w5 * r[3] + w1 * r[4]) / 1e6


def collect(days: int, project: str | None):
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()
    rows = []
    for proj in sorted(ROOT.glob("*")):
        if project and project not in proj.name:
            continue
        for t in proj.glob("*.jsonl"):
            sid = t.stem
            files = [(t, "main")] + [(s, "subagent") for s in (proj / sid / "subagents").glob("*.jsonl")]
            for f, who in files:
                if f.stat().st_mtime < (dt.datetime.now() - dt.timedelta(days=days + 1)).timestamp():
                    continue
                for ts, model, u in messages(f):
                    if ts >= since:
                        rows.append((proj.name, sid, who, ts, model, u))
    return rows


TS = re.compile(rb'"timestamp":"([^"]+)"')


def seek_to(fh, size: int, start: str) -> int:
    """Offset of a line boundary shortly before the first line stamped at or after `start` (lines are in time order).
    Binary search, so a multi-gigabyte transcript costs a few dozen line reads instead of a full scan."""
    lo, hi = 0, size
    while hi - lo > 1_000_000:
        mid = (lo + hi) // 2
        fh.seek(mid)
        fh.readline()                                  # skip the partial line
        ts = None
        for _ in range(200):                           # some lines carry no timestamp: look a little further
            line = fh.readline()
            if not line:
                break
            m = TS.search(line)
            if m:
                ts = m.group(1).decode()
                break
        if ts is not None and ts < start:
            lo = mid
        else:
            hi = mid
    fh.seek(lo)
    if lo:
        fh.readline()
    return fh.tell()


def today_usd(project: str | None, state: dict | None = None) -> float:
    """Today's list-price dollars. `state` (kept by hooks/budget.py between prompts) remembers how far each transcript
    was read, so each call reads only what was appended since the last one."""
    midnight = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start = midnight.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    state = {} if state is None else state
    total = 0.0
    for proj in sorted(ROOT.glob("*")):
        if project and project not in proj.name:
            continue
        for f in list(proj.glob("*.jsonl")) + list(proj.glob("*/subagents/*.jsonl")):
            try:
                st = f.stat()
                if st.st_mtime < midnight.timestamp():
                    continue
                e = state.get(str(f))
                if not e or e["off"] > st.st_size:
                    e = state[str(f)] = {"off": -1, "ids": {}}
                with f.open("rb") as fh:
                    if e["off"] < 0:
                        e["off"] = seek_to(fh, st.st_size, start)
                    fh.seek(e["off"])
                    for line in fh:
                        if not line.endswith(b"\n"):
                            break                      # half-written last line: read it next time
                        e["off"] += len(line)
                        if b'"usage"' not in line:
                            continue
                        try:
                            d = json.loads(line)
                        except ValueError:
                            continue
                        m = d.get("message") or {}
                        u = m.get("usage")
                        if isinstance(u, dict) and m.get("model") and d.get("timestamp", "") >= start:
                            e["ids"][m.get("id") or d.get("uuid")] = cost(m["model"], u)
            except OSError:
                continue
            total += sum(e["ids"].values())
    return total


# Headless runs in scratch folders (benchmarks, scripts) are not your work: leave them out of before/after.
SCRATCH = ("-tmp-", "-evals-runs-", "claude-lean-evals")
FRESH_MAX = 100_000   # a fresh session's first request is fixed overhead (~17-60K tokens); more means it was resumed


def install_time():
    """When Claude Lean was first installed here: its oldest settings backup (install.sh writes one each run)."""
    baks = sorted(Path.home().glob(".claude/settings.json.lean-*.bak"))
    if not baks:
        return None
    stamp = baks[0].name.split("lean-")[1].split(".bak")[0]                   # 20261120-020654
    return dt.datetime.strptime(stamp, "%Y%m%d-%H%M%S").astimezone(dt.timezone.utc)


def compare(cut, days, project):
    """Sessions before vs after `cut`. The first request of a session is pure fixed overhead (system prompt, tools,
    skills, memory) before any task work, so its size is the clean before/after signal. Per-session and per-request
    cost follow your workload too, so read them as context, not proof."""
    rows = collect(days + max((dt.datetime.now(dt.timezone.utc) - cut).days, 0) + 1, project)
    first, sess, side = {}, collections.defaultdict(float), {}
    for proj, sid, who, ts, model, u in rows:
        if who != "main" or any(x in proj for x in SCRATCH):
            continue
        t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if abs((t - cut).days) > days:
            continue
        prompt = u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
        if sid not in first or ts < first[sid][0]:
            first[sid] = (ts, prompt)
            side[sid] = "after" if t >= cut else "before"
        sess[sid] += cost(model, u)
    resumed = {i for i in first if first[i][1] > FRESH_MAX}      # opened with old history: not a fixed-overhead reading
    side = {i: k for i, k in side.items() if i not in resumed}
    req = collections.Counter(side[r[1]] for r in rows if r[2] == "main" and r[1] in side)
    stats = {}
    for k in ("before", "after"):
        ids = [i for i in side if side[i] == k]
        if not ids:
            continue
        firsts = sorted(first[i][1] for i in ids)
        stats[k] = {"sessions": len(ids), "first": firsts[len(firsts) // 2],
                    "per_session": sum(sess[i] for i in ids) / len(ids),
                    "per_request": sum(sess[i] for i in ids) / max(req[k], 1)}
    if len(stats) < 2:
        for k, v in stats.items():
            print(f"{k}: {v['sessions']} fresh sessions, first request {v['first']:,} tokens (median), "
                  f"${v['per_request']:.4f} per request")
        sys.exit(f"need fresh sessions on both sides of {cut:%Y-%m-%d %H:%M} UTC within {days} days "
                 f"(have: {', '.join(stats) or 'none'}). Use Claude Code for a while, then run this again.")
    b, a = stats["before"], stats["after"]

    def ch(x, y):
        return f"{100 * (y / x - 1):+.0f}%" if x else ""
    print(f"Claude Lean before/after {cut:%Y-%m-%d %H:%M} UTC, {days} days each side"
          f"{' (' + project + ')' if project else ''}\n")
    print(f"{'':<34} {'before':>12} {'after':>12} {'change':>8}")
    print(f"{'fresh sessions':<34} {b['sessions']:>12} {a['sessions']:>12}"
          f"   ({len(resumed)} resumed sessions left out)")
    print(f"{'first request, tokens (median)':<34} {b['first']:>12,} {a['first']:>12,} {ch(b['first'], a['first']):>8}")
    print(f"{'cost per request':<34} {'$%.4f' % b['per_request']:>12} {'$%.4f' % a['per_request']:>12} "
          f"{ch(b['per_request'], a['per_request']):>8}")
    print(f"{'cost per session':<34} {'$%.3f' % b['per_session']:>12} {'$%.3f' % a['per_session']:>12} "
          f"{ch(b['per_session'], a['per_session']):>8}")
    print("\nThe first request is fixed overhead only, so its change is what Claude Lean did. Cost per request and per "
          "session also move with what you worked on: compare similar weeks, and give it a few days of normal use.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--project")
    ap.add_argument("--today-usd", action="store_true")
    ap.add_argument("--compare", nargs="?", const="install", metavar="DATE",
                    help="before vs after DATE (YYYY-MM-DD[THH:MM]); default: when Claude Lean was installed")
    a = ap.parse_args()
    if a.today_usd:
        print(f"{today_usd(a.project):.2f}")
        return
    if a.compare:
        cut = install_time() if a.compare == "install" else dt.datetime.fromisoformat(a.compare).astimezone(dt.timezone.utc)
        if cut is None:
            sys.exit("no Claude Lean install found; pass a date: --compare 2026-11-20")
        return compare(cut, a.days, a.project)
    rows = collect(a.days, a.project)
    if not rows:
        sys.exit("no usage found")
    tok = collections.Counter()
    usd = collections.Counter()
    for proj, sid, who, ts, model, u in rows:
        c = cost(model, u)
        cc = u.get("cache_creation_input_tokens", 0)
        tok["input"] += u.get("input_tokens", 0)
        tok["cache read"] += u.get("cache_read_input_tokens", 0)
        tok["cache write"] += cc
        tok["output"] += u.get("output_tokens", 0)
        usd["total"] += c
        usd["who:" + who] += c
        usd["model:" + model] += c
        usd["proj:" + proj] += c
        usd["sess:" + proj + "/" + sid[:8]] += c
        r = rate(model, 0)
        if r:
            usd["class:cache read"] += u.get("cache_read_input_tokens", 0) * r[2] / 1e6
            usd["class:output"] += u.get("output_tokens", 0) * r[1] / 1e6
            usd["class:input"] += u.get("input_tokens", 0) * r[0] / 1e6
    usd["class:cache write"] = usd["total"] - usd["class:cache read"] - usd["class:output"] - usd["class:input"]
    t = usd["total"] or 1
    prompt = tok["input"] + tok["cache read"] + tok["cache write"]
    hit = tok["cache read"] / prompt if prompt else 0
    print(f"Claude Lean report, last {a.days} days: ${usd['total']:.2f} list price, {len(rows)} requests")
    print(f"cache read share of input: {hit:.0%}  (Anthropic: agent loops ~84%; look into it below 80%)")
    avg = prompt / len(rows)
    print(f"average prompt per request: {avg / 1000:.0f}K tokens (every request re-reads it)")

    def block(title, prefix, n=8):
        print(f"\n{title}")
        for k, v in sorted(((k, v) for k, v in usd.items() if k.startswith(prefix)), key=lambda x: -x[1])[:n]:
            print(f"  {k[len(prefix):]:<52} ${v:8.2f}  {v / t:5.0%}")

    block("by token class", "class:")
    block("main thread vs subagents", "who:")
    block("by model", "model:")
    block("by project", "proj:")
    block("top sessions", "sess:")
    tips = []
    if hit < 0.8:
        tips.append("cache read share under 80%: something rewrites the prompt start (CLAUDE.md/settings/effort edits, model switches, long pauses)")
    if usd["class:cache write"] / t > 0.3:
        tips.append("cache writes over 30% of spend: fewer mid-session model/effort switches; resume less after long breaks")
    if usd["class:cache read"] / t > 0.5 and avg > 80_000:
        tips.append(f"cache reads are {usd['class:cache read'] / t:.0%} of spend at ~{avg / 1000:.0f}K tokens a request: the context is too long; /clear or a new session per task, /compact earlier, hand bulky reads to `reader`")
    if usd["class:output"] / t > 0.3:
        tips.append("output over 30% of spend: ask for shorter answers (skills/lean)")
    if usd["who:subagent"] / t > 0.1:
        tips.append("subagents over 10%: route easy lookups to the Haiku `reader` agent, not `fork` (forks run on your main model)")
    if tips:
        print("\nlevers")
        for x in tips:
            print("  - " + x)


if __name__ == "__main__":
    main()
