#!/usr/bin/env python3
"""Output budget (SessionStart hook, matcher "startup|clear|compact").

Output tokens are priced at several times input tokens. This adds a few lines of standing rules at session start (~120 tokens, cached with
the rest of the prompt) so Claude writes less: the smallest change that works, and short final answers. Correctness,
error handling at boundaries and exact code are kept. LEAN_TERSE=0 drops the output rules but keeps the subagent rule:
slim alone made Claude start 9-10 Explore subagents on reading tasks (THOL Django: +109% cost), and this rule stopped it.
The web rule: each WebSearch is a separate Sonnet request (~10K input + ~1.8K output, ~$0.07); a WebFetch page is read by
Haiku (~$0.015). On THOL web research, WebSearch calls were ~80% of the cost."""
import json
import os
import sys

OUTPUT = """- Write the smallest change that solves the task. Reuse existing code and the standard library; add no abstraction, option, file or dependency nobody asked for.
- Final answer: lead with the result in 1-3 lines. No recap of steps, no restated question, no unasked options.
- Change files with Edit; use Write only for new files or full rewrites. Keep a to-do list only for 4+ steps.
"""
AGENTS = ("- Do the reading yourself with Grep, Glob and Read; start a subagent only when the user asks for one or the search is truly open-ended.\n"
          "- Web: one WebSearch costs about five WebFetch calls. Search to find sources, then WebFetch the richest page (an awesome-list, "
          "GitHub topic page, registry or docs index) instead of running many narrow searches; never repeat a query you already ran.\n"
          "- Run independent reads, searches and commands together in one turn; every extra turn re-reads the whole context.\n"
          "- Browser and computer use: read the page text first; take a screenshot only to check layout.\n"
          "- PDFs: when only the text matters, extract it (pdftotext or similar) and read that instead of the PDF.\n"
          "- Tests: run the narrowest test that proves a change; run the full suite once at the end.\n"
          "- Watching background work: filter to the events you will act on; every wake-up re-reads the whole context.\n")
KEEP = "- Never trim correctness: keep needed validation and error handling, and keep code, commands, paths and errors exact."
RULES = "Output budget (Claude Lean):\n" + OUTPUT + AGENTS + KEEP


def main():
    rules = "Claude Lean:\n" + AGENTS.strip() if os.environ.get("LEAN_TERSE") == "0" else RULES
    try:
        json.load(sys.stdin)
    except ValueError:
        pass
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": rules}}))


if __name__ == "__main__":
    main()
