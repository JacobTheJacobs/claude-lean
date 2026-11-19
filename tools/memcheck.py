#!/usr/bin/env python3
"""How much Claude Code's memory costs you on every request.

    python3 memcheck.py             every project's MEMORY.md index and CLAUDE.md files, in tokens

Claude Code loads each project's memory index (MEMORY.md) and its CLAUDE.md files into every request of every session
in that project. Topic files are read only when needed, so the index should be one short line per memory. Read-only:
it never edits your files. Tokens are estimated at 4 characters each."""
import os
from pathlib import Path

HOME = Path.home()
PROJECTS = HOME / ".claude" / "projects"
BUDGET = int(os.environ.get("LEAN_MEMORY_BUDGET", 1000))   # tokens per request worth spending on the index
LONG_LINE = 200


def tokens(p):
    try:
        return len(p.read_text(errors="replace")) // 4
    except OSError:
        return 0


def main():
    rows = []
    for idx in sorted(PROJECTS.glob("*/memory/MEMORY.md")):
        lines = idx.read_text(errors="replace").splitlines()
        rows.append((tokens(idx), idx, sum(len(l) > LONG_LINE for l in lines), len(lines)))
    if not rows:
        print("no memory indexes found")
    else:
        print(f"{'tokens':>7}  {'lines':>5}  {'long':>4}  memory index (loaded on every request in that project)")
        for t, p, long_, n in sorted(rows, reverse=True):
            flag = "  <- over budget" if t > BUDGET else ""
            print(f"{t:>7}  {n:>5}  {long_:>4}  {p.parent.parent.name}{flag}")
    g = HOME / ".claude" / "CLAUDE.md"
    print(f"\n{tokens(g):>7}  global CLAUDE.md (every request, every project)" if g.exists() else "")
    over = [r for r in rows if r[0] > BUDGET]
    if over:
        print(f"\nTo trim an index over {BUDGET} tokens without losing anything: move detail into its topic files and keep "
              f"one line per memory in MEMORY.md (`- [Title](file.md) - hook`, under {LONG_LINE} characters). "
              "Ask Claude in that project: \"trim MEMORY.md to one short line per memory; move details into the topic files\".")


if __name__ == "__main__":
    main()
