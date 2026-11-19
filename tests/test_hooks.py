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

    def test_hooks_never_crash_on_garbage(self):
        for h in ("session_guard.py", "cache_guard.py", "squeeze_hook.py", "budget.py", "handoff_hook.py"):
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
                    "permissions": {"allow": ["Read"]}}
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
            self.assertEqual(len(s["hooks"]["PreToolUse"]), 2)
            self.assertTrue((Path(d) / "agents/reader.md").exists())
            skill = (Path(d) / "skills/handoff/SKILL.md").read_text()
            self.assertIn(str(ROOT / "tools" / "handoff.py"), skill)                   # path filled in
            self.install(d, "--uninstall", "--reader")
            self.assertEqual(json.loads(f.read_text()), mine)
            self.assertFalse((Path(d) / "agents/reader.md").exists())

    def test_slim_keeps_user_env(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "settings.json"
            f.write_text(json.dumps({"env": {"FOO": "1", "CLAUDE_CODE_DISABLE_CRON": "1"}}))
            self.install(d)
            env = json.loads(f.read_text())["env"]
            self.assertEqual(env["CLAUDE_CODE_DISABLE_ARTIFACT"], "1")
            self.assertNotIn("CLAUDE_CODE_DISABLE_CRON", env["CLAUDE_LEAN_SLIM"])   # was the user's own
            self.install(d, "--uninstall")
            self.assertEqual(json.loads(f.read_text()), {"env": {"FOO": "1", "CLAUDE_CODE_DISABLE_CRON": "1"}})
            self.install(d, "--no-slim")
            self.assertNotIn("CLAUDE_CODE_DISABLE_ARTIFACT", f.read_text())

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
