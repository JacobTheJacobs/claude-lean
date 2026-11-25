import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

class Install(unittest.TestCase):
    def run_install(self, cfg, *a):
        subprocess.run(["bash", str(ROOT / "install.sh"), *a], env={**os.environ, "CLAUDE_CONFIG_DIR": cfg},
                       check=True, capture_output=True)
        return json.loads((Path(cfg) / "settings.json").read_text())

    def test_upgrade_removes_old_hooks_keeps_other_tools(self):
        with tempfile.TemporaryDirectory() as cfg:
            other = {"type": "command", "command": "python3 /home/u/.claude-lean/hooks/web_guard.py"}
            old = [{"type": "command", "command": f"python3 /x/boostv2/hooks/{n}"} for n in ("agy_search.py", "web_guard.py")]
            moved = {"type": "command", "command": "test -f /gone/hooks/cache_guard.py && python3 /gone/hooks/cache_guard.py; "
                                                   "exit 0 # claude-lean-v2"}
            (Path(cfg) / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
                {"matcher": "WebSearch", "hooks": [other, *old]}, {"matcher": "Edit", "hooks": [moved]}]}}))
            cmds = [h["command"] for g in self.run_install(cfg)["hooks"]["PreToolUse"] for h in g["hooks"]]
            self.assertEqual(len(cmds), 2)
            self.assertIn(other["command"], cmds)
            self.assertIn(str(ROOT / "hooks/cache_guard.py"), cmds[1])

    def test_missing_hook_never_blocks(self):
        with tempfile.TemporaryDirectory() as cfg:
            c = self.run_install(cfg)["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
            gone = c.replace(str(ROOT), "/nowhere")
            r = subprocess.run(["sh", "-c", gone], input='{"tool_input": {"file_path": "/p/CLAUDE.md"}}',
                               capture_output=True, text=True)
            self.assertEqual((r.returncode, r.stdout), (0, ""))
            r = subprocess.run(["sh", "-c", c], input='{"tool_input": {"file_path": "/p/CLAUDE.md"}}',
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            self.assertIn("cache", r.stdout)

    def test_old_marker_migrates(self):
        with tempfile.TemporaryDirectory() as cfg:
            (Path(cfg) / "settings.json").write_text(json.dumps({"idleCompaction": False, "permissions": {"deny": ["ListAgents"]},
                                                                 "env": {"BOOSTV2_ADDED": "setting:idleCompaction,deny:ListAgents"}}))
            s = self.run_install(cfg)
            self.assertNotIn("BOOSTV2_ADDED", s["env"])
            self.assertIn("setting:idleCompaction", s["env"]["CLAUDE_LEAN_V2_ADDED"])
            self.assertEqual(self.run_install(cfg, "--uninstall"), {})

    def test_value_changed_after_install_is_kept(self):
        with tempfile.TemporaryDirectory() as cfg:
            s = self.run_install(cfg)
            s["skillListingMaxDescChars"] = 500
            s["env"]["CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION"] = "true"
            (Path(cfg) / "settings.json").write_text(json.dumps(s))
            s = self.run_install(cfg)
            self.assertEqual((s["skillListingMaxDescChars"], s["env"]["CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION"]), (500, "true"))
            s = self.run_install(cfg, "--uninstall")
            self.assertEqual(s, {"skillListingMaxDescChars": 500, "env": {"CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION": "true"}})

    def test_roundtrip_keeps_user_settings(self):
        with tempfile.TemporaryDirectory() as cfg:
            mine = {"model": "sonnet", "env": {"FOO": "1"}, "permissions": {"deny": ["Read(./.env)"]},
                    "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "x"}]}]}}
            (Path(cfg) / "settings.json").write_text(json.dumps(mine))
            s = self.run_install(cfg, "--pin", "--cache-1h")
            s = self.run_install(cfg, "--pin", "--cache-1h")          # idempotent
            matchers = [g["matcher"] for g in s["hooks"]["PreToolUse"]]
            self.assertEqual(matchers, ["Bash", "Edit|Write|MultiEdit"])
            self.assertEqual(s["env"]["DISABLE_AUTOUPDATER"], "1")
            self.assertEqual(s["promptCacheTtl"], "1h")
            self.assertEqual(s["env"]["CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION"], "false")
            self.assertEqual((s["idleCompaction"], s["skillListingMaxDescChars"]), (False, 200))
            self.assertEqual(s["permissions"]["deny"], ["Read(./.env)", "ListAgents"])
            s = self.run_install(cfg)                                  # options dropped on re-run
            self.assertNotIn("DISABLE_AUTOUPDATER", s["env"])
            self.assertNotIn("promptCacheTtl", s)
            self.assertEqual(s["permissions"]["deny"], ["Read(./.env)", "ListAgents"])
            self.assertEqual(self.run_install(cfg, "--uninstall"), mine)

    def test_keeps_users_own_values(self):
        with tempfile.TemporaryDirectory() as cfg:
            mine = {"promptCacheTtl": "5m", "skillListingMaxDescChars": 500,
                    "env": {"DISABLE_AUTOUPDATER": "0"}, "permissions": {"deny": ["ListAgents"]}}
            (Path(cfg) / "settings.json").write_text(json.dumps(mine))
            s = self.run_install(cfg, "--pin", "--cache-1h")
            self.assertEqual((s["promptCacheTtl"], s["env"]["DISABLE_AUTOUPDATER"]), ("5m", "0"))
            self.assertEqual((s["skillListingMaxDescChars"], s["permissions"]["deny"]), (500, ["ListAgents"]))
            self.assertEqual(self.run_install(cfg, "--uninstall"), mine)


class CacheGuard(unittest.TestCase):
    def guard(self, path):
        r = subprocess.run([sys.executable, str(ROOT / "hooks/cache_guard.py")], capture_output=True, text=True,
                           input=json.dumps({"tool_name": "Edit", "tool_input": {"file_path": path}}))
        return r.stdout.strip()

    def test_warns_on_claude_md_only(self):
        self.assertIn("cache", json.loads(self.guard("/p/CLAUDE.md"))["systemMessage"])
        self.assertIn("cache", json.loads(self.guard("/p/.claude/settings.json"))["systemMessage"])
        self.assertEqual(self.guard("/p/app.py"), "")
        self.assertEqual(self.guard("/p/.vscode/settings.json"), "")


if __name__ == "__main__":
    unittest.main()
