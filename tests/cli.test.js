// node --test tests/cli.test.js: init/uninstall through the CLI into throwaway folders, including an upgrade from an
// old (0.2.x) install whose hooks point into ~/.claude-lean.
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const CLI = path.resolve(__dirname, "..", "bin", "cli.js");

function sandbox() {
  const t = fs.mkdtempSync(path.join(os.tmpdir(), "lean-cli-"));
  const env = { ...process.env, HOME: t, LEAN_HOME: path.join(t, ".claude-lean"), CLAUDE_CONFIG_DIR: path.join(t, ".claude") };
  fs.mkdirSync(env.CLAUDE_CONFIG_DIR);
  const cli = (...a) => spawnSync("node", [CLI, ...a], { env, encoding: "utf8" });
  const settings = () => JSON.parse(fs.readFileSync(path.join(env.CLAUDE_CONFIG_DIR, "settings.json"), "utf8"));
  return { t, env, cli, settings };
}

test("init then uninstall leaves settings as they were", () => {
  const { env, cli, settings } = sandbox();
  fs.writeFileSync(path.join(env.CLAUDE_CONFIG_DIR, "settings.json"), JSON.stringify({ model: "sonnet" }));
  assert.strictEqual(cli("init").status, 0);
  const s = settings();
  assert.strictEqual(s.skillListingMaxDescChars, 200);
  assert.ok(s.hooks.PreToolUse[0].hooks[0].command.includes(path.join(env.LEAN_HOME, "hooks", "cache_guard.py")));
  assert.strictEqual(cli("doctor").status, 0);
  assert.strictEqual(cli("uninstall").status, 0);
  assert.deepStrictEqual(settings(), { model: "sonnet" });
  assert.ok(!fs.existsSync(env.LEAN_HOME));
});

test("upgrade from 0.2.x runs the old uninstaller before replacing the folder", () => {
  const { env, cli, settings } = sandbox();
  fs.mkdirSync(env.LEAN_HOME);
  fs.writeFileSync(path.join(env.LEAN_HOME, "VERSION"), "0.2.8\n");
  const oldHook = { type: "command", command: `python3 ${env.LEAN_HOME}/hooks/web_guard.py` };
  fs.writeFileSync(path.join(env.CLAUDE_CONFIG_DIR, "settings.json"),
    JSON.stringify({ hooks: { PreToolUse: [{ matcher: "WebSearch", hooks: [oldHook] }] } }));
  // stand-in for the old installer: its --uninstall removes the old hook entry
  fs.writeFileSync(path.join(env.LEAN_HOME, "install.sh"),
    `[ "$1" = --uninstall ] && echo '{}' > "$CLAUDE_CONFIG_DIR/settings.json"\n`);
  assert.strictEqual(cli("init").status, 0);
  const cmds = settings().hooks.PreToolUse.flatMap((g) => g.hooks.map((h) => h.command));
  assert.ok(!cmds.includes(oldHook.command));
  assert.strictEqual(fs.readFileSync(path.join(env.LEAN_HOME, "VERSION"), "utf8").trim(),
    require("../package.json").version);
});
