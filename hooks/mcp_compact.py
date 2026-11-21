#!/usr/bin/env python3
"""MCP result compaction (PostToolUse hook, matcher mcp__.*).

MCP tools often return pretty-printed JSON full of nulls, and every byte of it is re-read on every later turn. For
each text block that is JSON, this removes the indentation and drops null and "" fields inside nested records (where
a missing field reads the same as an empty one), then hands Claude the smaller result. Top-level fields, empty lists
and objects ("items": [] means nothing was found), numbers, false and every other value stay exactly as they were.
Results that aren't JSON, or that would shrink by less than 10%, are left alone. LEAN_MCP_COMPACT=0 turns it off."""
import json
import os
import sys

def prune(v, depth=0):
    if isinstance(v, dict):
        out = {k: prune(x, depth + 1) for k, x in v.items()}
        return out if depth == 0 else {k: x for k, x in out.items() if x is not None and x != ""}
    if isinstance(v, list):
        return [prune(x, depth + 1) for x in v]
    return v


def compact(text):
    s = text.strip()
    if not s or s[0] not in "[{":
        return None
    try:
        small = json.dumps(prune(json.loads(s)), separators=(",", ":"), ensure_ascii=False)
    except ValueError:
        return None
    return small if len(small) < 0.9 * len(text) else None


def main():
    if os.environ.get("LEAN_MCP_COMPACT") == "0":
        return
    d = json.load(sys.stdin)
    resp = d.get("tool_response")
    if isinstance(resp, str):
        new = compact(resp)
        out = new
    elif isinstance(resp, list):
        changed, out = False, []
        for b in resp:
            new = compact(b.get("text", "")) if isinstance(b, dict) and b.get("type") == "text" else None
            changed |= new is not None
            out.append(dict(b, text=new) if new is not None else b)
        out = out if changed else None
    else:
        out = None
    if out is not None:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "updatedMCPToolOutput": out}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
