#!/usr/bin/env python3
"""Retry-loop breaker (PostToolUseFailure hook, matcher Bash|Edit).

When the same command (or an Edit of the same file) fails for the third time in a session with the same last error
line, Claude gets one short note: read the error, change the approach, or ask. Each retry is a full turn that re-reads the whole conversation, so
a loop of identical failures is pure cost. It never blocks anything. LEAN_LOOP_AT sets the count (default 3; 0 = off)."""
import json
import os
import sys

AT = int(os.environ.get("LEAN_LOOP_AT", 3))


def last_line(err):
    lines = [x.strip() for x in str(err or "").splitlines() if x.strip()]
    return lines[-1][:200] if lines else ""


def main():
    d = json.load(sys.stdin)
    tool = d.get("tool_name") or "Bash"
    ti = d.get("tool_input") or {}
    target = lambda name, inp: (name, ((inp or {}).get("command") or (inp or {}).get("file_path") or "").strip())
    cmd = target(tool, ti)[1]
    err = last_line(d.get("error"))
    if not AT or not cmd:
        return
    cmds, fails = {}, 0
    with open(d.get("transcript_path") or "", encoding="utf-8", errors="replace") as f:
        for line in f:
            if "tool_use" not in line and "tool_result" not in line:
                continue
            try:
                content = json.loads(line)["message"]["content"]
            except (ValueError, KeyError, TypeError):
                continue
            for b in content if isinstance(content, list) else []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use" and b.get("name") in ("Bash", "Edit", "MultiEdit"):
                    cmds[b.get("id")] = target(b.get("name"), b.get("input"))
                elif (b.get("type") == "tool_result" and b.get("is_error") and b.get("tool_use_id") != d.get("tool_use_id")
                      and cmds.get(b.get("tool_use_id")) == (tool, cmd) and last_line(b.get("content")) == err):
                    fails += 1
    if fails + 1 == AT:                       # once, on the AT-th identical failure
        what = (f"editing {cmd} has now failed {AT} times ({err}). Read the exact current lines of that part of the "
                "file, then edit with text copied from them") if tool != "Bash" else \
               (f"this exact command has now failed {AT} times with the same error ({err}). Retrying it unchanged "
                "will fail again. Read the error, change the approach, or ask the user")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUseFailure",
                                                 "additionalContext": f"Claude Lean: {what}."}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
