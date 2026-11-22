#!/usr/bin/env python3
"""Long-session guard (UserPromptSubmit hook): tells you when the session has grown long, so you can /clear before
starting something unrelated. Silent below the threshold, so short sessions pay nothing.

It does not promise savings. Measured (evals/long.py, per-step costs): when tasks run back to back, one continuous
session is cheaper than a fresh one per task, because the history is read from cache at a tenth of the input price
while a fresh session pays to write its whole starting context again. /clear is for focus and for unrelated work.
This hook reads the last request's prompt size from the transcript and, past
LEAN_CLEAR_AT tokens (default 100000), shows a one-line note to you (systemMessage: not sent to the model, adds no
tokens). It repeats at most once per LEAN_CLEAR_EVERY tokens of further growth (default 50000). Never blocks.
It also notes a pasted prompt over LEAN_PASTE_CHARS characters (default 40000, ~10K tokens): pasted text stays in the
context and is re-read on every later turn, while a file Claude searches costs only what it reads."""
import json
import os
import sys
from pathlib import Path

AT = int(os.environ.get("LEAN_CLEAR_AT", 100_000))
EVERY = int(os.environ.get("LEAN_CLEAR_EVERY", 50_000))
PASTE = int(os.environ.get("LEAN_PASTE_CHARS", 40_000))
# Prompt cache lifetime: 1 hour on a Claude subscription, 5 minutes with an API key (Claude Code's defaults).
TTL = int(os.environ.get("LEAN_CACHE_TTL") or (300 if os.environ.get("ANTHROPIC_API_KEY") else 3600))


def idle_seconds(transcript: Path) -> float:
    """Seconds since the last message in the transcript."""
    import datetime as dt
    size = transcript.stat().st_size
    with transcript.open("rb") as f:
        f.seek(max(0, size - 200_000))
        lines = f.read().decode("utf-8", "replace").splitlines()
    for line in reversed(lines):
        if '"timestamp"' in line and '"assistant"' in line:
            try:
                ts = json.loads(line)["timestamp"].replace("Z", "+00:00")
                return (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(ts)).total_seconds()
            except (ValueError, KeyError, TypeError):
                continue
    return 0


def last_prompt_tokens(transcript: Path) -> int:
    """Prompt size of the newest API request in the transcript (input + cache read + cache write)."""
    size = transcript.stat().st_size
    with transcript.open("rb") as f:
        f.seek(max(0, size - 2_000_000))
        lines = f.read().decode("utf-8", "replace").splitlines()
    for line in reversed(lines):
        if '"usage"' not in line:
            continue
        try:
            u = json.loads(line)["message"]["usage"]
        except (ValueError, KeyError, TypeError):
            continue
        return u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
    return 0


def main():
    d = json.load(sys.stdin)
    prompt = d.get("prompt") or ""
    if PASTE and len(prompt) > PASTE:
        print(json.dumps({"systemMessage": f"Claude Lean: this prompt is ~{len(prompt) // 4000}K tokens and stays in "
                          "the context for every later turn. For a big log or document, save it to a file and ask "
                          "Claude to search it: only the parts it reads are paid for."}))
        return
    t = Path(d.get("transcript_path") or "")
    if not t.is_file():
        return
    n = last_prompt_tokens(t)
    idle = idle_seconds(t)
    if n >= 30_000 and idle > TTL:
        turns = 20 if TTL > 300 else 12           # a cache write costs 2x (1 h) or 1.25x (5 min) vs 0.1x for a read
        print(json.dumps({"systemMessage": f"Claude Lean: {idle / 60:.0f} min since the last reply, so the prompt "
                          f"cache has expired. This message writes the whole ~{n // 1000}K-token conversation to cache "
                          f"again (about as much as {turns} normal turns). Coming back to something different? Say "
                          "\"handoff\", then /clear: a short note costs far less."}))
        return
    if n < AT:
        return
    mark = Path.home() / ".cache" / "claude-lean" / f"guard-{d.get('session_id', 'x')}"
    try:
        shown = int(mark.read_text())
    except (OSError, ValueError):
        shown = 0
    if shown and n < shown + EVERY:
        return
    mark.parent.mkdir(parents=True, exist_ok=True)
    mark.write_text(str(n))
    print(json.dumps({"systemMessage": f"Claude Lean: this session is ~{n // 1000}K tokens. "
                      "Starting something unrelated? /clear keeps the context focused. "
                      "Same task, but the context is getting messy? Say \"handoff\", then /clear: a short note carries over."}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
