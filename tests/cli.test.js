// node --test tests/
const { test } = require("node:test");
const assert = require("node:assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const CLI = path.join(__dirname, "..", "bin", "cli.js");

function cli(args, env) {
  return spawnSync(process.execPath, [CLI, ...args], { encoding: "utf8", env: { ...process.env, ...env } });
}

test("help and version", () => {
  assert.match(cli(["--help"]).stdout, /claude-lean init/);
  assert.match(cli(["--version"]).stdout, /^\d+\.\d+\.\d+/);
  assert.notStrictEqual(cli(["nope"]).status, 0);
});

test("init, doctor, uninstall in a temp home", () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "lean-"));
  // a space in the path: home folders like "/Users/John Doe" must work
  const env = { LEAN_HOME: path.join(tmp, "lean home"), CLAUDE_DIR: path.join(tmp, "claude"), LEAN_CACHE: path.join(tmp, "cache") };
  const init = cli(["init"], env);
  assert.strictEqual(init.status, 0, init.stderr);
  assert.ok(fs.existsSync(path.join(env.LEAN_HOME, "hooks", "squeeze_hook.py")));
  const settings = fs.readFileSync(path.join(env.CLAUDE_DIR, "settings.json"), "utf8");
  assert.ok(settings.includes(path.join(env.LEAN_HOME, "hooks", "session_guard.py")));
  assert.strictEqual(cli(["doctor"], env).status, 0);
  for (const groups of Object.values(JSON.parse(settings).hooks)) {
    for (const h of groups.flatMap((g) => g.hooks)) {
      const r = spawnSync("sh", ["-c", h.command], { input: "{}", encoding: "utf8", env: { ...process.env, ...env } });
      assert.strictEqual(r.status, 0, `${h.command}: ${r.stderr}`);
      assert.strictEqual(r.stderr, "", h.command);
    }
  }
  fs.mkdirSync(env.LEAN_CACHE);
  const un = cli(["uninstall"], env);
  assert.strictEqual(un.status, 0, un.stderr);
  assert.ok(!fs.existsSync(env.LEAN_HOME));
  assert.ok(!fs.existsSync(env.LEAN_CACHE));
  assert.deepStrictEqual(JSON.parse(fs.readFileSync(path.join(env.CLAUDE_DIR, "settings.json"), "utf8")), {});
  fs.rmSync(tmp, { recursive: true, force: true });
});

test("lite passes the core tool set and user args to claude", () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "lean-"));
  const fake = path.join(tmp, "claude");
  fs.writeFileSync(fake, '#!/bin/sh\nprintf "%s\\n" "$@"\n', { mode: 0o755 });
  const out = cli(["lite", "-p", "hi"], { LEAN_CLAUDE: fake }).stdout.split("\n");
  assert.ok(out.includes("--tools") && out.includes("--strict-mcp-config") && out.includes("--disable-slash-commands"));
  assert.deepStrictEqual(out.slice(-3, -1), ["-p", "hi"]);
  fs.writeFileSync(fake, '#!/bin/sh\necho "slim=$CLAUDE_CODE_DISABLE_ARTIFACT"\n', { mode: 0o755 });
  assert.match(cli(["lite"], { LEAN_CLAUDE: fake }).stdout, /slim=1/);
  fs.writeFileSync(fake, '#!/bin/sh\nprintf "%s\\n" "$@"\n', { mode: 0o755 });
  const keep = cli(["lite", "--keep-mcp", "--keep-skills"], { LEAN_CLAUDE: fake }).stdout;
  assert.ok(!keep.includes("--strict-mcp-config") && !keep.includes("--disable-slash-commands"));
  fs.rmSync(tmp, { recursive: true, force: true });
});
