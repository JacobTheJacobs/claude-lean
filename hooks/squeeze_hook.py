#!/usr/bin/env python3
"""Pipe noisy commands through tools/squeeze.py (PreToolUse hook, matcher "Bash").

Rewrites a plain `pytest -x` into `pytest -x 2>&1 | python3 .../squeeze.py filter pytest`. Only simple commands are
touched: anything with pipes, redirects, `;`, `&&`, subshells or several lines runs as written, and so do dev
servers and watchers (`npm run dev`, `--watch`, `docker compose up`), whose output must stream. The hook sets no
permission decision, so your normal permission rules and prompts still apply. A failing command's output still shows
every error line, but the pipe means the tool reports the filter's exit code instead of the command's.
Turn it off for one session with LEAN_SQUEEZE=0."""
import json
import os
import re
import shlex
import sys
from pathlib import Path

SQUEEZE = Path(__file__).resolve().parent.parent / "tools" / "squeeze.py"
# tool -> subcommands worth filtering (None = always)
NOISY = {
    "pytest": None, "py.test": None, "tox": None, "nox": None, "jest": None, "vitest": None, "mocha": None,
    "tsc": None, "eslint": None, "make": None, "cmake": None, "ninja": None, "mvn": None, "gradle": None,
    "./gradlew": None, "./mvnw": None, "rspec": None, "phpunit": None, "ctest": None,
    "npm": {"install", "i", "ci", "test", "t", "run", "build", "update", "audit"},
    "pnpm": {"install", "i", "add", "test", "run", "build", "update"},
    "yarn": {"install", "add", "test", "run", "build"},
    "bun": {"install", "test", "run", "build"},
    "pip": {"install", "download", "wheel"}, "pip3": {"install", "download", "wheel"},
    "uv": {"sync", "pip", "add"}, "poetry": {"install", "update", "add"},
    "cargo": {"build", "test", "check", "clippy", "install", "update", "fetch"},
    "go": {"build", "test", "vet", "get", "install", "mod", "generate"},
    "docker": {"build", "pull", "push"}, "docker-compose": {"build", "pull"},
    "dotnet": {"build", "test", "restore", "publish"},
}
SHELL_OPS = ("|", ";", "&", ">", "<", "`", "$(", "\n", "<<")
# The filter prints only after the command exits, so anything that keeps running (dev servers, watchers) is left alone.
LONG_RUNNING = {"--watch", "--watchAll", "-w", "watch", "dev", "serve", "start", "up"}
RUN_OK = re.compile(r"^(build|test|lint|typecheck|type-check|check|compile)\b")   # `npm run <script>` worth filtering


def tool_of(cmd):
    if any(op in cmd for op in SHELL_OPS):
        return None
    try:
        w = shlex.split(cmd)
    except ValueError:
        return None
    while w and "=" in w[0] and not w[0].startswith("="):      # FOO=1 pytest
        w = w[1:]
    if w[:2] in (["python", "-m"], ["python3", "-m"]):
        w = w[2:]
    if w[:1] in (["npx"], ["uvx"]) and len(w) > 1:
        w = w[1:]
    if w[:2] in (["uv", "run"], ["poetry", "run"]):              # uv run pytest -> pytest
        w = w[2:]
    if not w or LONG_RUNNING & set(w):
        return None
    if w[1:2] == ["run"] and not (len(w) > 2 and RUN_OK.match(w[2])):
        return None
    subs = NOISY.get(w[0])
    if w[0] not in NOISY:
        return None
    if subs is None or (len(w) > 1 and w[1] in subs):
        return w[0].lstrip("./")
    return None


def main():
    if os.environ.get("LEAN_SQUEEZE") == "0":
        return
    d = json.load(sys.stdin)
    if d.get("tool_name") != "Bash":
        return
    ti = d.get("tool_input") or {}
    cmd = (ti.get("command") or "").strip()
    if not cmd or ti.get("run_in_background") or str(SQUEEZE) in cmd:
        return
    tool = tool_of(cmd)
    if not tool:
        return
    new = f"{cmd} 2>&1 | python3 {shlex.quote(str(SQUEEZE))} filter {shlex.quote(tool)}"
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": {**ti, "command": new}}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
