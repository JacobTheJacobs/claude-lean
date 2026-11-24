"""Tests for the hooks, the output filter and the installer. Standard library only: python3 -m unittest discover -s tests"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQUEEZE = ROOT / "tools" / "squeeze.py"


def run(script, stdin="", env=None, args=()):
    e = {**os.environ, **(env or {})}
    return subprocess.run([sys.executable, str(script), *args], input=stdin, capture_output=True, text=True, env=e)


def hook(script, payload, env=None):
    out = run(ROOT / "hooks" / script, json.dumps(payload), env).stdout.strip()
    return json.loads(out) if out else None


PYTEST_LOG = "\n".join(
    ["============ test session starts ============", "collected 300 items"]
    + [f"tests/test_a.py::test_{i} PASSED [{i // 3}%]" for i in range(299)]
    + ["tests/test_a.py::test_bad FAILED [100%]", "E   assert 40 == 41",
       "FAILED tests/test_a.py::test_bad - assert 40 == 41", "===== 1 failed, 299 passed in 0.4s ====="])


class Squeeze(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {"LEAN_CACHE": self.tmp.name}

    def tearDown(self):
        self.tmp.cleanup()

    def squeeze(self, text, tool="pytest"):
        return run(SQUEEZE, text, self.env, ("filter", tool)).stdout

    def test_keeps_failures_drops_passes(self):
        out = self.squeeze(PYTEST_LOG)
        self.assertIn("test_bad FAILED", out)
        self.assertIn("assert 40 == 41", out)
        self.assertIn("1 failed, 299 passed", out)
        self.assertNotIn("test_5 PASSED", out)
        self.assertLess(len(out), len(PYTEST_LOG) / 5)

    def test_broken_cache_passes_output_through(self):
        blocker = Path(self.tmp.name) / "file"
        blocker.write_text("x")                      # the cache path is a file: saving the original must fail
        r = run(SQUEEZE, PYTEST_LOG, {"LEAN_CACHE": str(blocker)}, ("filter", "pytest"))
        self.assertEqual(r.stdout, PYTEST_LOG)
        self.assertEqual(r.stderr, "")

    def test_no_3_10_only_syntax_at_import(self):
        for f in list((ROOT / "tools").glob("*.py")) + list((ROOT / "hooks").glob("*.py")):
            src = f.read_text()
            if " | None" in src:
                self.assertIn("from __future__ import annotations", src, f.name)

    def test_short_output_untouched(self):
        text = "line\n" * 10
        self.assertEqual(self.squeeze(text), text)

    def test_ansi_and_progress_stripped(self):
        text = "\n".join(f"\x1b[32mCompiling crate{i} v1.0.{i}\x1b[0m" for i in range(100)) + "\nerror[E0425]: oops"
        out = self.squeeze(text, "cargo")
        self.assertIn("error[E0425]: oops", out)
        self.assertNotIn("\x1b[", out)
        self.assertNotIn("Compiling crate", out)

    def test_get_returns_original_and_gives_up(self):
        out = self.squeeze(PYTEST_LOG)
        rid = out.rsplit(" get ", 1)[1].rstrip("]\n")
        for i in range(3):
            got = run(SQUEEZE, env=self.env, args=("get", rid)).stdout
            self.assertTrue(got.startswith(PYTEST_LOG))
        self.assertIn("now off", got)
        self.assertEqual(self.squeeze(PYTEST_LOG), PYTEST_LOG)       # filter off: passes through
        run(SQUEEZE, env=self.env, args=("on", "pytest"))
        self.assertNotEqual(self.squeeze(PYTEST_LOG), PYTEST_LOG)

    def test_get_rejects_paths(self):
        r = run(SQUEEZE, env=self.env, args=("get", "../../etc/passwd"))
        self.assertNotEqual(r.returncode, 0)

    def test_stats(self):
        self.squeeze(PYTEST_LOG)
        out = run(SQUEEZE, env=self.env, args=("stats",)).stdout
        self.assertIn("pytest", out)


class SqueezeHook(unittest.TestCase):
    def rewrite(self, cmd, **extra):
        r = hook("squeeze_hook.py", {"tool_name": "Bash", "tool_input": {"command": cmd, **extra}})
        return r and r["hookSpecificOutput"]["updatedInput"]["command"]

    def test_rewrites_noisy(self):
        for cmd in ("pytest -x", "npm install", "cargo test", "FOO=1 python3 -m pytest tests", "docker build ."):
            new = self.rewrite(cmd)
            self.assertTrue(new and new.startswith(cmd + " 2>&1 | python3 "), cmd)

    def test_leaves_others(self):
        for cmd in ("git status", "npm ls", "ls -la", "pytest | head", "pytest && rm x", "make > log", "echo $(pytest)"):
            self.assertIsNone(self.rewrite(cmd), cmd)

    def test_long_running_left_alone(self):
        for cmd in ("npm run dev", "npm start", "pnpm run serve", "cargo run", "jest --watch", "tsc -w",
                    "docker compose up", "docker-compose up", "uv run app.py", "npm run storybook"):
            self.assertIsNone(self.rewrite(cmd), cmd)
        for cmd in ("npm run build", "npm run test:unit", "uv run pytest -x", "poetry run pytest", "yarn run lint"):
            self.assertTrue(self.rewrite(cmd), cmd)

    def test_no_permission_decision(self):
        r = hook("squeeze_hook.py", {"tool_name": "Bash", "tool_input": {"command": "pytest"}})
        self.assertNotIn("permissionDecision", r["hookSpecificOutput"])

    def test_background_and_off(self):
        self.assertIsNone(self.rewrite("pytest", run_in_background=True))
        r = hook("squeeze_hook.py", {"tool_name": "Bash", "tool_input": {"command": "pytest"}}, {"LEAN_SQUEEZE": "0"})
        self.assertIsNone(r)


class OtherHooks(unittest.TestCase):
    def test_cache_guard(self):
        r = hook("cache_guard.py", {"tool_input": {"file_path": "/x/CLAUDE.md"}})
        self.assertIn("systemMessage", r)
        self.assertIsNone(hook("cache_guard.py", {"tool_input": {"file_path": "/x/app.py"}}))

    def test_session_guard(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "t.jsonl"
            usage = lambda n: json.dumps({"message": {"usage": {"input_tokens": 1, "cache_read_input_tokens": n}}})
            t.write_text(usage(5000) + "\n")
            env = {"HOME": d}
            self.assertIsNone(hook("session_guard.py", {"transcript_path": str(t), "session_id": "s"}, env))
            t.write_text(usage(150_000) + "\n")
            r = hook("session_guard.py", {"transcript_path": str(t), "session_id": "s"}, env)
            self.assertIn("/clear", r["systemMessage"])
            self.assertIsNone(hook("session_guard.py", {"transcript_path": str(t), "session_id": "s"}, env))  # once

    def test_terse(self):
        r = hook("terse_hook.py", {"source": "startup"})
        self.assertEqual(r["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("smallest change", r["hookSpecificOutput"]["additionalContext"])
        self.assertIn("subagent", r["hookSpecificOutput"]["additionalContext"])
        off = hook("terse_hook.py", {"source": "startup"}, {"LEAN_TERSE": "0"})["hookSpecificOutput"]["additionalContext"]
        self.assertIn("subagent", off)                # fan-out rule stays: slim alone caused it
        self.assertIn("WebFetch", off)
        self.assertIn("never edit or delete an existing test", off)   # SWE-bench django-13297: Lean edited tests to fit its fix
        self.assertNotIn("smallest change", off)

    def test_web_guard(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td) / "t.jsonl"
            qs = ["prompt compression open source GitHub 2025", "KV cache eviction methods"]
            t.write_text("".join(json.dumps({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": f"u{i}", "name": "WebSearch", "input": {"query": q}}]}}) + "\n"
                for i, q in enumerate(qs)))
            ask = lambda q, env=None: hook("web_guard.py", {"transcript_path": str(t), "tool_input": {"query": q}},
                                           dict(env or {}, LEAN_WEB_SEARCH="0"))         # no network in tests
            self.assertIsNone(ask("semantic caching for LLM apps"))                       # new topic: allowed
            r = ask("GitHub prompt compression 2024 open source")                         # same content words
            self.assertEqual(r["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertIn("repeats", r["hookSpecificOutput"]["permissionDecisionReason"])
            r = ask("tokenizer libraries", {"LEAN_WEB_SEARCHES": "2"})                     # over the cap
            self.assertIn("WebFetch", r["hookSpecificOutput"]["permissionDecisionReason"])
            self.assertIsNone(ask("tokenizer libraries", {"LEAN_WEB_SEARCHES": "0"}))     # cap off

    def test_web_guard_parsers(self):
        sys.path.insert(0, str(ROOT / "hooks"))
        import web_guard as w
        page = ('<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fgithub.com%2Fmicrosoft'
                '%2FLLMLingua&amp;rut=x">GitHub - microsoft/LLMLingua</a><a class="result__snippet" href="#">Prompt '
                '<b>compression</b> for LLMs</a>')
        self.assertEqual(w.ddg(page), [("GitHub - microsoft/LLMLingua", "https://github.com/microsoft/LLMLingua",
                                        "Prompt compression for LLMs")])
        needles = [x[:6] for x in w.words("prompt compression library") if len(x) >= 4]
        self.assertTrue(w.on_topic(("LLMLingua", "https://x.org", "prompt compression"), needles))
        self.assertFalse(w.on_topic(("PROMPT definition", "https://dictionary.com", "to make happen"), needles))

    def test_read_guard(self):
        with tempfile.TemporaryDirectory() as td:
            big, t = Path(td) / "big.txt", Path(td) / "t.jsonl"
            big.write_text("x\n" * 1500)
            t.write_text("")
            pre = lambda ti: hook("read_guard.py", {"hook_event_name": "PreToolUse", "transcript_path": str(t),
                                                    "tool_input": ti})
            r = pre({"file_path": str(big)})
            self.assertEqual(r["hookSpecificOutput"]["permissionDecision"], "deny")         # big, no range
            self.assertIsNone(pre({"file_path": str(big), "limit": 100}))                   # a range is fine
            t.write_text(json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "is_error": True,
                "content": r["hookSpecificOutput"]["permissionDecisionReason"]}]}}) + "\n")
            self.assertIsNone(pre({"file_path": str(big)}))                                 # repeated: allowed
            # identical re-read -> note; changed content -> untouched
            f = {"filePath": "/x/a.py", "content": "print(1)\n", "numLines": 2, "startLine": 1, "totalLines": 2}
            t.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "r1",
                "name": "Read", "input": {"file_path": "/x/a.py"}}]}}) + "\n" + json.dumps({"type": "user",
                "message": {"content": [{"type": "tool_result", "tool_use_id": "r1", "content": "1\tprint(1)"}]},
                "toolUseResult": {"type": "text", "file": f}}) + "\n")
            post = lambda content: hook("read_guard.py", {"hook_event_name": "PostToolUse", "transcript_path": str(t),
                "tool_use_id": "r2", "tool_input": {"file_path": "/x/a.py"},
                "tool_response": {"type": "text", "file": dict(f, content=content)}})
            r = post("print(1)\n")
            self.assertIn("Unchanged", r["hookSpecificOutput"]["updatedToolOutput"]["file"]["content"])
            self.assertIsNone(post("print(2)\n"))

    def test_read_guard_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            nb = Path(td) / "n.ipynb"
            nb.write_text('{"cells": [{"outputs": ["' + "A" * 200_000 + '"]}]}')     # 1 line, 200 KB
            r = hook("read_guard.py", {"hook_event_name": "PreToolUse", "transcript_path": "",
                                       "tool_input": {"file_path": str(nb)}})
            self.assertIn("200,0", r["hookSpecificOutput"]["permissionDecisionReason"])

    def test_read_guard_cat(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "big.log").write_text("x\n" * 3000)
            bash = lambda c: hook("read_guard.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": td,
                                                    "transcript_path": "", "tool_input": {"command": c}})
            self.assertEqual(bash("cat big.log")["hookSpecificOutput"]["permissionDecision"], "deny")
            self.assertFalse(bash("cat big.log | grep x"))      # piped: output is already narrowed
            self.assertFalse(bash("tail -50 big.log"))          # ranged
            src = Path(td) / "m.py"
            src.write_text("# comment\n" + "".join(f"def f{i}():\n" + "    pass\n" * 300 for i in range(4)))
            why = hook("read_guard.py", {"hook_event_name": "PreToolUse", "transcript_path": "",
                                         "tool_input": {"file_path": str(src)}})["hookSpecificOutput"]["permissionDecisionReason"]
            self.assertIn("2: def f0():", why)                   # outline with line numbers
            self.assertNotIn("comment", why)

    def test_paste_note(self):
        r = hook("session_guard.py", {"prompt": "x" * 50_000})
        self.assertIn("stays in the context", r["systemMessage"])
        self.assertIsNone(hook("session_guard.py", {"prompt": "short"}))

    def test_statusline(self):
        d = {"model": {"display_name": "Opus"}, "cost": {"total_cost_usd": 1.5},
             "context_window": {"used_percentage": 40}, "prompt_cache": {"hit_ratio": 0.9}}
        out = run(ROOT / "tools" / "statusline.py", json.dumps(d)).stdout.strip()
        self.assertEqual(out, "Opus | $1.50 | context 40% | cache 90%")
        self.assertEqual(run(ROOT / "tools" / "statusline.py", "garbage").stdout.strip(), "Claude")

    def test_audit_profile(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as proj:
            h = Path(home)
            for n in ("used", "idle"):
                (h / ".claude/skills" / n).mkdir(parents=True)
                (h / ".claude/skills" / n / "SKILL.md").write_text(f"---\nname: {n}\ndescription: d\n---\nbody")
            (h / ".claude.json").write_text(json.dumps({"mcpServers": {"gh": {}, "db": {}}}))
            import re as _re
            logs = h / ".claude/projects" / _re.sub(r"[^A-Za-z0-9]", "-", str(Path(proj).resolve()))
            logs.mkdir(parents=True)
            for i in range(3):
                (logs / f"s{i}.jsonl").write_text(json.dumps({"message": {"content": [
                    {"type": "tool_use", "name": "Skill", "input": {"skill": "used"}},
                    {"type": "tool_use", "name": "mcp__gh__list", "input": {}}]}}) + "\n")
            local = Path(proj) / ".claude/settings.local.json"
            local.parent.mkdir()
            local.write_text(json.dumps({"permissions": {"deny": ["Bash(rm *)"]}}))
            env = {"HOME": home}
            out = run(ROOT / "tools" / "audit.py", "", env, ("--profile", proj))
            s = json.loads(local.read_text())
            self.assertEqual(s["skillOverrides"], {"idle": "off"}, out.stdout + out.stderr)
            self.assertEqual(s["permissions"]["deny"], ["Bash(rm *)", "mcp__db__*"])
            run(ROOT / "tools" / "audit.py", "", env, ("--unprofile", proj))
            self.assertEqual(json.loads(local.read_text()), {"permissions": {"deny": ["Bash(rm *)"]}})

    def test_cache_expired_note(self):
        import datetime as dt
        with tempfile.TemporaryDirectory() as td:
            t = Path(td) / "t.jsonl"
            old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)).isoformat().replace("+00:00", "Z")
            t.write_text(json.dumps({"type": "assistant", "timestamp": old, "message": {"usage": {
                "input_tokens": 10, "cache_read_input_tokens": 80_000, "cache_creation_input_tokens": 0}}}) + "\n")
            r = hook("session_guard.py", {"transcript_path": str(t), "session_id": "x", "prompt": "hi"},
                     {"HOME": td, "ANTHROPIC_API_KEY": ""})
            self.assertIn("cache has expired", r["systemMessage"])

    def test_web_fetch_repeat(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td) / "t.jsonl"
            t.write_text(json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "f1",
                "name": "WebFetch", "input": {"url": "https://a.org/x", "prompt": "list repos"}}]}}) + "\n")
            ask = lambda prompt: hook("web_guard.py", {"tool_name": "WebFetch", "transcript_path": str(t),
                                                       "tool_use_id": "f2",
                                                       "tool_input": {"url": "https://a.org/x", "prompt": prompt}})
            self.assertIn("already fetched", ask("list repos")["hookSpecificOutput"]["permissionDecisionReason"])
            self.assertIsNone(ask("what license?"))

    def test_loop_guard_edit(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td) / "t.jsonl"
            rows = []
            for i in range(2):
                rows.append({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": f"e{i}",
                             "name": "Edit", "input": {"file_path": "/x/a.py", "old_string": f"v{i}"}}]}})
                rows.append({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": f"e{i}",
                             "is_error": True, "content": "String to replace not found in file."}]}})
            t.write_text("".join(json.dumps(r) + "\n" for r in rows))
            r = hook("loop_guard.py", {"tool_name": "Edit", "transcript_path": str(t), "tool_use_id": "e9",
                                       "tool_input": {"file_path": "/x/a.py"},
                                       "error": "String to replace not found in file."})
            self.assertIn("Read the exact current lines", r["hookSpecificOutput"]["additionalContext"])

    def test_loop_guard(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td) / "t.jsonl"
            rows = []
            for i in range(2):
                rows.append({"type": "assistant", "message": {"content": [{"type": "tool_use", "id": f"b{i}",
                             "name": "Bash", "input": {"command": "make test"}}]}})
                rows.append({"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": f"b{i}",
                             "is_error": True, "content": "Exit code 2\nE: missing x"}]}})
            t.write_text("".join(json.dumps(r) + "\n" for r in rows))
            ask = lambda cmd: hook("loop_guard.py", {"transcript_path": str(t), "tool_use_id": "b9",
                                                     "tool_input": {"command": cmd}, "error": "Exit code 2\nE: missing x"})
            self.assertIn("failed 3 times", ask("make test")["hookSpecificOutput"]["additionalContext"])
            self.assertIsNone(ask("make lint"))

    def test_mcp_compact(self):
        text = json.dumps({"next": None, "items": [{"id": 1, "x": None, "tags": [], "ok": False, "n": 0, "s": ""}]},
                          indent=2)
        r = hook("mcp_compact.py", {"tool_response": [{"type": "text", "text": text}]})
        out = r["hookSpecificOutput"]["updatedMCPToolOutput"][0]["text"]
        self.assertEqual(json.loads(out), {"next": None, "items": [{"id": 1, "tags": [], "ok": False, "n": 0}]})
        self.assertIsNone(hook("mcp_compact.py", {"tool_response": [{"type": "text", "text": "plain words"}]}))

    def test_hooks_never_crash_on_garbage(self):
        for h in ("session_guard.py", "cache_guard.py", "squeeze_hook.py", "budget.py", "handoff_hook.py", "terse_hook.py", "web_guard.py",
                  "read_guard.py", "loop_guard.py", "mcp_compact.py", "compact_hook.py"):
            r = run(ROOT / "hooks" / h, "not json")
            self.assertEqual(r.returncode, 0, h)


class Handoff(unittest.TestCase):
    def test_save_load_once_per_folder(self):
        with tempfile.TemporaryDirectory() as cache, tempfile.TemporaryDirectory() as proj:
            env = {"LEAN_CACHE": cache}
            tool = ROOT / "tools" / "handoff.py"
            r = subprocess.run([sys.executable, str(tool), "save"], input="Goal: fix parse_price", cwd=proj,
                               capture_output=True, text=True, env={**os.environ, **env})
            self.assertIn("saved", r.stdout)
            other = hook("handoff_hook.py", {"source": "clear", "cwd": cache}, env)
            self.assertIsNone(other)                                                 # another folder: nothing
            got = hook("handoff_hook.py", {"source": "clear", "cwd": proj}, env)
            self.assertIn("Goal: fix parse_price", got["hookSpecificOutput"]["additionalContext"])
            self.assertIsNone(hook("handoff_hook.py", {"source": "clear", "cwd": proj}, env))   # used once
            self.assertIsNone(hook("handoff_hook.py", {"source": "compact", "cwd": proj}, env))


class Audit(unittest.TestCase):
    def test_finds_unused_and_parks_reversibly(self):
        with tempfile.TemporaryDirectory() as home:
            h = Path(home)
            for name in ("used-one", "never-used"):
                (h / ".claude/skills" / name).mkdir(parents=True)
                (h / ".claude/skills" / name / "SKILL.md").write_text(f"---\nname: {name}\ndescription: does {name}\n---\n")
            log = h / ".claude/projects/p/s.jsonl"
            log.parent.mkdir(parents=True)
            log.write_text(json.dumps({"message": {"content": [
                {"type": "tool_use", "name": "Skill", "input": {"skill": "used-one"}},
                {"type": "tool_use", "name": "mcp__srv__do", "input": {}}]}}) + "\n")
            env = {"HOME": home}
            out = run(ROOT / "tools/audit.py", env=env).stdout
            self.assertIn("never-used   <- unused", out)
            self.assertNotIn("used-one   <- unused", out)
            run(ROOT / "tools/audit.py", env=env, args=("--disable-unused",))
            self.assertFalse((h / ".claude/skills/never-used").exists())
            self.assertTrue((h / ".claude/skills-disabled/never-used/SKILL.md").exists())
            self.assertTrue((h / ".claude/skills/used-one").exists())
            run(ROOT / "tools/audit.py", env=env, args=("--restore",))
            self.assertTrue((h / ".claude/skills/never-used/SKILL.md").exists())


class Installer(unittest.TestCase):
    def install(self, d, *args, env=None):
        e = {**os.environ, "CLAUDE_DIR": d, **(env or {})}
        return subprocess.run(["bash", str(ROOT / "install.sh"), *args], capture_output=True, text=True, env=e)

    def test_install_idempotent_uninstall_restores(self):
        with tempfile.TemporaryDirectory() as d:
            mine = {"model": "x", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]},
                    "permissions": {"allow": ["Read"], "deny": ["Read(**/*.map)"]}}  # user's own deny rule
            f = Path(d) / "settings.json"
            f.write_text(json.dumps(mine))
            self.assertEqual(self.install(d, "--dry-run").returncode, 0)
            self.assertEqual(json.loads(f.read_text()), mine)                          # dry run writes nothing
            self.install(d, "--reader")
            once = f.read_text()
            self.install(d, "--reader")
            self.assertEqual(f.read_text(), once)                                      # re-run: no duplicates
            s = json.loads(once)
            self.assertEqual(s["hooks"]["Stop"], mine["hooks"]["Stop"])
            self.assertEqual(len(s["hooks"]["PreToolUse"]), 4)       # cache guard, web guard, read guard, filter
            self.assertIn("Read(**/node_modules/**)", s["permissions"]["deny"])
            self.assertEqual(s["permissions"]["deny"].count("Read(**/*.map)"), 1)      # not added twice
            self.assertTrue((Path(d) / "agents/reader.md").exists())
            skill = (Path(d) / "skills/handoff/SKILL.md").read_text()
            self.assertIn(str(ROOT / "tools" / "handoff.py"), skill)                   # path filled in
            self.install(d, "--uninstall", "--reader")
            self.assertEqual(json.loads(f.read_text()), mine)
            self.assertFalse((Path(d) / "agents/reader.md").exists())

    def test_replaces_hooks_from_another_install(self):
        with tempfile.TemporaryDirectory() as d:
            old = lambda c: {"hooks": [{"type": "command", "command": c}]}
            f = Path(d) / "settings.json"
            f.write_text(json.dumps({"hooks": {"SessionStart": [old("python3 /old/claude-lean/hooks/terse_hook.py"),
                                                                old("python3 /other/hooks/terse_hook.py")]}}))
            self.install(d)
            cmds = [h["command"] for g in json.loads(f.read_text())["hooks"]["SessionStart"] for h in g["hooks"]]
            self.assertNotIn("python3 /old/claude-lean/hooks/terse_hook.py", cmds)   # stale Lean copy removed
            self.assertIn("python3 /other/hooks/terse_hook.py", cmds)                # someone else's hook kept

    def test_slim_keeps_user_env(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "settings.json"
            mine = {"env": {"FOO": "1", "CLAUDE_CODE_DISABLE_CRON": "1"}, "permissions": {"deny": ["ListAgents"]}}
            f.write_text(json.dumps(mine))
            self.install(d)
            s = json.loads(f.read_text())
            env = s["env"]
            self.assertEqual(env["CLAUDE_CODE_DISABLE_ARTIFACT"], "1")
            self.assertNotIn("CLAUDE_CODE_DISABLE_CRON", env["CLAUDE_LEAN_SLIM"])   # was the user's own
            self.assertEqual(s["permissions"]["deny"].count("ListAgents"), 1)       # user's own, not added twice
            self.assertEqual(s["skillListingMaxDescChars"], 200)
            self.install(d)
            self.assertEqual(json.loads(f.read_text()), s)                          # re-run changes nothing
            self.install(d, "--uninstall")
            self.assertEqual(json.loads(f.read_text()), mine)
            self.install(d, "--no-slim")
            self.assertNotIn("CLAUDE_CODE_DISABLE_ARTIFACT", f.read_text())

    def test_other_folder_and_shapes(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "settings.json"
            old = "python3 '/x/.claude-lean/tools/statusline.py'"
            f.write_text(json.dumps({"statusLine": {"type": "command", "command": old},
                                     "permissions": {"allow": ["Bash(python3 /x/claude-lean/tools/squeeze.py *)"]},
                                     "hooks": {"Stop": [{"hooks": [{"type": "command",
                                                                    "command": "python3 /x/claude-leaner/hooks/read_guard.py"}]}]}}))
            self.install(d)
            s = f.read_text()
            self.assertNotIn("/x/.claude-lean/", s)                          # old copy's status line replaced
            self.assertNotIn("/x/claude-lean/", s)                           # old copy's allow rule removed
            self.assertIn("/x/claude-leaner/hooks/read_guard.py", s)         # not a Lean folder: kept
            for start in ({"permissions": {}}, {"permissions": {"deny": []}}):      # slim on + off alone
                f.write_text(json.dumps(start))
                for c in ("on", "off"):
                    subprocess.run([sys.executable, str(ROOT / "tools/slim.py"), c], env={**os.environ, "CLAUDE_DIR": d},
                                   capture_output=True)
                self.assertEqual(json.loads(f.read_text()), start)
            f.write_text(json.dumps({"permissions": {"deny": "ListAgents"}}))
            r = self.install(d)
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(json.loads(f.read_text()), {"permissions": {"deny": "ListAgents"}})   # untouched

    def test_slim_keeps_user_desc_cap(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "settings.json"
            f.write_text(json.dumps({"skillListingMaxDescChars": 500}))
            self.install(d)
            self.assertEqual(json.loads(f.read_text())["skillListingMaxDescChars"], 500)
            self.install(d, "--uninstall")
            self.assertEqual(json.loads(f.read_text()), {"skillListingMaxDescChars": 500})

    def test_no_filter_and_day_cap(self):
        with tempfile.TemporaryDirectory() as d:
            self.install(d, "--no-filter", env={"LEAN_DAY_USD": "7.5"})
            s = (Path(d) / "settings.json").read_text()
            self.assertNotIn("squeeze", s)
            self.assertIn("LEAN_DAY_USD=7.5 python3", s)

    def test_bad_flag(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertNotEqual(self.install(d, "--nope").returncode, 0)


class Budget(unittest.TestCase):
    def test_today_usd_reads_only_new_lines(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import datetime as dt
        import report
        now = dt.datetime.now(dt.timezone.utc).isoformat()

        def line(i):
            return json.dumps({"timestamp": now, "message": {"id": f"m{i}", "model": "claude-opus-5-5",
                               "usage": {"input_tokens": 1_000_000, "output_tokens": 0}}}) + "\n"
        with tempfile.TemporaryDirectory() as d:
            old_root, report.ROOT = report.ROOT, Path(d)
            try:
                t = Path(d) / "proj" / "s.jsonl"
                t.parent.mkdir()
                t.write_text(line(1))
                state = {}
                one = report.today_usd(None, state)
                self.assertGreater(one, 0)
                self.assertEqual(report.today_usd(None, state), one)          # nothing new: same total
                with t.open("a") as f:
                    f.write(line(2) + line(2))                                # same message id twice: counted once
                self.assertAlmostEqual(report.today_usd(None, state), 2 * one)
                self.assertAlmostEqual(report.today_usd(None), 2 * one)       # a cold read agrees
            finally:
                report.ROOT = old_root


if __name__ == "__main__":
    unittest.main()
