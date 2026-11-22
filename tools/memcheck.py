#!/usr/bin/env python3
"""How much Claude Code's memory costs you on every request.

    python3 memcheck.py             every project's MEMORY.md index and CLAUDE.md files, in tokens

Claude Code loads each project's memory index (MEMORY.md) and its CLAUDE.md files into every request of every session
in that project. Topic files are read only when needed, so the index should be one short line per memory. Read-only:
it never edits your files. Tokens are estimated at 4 characters each."""
import os
import re
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


IMPORT = re.compile(r"(?:^|\s)@((?:~|\.{1,2})?/?[\w./-]+\.\w+)")


def imports(md, seen=None):
    """Files a CLAUDE.md pulls in with @path (up to 5 levels deep, as Claude Code does): (tokens, path) pairs."""
    seen = seen if seen is not None else {md.resolve()}
    out = []
    if len(seen) > 50:
        return out
    try:
        text = md.read_text(errors="replace")
    except OSError:
        return out
    text = re.sub(r"```.*?```|`[^`]*`", "", text, flags=re.S)        # imports inside code are not evaluated
    for m in IMPORT.findall(text):
        f = Path(os.path.expanduser(m)) if m.startswith("~") else (md.parent / m)
        if f.is_file() and f.resolve() not in seen and len(seen) < 6 * 10:
            seen.add(f.resolve())
            out.append((tokens(f), f))
            out += imports(f, seen)
    return out


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
    if g.exists():
        imp = imports(g)
        print(f"\n{tokens(g):>7}  global CLAUDE.md (every request, every project)")
        for t, f in imp:
            print(f"{t:>7}    + @import {f}")
    over = [r for r in rows if r[0] > BUDGET]
    if over:
        print(f"\nTo trim an index over {BUDGET} tokens without losing anything: move detail into its topic files and keep "
              f"one line per memory in MEMORY.md (`- [Title](file.md) - hook`, under {LONG_LINE} characters). "
              "Ask Claude in that project: \"trim MEMORY.md to one short line per memory; move details into the topic files\".")


if __name__ == "__main__":
    main()
