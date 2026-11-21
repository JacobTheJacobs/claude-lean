#!/usr/bin/env python3
"""Read guard (PreToolUse and PostToolUse hook, matcher Read).

Every Read result stays in the conversation and is re-read from cache on every later turn, so a big or repeated read
is paid many times over.
- PreToolUse, large file: a Read with no offset/limit of a text file over LEAN_READ_LINES lines (default 1000) or
  LEAN_READ_BYTES bytes (default 100000: catches notebooks with embedded images, one-line JSON, minified code) is
  blocked once, with its size, and Claude is pointed at Grep or a line range. Repeating the same Read goes through.
- PostToolUse, identical re-read: when the same file and range was read earlier in this session, has not changed, and
  the conversation was not compacted since, the result is replaced by a one-line note pointing at the earlier read.
LEAN_READ_LINES=0 turns the size check off; LEAN_READ_DEDUPE=0 turns the re-read note off. Any error: no change."""
import hashlib
import json
import os
import sys

LINES = int(os.environ.get("LEAN_READ_LINES", 1000))
BYTES = int(os.environ.get("LEAN_READ_BYTES", 100_000))
DEDUPE = os.environ.get("LEAN_READ_DEDUPE", "1") != "0"
MARK = "[Claude Lean read]"


def entries(transcript, needles=()):
    """Transcript lines as (text, parsed); with needles, only lines containing one of them are parsed (transcripts
    reach tens of MB and this runs on every Read)."""
    try:
        with open(transcript, encoding="utf-8", errors="replace") as f:
            for line in f:
                if needles and not any(n in line for n in needles):
                    continue
                try:
                    yield line, json.loads(line)
                except ValueError:
                    continue
    except OSError:
        return


def same_range(a, b):
    return (a.get("file_path"), a.get("offset"), a.get("limit")) == (b.get("file_path"), b.get("offset"), b.get("limit"))


def pre(d):
    ti = d.get("tool_input") or {}
    path = ti.get("file_path") or ""
    if not (LINES or BYTES) or ti.get("offset") or ti.get("limit") or not os.path.isfile(path):
        return
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(8192)
        if b"\0" in head:                     # binary: images and PDFs are Claude Code's business
            return
        n = head.count(b"\n") + (sum(c.count(b"\n") for c in iter(lambda: f.read(1 << 20), b"")) if size < 50 << 20 else 0)
    if not ((LINES and n > LINES) or (BYTES and size > BYTES)):
        return
    for line, e in entries(d.get("transcript_path") or "", (MARK,)):
        if path in line and "is_error" in line:
            return                            # already warned about this file: let the full read through
    tokens = (size + 8 * n) // 4     # Read adds a line-number column
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": f"{MARK} {path} has {n:,} lines and {size:,} bytes (~{tokens:,} tokens), and a full read stays in "
        "the context for the rest of the session. If you need part of it, Grep for what you want or Read with "
        "offset/limit. If you really need all of it, repeat this exact Read and it will go through."}}))


def post(d):
    if not DEDUPE:
        return
    ti = d.get("tool_input") or {}
    resp = d.get("tool_response") or {}
    f = resp.get("file") if isinstance(resp, dict) else None
    if not (isinstance(f, dict) and isinstance(f.get("content"), str)) or resp.get("type") != "text":
        return
    digest = hashlib.sha256(f["content"].encode()).hexdigest()
    calls, earlier, me = {}, None, d.get("tool_use_id")
    fp = json.dumps(ti.get("file_path") or "")[1:-1]          # the path as it appears inside a JSON line
    for line, e in entries(d.get("transcript_path") or "", (fp, "compact_boundary", '"isCompactSummary":true')):
        if "compact_boundary" in line or e.get("isCompactSummary"):
            earlier = None                    # after compaction the earlier copy is gone from the context
            continue
        content = (e.get("message") or {}).get("content")
        if e.get("type") == "assistant" and isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Read":
                    calls[b.get("id")] = b.get("input") or {}
        r = e.get("toolUseResult")
        if e.get("type") == "user" and isinstance(r, dict) and isinstance(r.get("file"), dict) and isinstance(content, list):
            for b in content:
                tid = b.get("tool_use_id") if isinstance(b, dict) else None
                if tid and tid != me and tid in calls and same_range(calls[tid], ti):
                    c = r["file"].get("content")
                    if isinstance(c, str) and MARK not in c:
                        earlier = (hashlib.sha256(c.encode()).hexdigest(), e.get("timestamp", ""))
    if not earlier or earlier[0] != digest:
        return
    note = (f"{MARK} Unchanged since you read this same range earlier in this session; that result is above. "
            "Read it again only if you edited it since.")
    out = dict(resp, file=dict(f, content=note, numLines=1))
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "updatedToolOutput": out}}))


def main():
    d = json.load(sys.stdin)
    (pre if d.get("hook_event_name") == "PreToolUse" else post)(d)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
