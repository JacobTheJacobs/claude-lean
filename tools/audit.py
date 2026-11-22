#!/usr/bin/env python3
"""Find skills and MCP servers you load on every request but never use.

    python3 audit.py [--days 30]              report: each skill / MCP server, uses in the window, description size
    python3 audit.py --disable-unused         move unused personal skills to ~/.claude/skills-disabled (reversible)
    python3 audit.py --disable NAME [NAME..]  move just these
    python3 audit.py --restore [NAME..]       move them back (all when no name is given)
    python3 audit.py --profile [DIR]          for one project: turn off the personal skills and user MCP servers it
                                              never used, in DIR/.claude/settings.local.json (reversible: --unprofile)

Every skill's name and description ride along in every request, but Claude Code caps that listing, so parking skills
saves less than their descriptions add up to (measured: 23 unused skills parked, 49.5K -> 49.3K tokens per request).
The main reason to park them is a shorter, more relevant skill list; the token saving is small. Usage comes from
your own session logs (~/.claude/projects): Skill tool calls, /slash-command runs, and mcp__<server>__ tool calls.
Nothing is deleted; MCP servers are only reported, with the command to remove one. Tokens: ~4 characters each."""
import argparse
import collections
import json
import re
import shutil
import sys
import time
from pathlib import Path

CLAUDE = Path.home() / ".claude"
SKILLS = CLAUDE / "skills"
PARKED = CLAUDE / "skills-disabled"
PROJECTS = CLAUDE / "projects"
CMD = re.compile(r"<command-name>/?([\w:.-]+)</command-name>")
KEEP = {"lean", "handoff"}  # Claude Lean's own; they cost ~60 tokens and the long-session guard points at handoff


def skill_info(d):
    f = d / "SKILL.md"
    try:
        text = f.read_text(errors="replace")
    except OSError:
        return None
    head = text.split("---")[1] if text.startswith("---") else ""
    meta = {}
    key = None
    for line in head.splitlines():
        m = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if m:
            key = m.group(1)
            meta[key] = m.group(2).strip()
        elif key and line.startswith((" ", "\t")):
            meta[key] += " " + line.strip()
    name = meta.get("name", d.name).strip("'\"")
    return {"name": name, "dir": d, "tokens": (len(name) + len(meta.get("description", ""))) // 4 + 5,
            "body": len(text) // 4}           # what the skill adds to the context, every later turn, once it runs


def slug(path):
    """Claude Code's log folder name for a project directory."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(Path(path).resolve()))


def usage(days, folder=None):
    since = time.time() - days * 86400
    skills, mcp, sessions = collections.Counter(), collections.Counter(), 0
    oldest = time.time()
    for f in (PROJECTS / folder if folder else PROJECTS).glob("**/*.jsonl"):
        mt = f.stat().st_mtime
        if mt < since:
            continue
        sessions += 1
        oldest = min(oldest, mt)
        with f.open(errors="replace") as fh:
            for line in fh:
                if '"tool_use"' not in line and "command-name" not in line:
                    continue
                try:
                    msg = json.loads(line).get("message") or {}
                except ValueError:
                    continue
                content = msg.get("content")
                if isinstance(content, str):
                    for m in CMD.findall(content):
                        skills[m.split(":")[-1]] += 1
                    continue
                for c in content or []:
                    if not isinstance(c, dict):
                        continue
                    if c.get("type") == "text":
                        for m in CMD.findall(c.get("text", "")):
                            skills[m.split(":")[-1]] += 1
                    if c.get("type") != "tool_use":
                        continue
                    name = c.get("name", "")
                    if name == "Skill":
                        skills[str((c.get("input") or {}).get("skill", "")).split(":")[-1]] += 1
                    elif name.startswith("mcp__"):
                        mcp[name.split("__")[1]] += 1
    return skills, mcp, sessions, oldest


INJECTED = ("hook_success", "hook_additional_context", "skill_listing", "deferred_tools_delta", "agent_listing_delta",
            "invoked_skills", "mcp_instructions_delta")


def injected(days):
    """Context added without you asking, from session logs: hook output, skill and tool listings, invoked skills.
    Also counts hooks that fail on every call (they add latency to every tool call)."""
    since = time.time() - days * 86400
    size, fails, sessions = collections.Counter(), collections.Counter(), 0
    for f in PROJECTS.glob("*/*.jsonl"):
        if f.stat().st_mtime < since:
            continue
        sessions += 1
        with f.open(errors="replace") as fh:
            for line in fh:
                if '"attachment"' not in line:
                    continue
                try:
                    a = json.loads(line).get("attachment") or {}
                except ValueError:
                    continue
                t = a.get("type", "")
                if t == "hook_non_blocking_error":
                    fails[(a.get("hookEvent", "?"), (a.get("stderr") or "")[:70])] += 1
                elif t in INJECTED:
                    who = t
                    if t.startswith("hook"):
                        who = f"hook {a.get('hookName') or a.get('hookEvent')}: {str(a.get('command', ''))[-50:]}"
                    size[who] += len(json.dumps(a.get("content") or a.get("stdout") or a)) // 4
    return size, fails, sessions


def mcp_servers():
    out = {}
    try:
        d = json.loads((Path.home() / ".claude.json").read_text())
    except (OSError, ValueError):
        return out
    for n in d.get("mcpServers") or {}:
        out[n] = "user"
    for proj, v in (d.get("projects") or {}).items():
        for n in v.get("mcpServers") or {}:
            out.setdefault(n, f"project {proj}")
    return out


def profile(project, days, undo=False):
    """Per-project switches in .claude/settings.local.json: skillOverrides "off" for personal skills and a
    permissions.deny "mcp__<server>__*" for user MCP servers this project never used. A deny rule on a whole server
    removes its tools from Claude's context. What we added is recorded in .claude/lean-profile.json for --unprofile."""
    proj = Path(project).resolve()
    f, rec = proj / ".claude" / "settings.local.json", proj / ".claude" / "lean-profile.json"
    try:
        s = json.loads(f.read_text()) if f.exists() else {}
        old = json.loads(rec.read_text()) if rec.exists() else {}
    except ValueError:
        sys.exit(f"{f} or {rec} is not valid JSON; fix it first.")
    if f.exists():
        shutil.copy2(f, f.with_suffix(f".json.lean-{time.strftime('%Y%m%d-%H%M%S')}.bak"))
    ov = s.get("skillOverrides", {})
    for n in old.get("skills", []):
        if ov.get(n) == "off":
            del ov[n]
    deny = s.get("permissions", {}).get("deny", [])
    deny[:] = [r for r in deny if r not in old.get("deny", [])]
    added = {"skills": [], "deny": []}
    if not undo:
        folder = slug(proj)
        if not (PROJECTS / folder).is_dir():
            sys.exit(f"no Claude Code logs for {proj} yet; use it for a while first.")
        used, mcp_used, sessions, _ = usage(days, folder)
        if sessions < 3:
            sys.exit(f"only {sessions} session logs for {proj}; profile after a few more sessions.")
        skills = [i for d in sorted(SKILLS.iterdir()) if d.is_dir() and (i := skill_info(d))] if SKILLS.exists() else []
        for sk in skills:
            if not used[sk["name"]] and not used[sk["dir"].name] and sk["name"] not in KEEP and sk["name"] not in ov:
                ov[sk["name"]] = "off"
                added["skills"].append(sk["name"])
        for n, where in mcp_servers().items():
            r = f"mcp__{n}__*"
            if where == "user" and not mcp_used[n] and r not in deny:
                deny.append(r)
                added["deny"].append(r)
    if ov:
        s["skillOverrides"] = ov
    else:
        s.pop("skillOverrides", None)
    if deny:
        s.setdefault("permissions", {})["deny"] = deny
    elif "permissions" in s:
        s["permissions"].pop("deny", None)
        if not s["permissions"]:
            del s["permissions"]
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(s, indent=2) + "\n")
    if undo or not (added["skills"] or added["deny"]):
        rec.unlink(missing_ok=True)
    else:
        rec.write_text(json.dumps(added, indent=2) + "\n")
    if undo:
        print(f"Removed Claude Lean's project profile from {f}.")
        return
    print(f"{f}: {len(added['skills'])} skills off, {len(added['deny'])} MCP servers denied (unused in this project, "
          f"last {days} days).")
    for n in added["skills"]:
        print(f"  skill off   {n}")
    for r in added["deny"]:
        print(f"  deny        {r}")
    print(f"Applies to new sessions in {proj}. Undo: claude-lean audit --unprofile {proj}")


def move(names, src, dst):
    dst.mkdir(parents=True, exist_ok=True)
    for n in names:
        s = src / n
        if not s.is_dir():
            print(f"skip {n}: not in {src}")
            continue
        if (dst / n).exists():
            print(f"skip {n}: already in {dst}")
            continue
        shutil.move(str(s), str(dst / n))
        print(f"moved {n} -> {dst / n}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--disable-unused", action="store_true")
    ap.add_argument("--disable", nargs="+", metavar="NAME")
    ap.add_argument("--restore", nargs="*", metavar="NAME")
    ap.add_argument("--profile", nargs="?", const=".", metavar="DIR")
    ap.add_argument("--unprofile", nargs="?", const=".", metavar="DIR")
    a = ap.parse_args()

    if a.profile or a.unprofile:
        return profile(a.profile or a.unprofile, a.days, undo=bool(a.unprofile))

    if a.restore is not None:
        names = a.restore or [d.name for d in PARKED.iterdir() if d.is_dir()] if PARKED.exists() else []
        move(names, PARKED, SKILLS)
        print("Restored. New Claude Code sessions load them again.")
        return
    if a.disable:
        move(a.disable, SKILLS, PARKED)
        print(f"Done. Undo: claude-lean audit --restore {' '.join(a.disable)}")
        return

    used, mcp_used, sessions, oldest = usage(a.days)
    skills = [i for d in sorted(SKILLS.iterdir()) if d.is_dir() and (i := skill_info(d))] if SKILLS.exists() else []
    unused = [s for s in skills if not used[s["name"]] and not used[s["dir"].name] and s["name"] not in KEEP]

    span = (time.time() - oldest) / 86400
    print(f"Last {a.days} days: {sessions} session logs, the oldest from {span:.0f} days ago.")
    if span < a.days * 0.8:
        print("Claude Code deletes logs after cleanupPeriodDays (default 30), so skills used before then show as unused. "
              "Keep any you use now and then.")
    print()
    print(f"{'uses':>5} {'~tokens':>8} {'when run':>9}  personal skill (~/.claude/skills)")
    for s in sorted(skills, key=lambda s: (used[s['name']] + used[s['dir'].name], -s["tokens"])):
        n = used[s["name"]] + used[s["dir"].name]
        big = "   <- large: stays in the context after it runs" if s["body"] > 8000 else ""
        print(f"{n:>5} {s['tokens']:>8} {s['body']:>9}  {s['name']}{'' if n or s['name'] in KEEP else '   <- unused'}{big}")
    cost = sum(s["tokens"] for s in unused)
    print(f"\nUnused skills: {len(unused)} of {len(skills)} (descriptions ~{cost} tokens; Claude Code caps the skill "
          "listing, so the real per-request saving is smaller: measure with `claude -p hi --output-format json`).")

    servers = mcp_servers()
    seen = set(servers) | set(mcp_used)
    if seen:
        print(f"\n{'uses':>5}  MCP server")
        for n in sorted(seen, key=lambda n: mcp_used[n]):
            where = servers.get(n, "claude.ai connector or plugin")
            print(f"{mcp_used[n]:>5}  {n}  ({where}){'   <- unused' if not mcp_used[n] else ''}")
        idle = [n for n in servers if not mcp_used[n]]
        if idle:
            print("\nRemove an unused MCP server: claude mcp remove <name> (-s user for user scope). "
                  "claude.ai connectors are switched off in claude.ai settings.")

    size, fails, n = injected(a.days)
    if size:
        print(f"\nAdded to the context without you asking ({n} sessions; tokens per session, each re-read every later turn)")
        for k, v in size.most_common(8):
            print(f"{v // max(n, 1):>7}  {k}")
    if fails:
        print("\nHooks that keep failing (each failure adds a delay to that event; fix or remove them in settings.json)")
        for (ev, err), c in fails.most_common(5):
            print(f"{c:>7}x  {ev}: {err}")
    try:
        style = json.loads((CLAUDE / "settings.json").read_text()).get("outputStyle")
    except (OSError, ValueError):
        style = None
    if style and style.lower() not in ("default", ""):
        print(f"\nOutput style \"{style}\" is on: its instructions ride in every request, and explanatory or learning "
              "styles write longer answers (output costs 5x input). /output-style default turns it off.")

    if a.disable_unused:
        if not unused:
            print("\nNothing to disable.")
            return
        print()
        move([s["dir"].name for s in unused], SKILLS, PARKED)
        print("\nDone. Undo all: claude-lean audit --restore")
    elif unused:
        print("\nPark them all (reversible): claude-lean audit --disable-unused")


if __name__ == "__main__":
    sys.exit(main())
