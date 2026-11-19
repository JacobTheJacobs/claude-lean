#!/usr/bin/env node
// claude-lean CLI. `npx claude-lean init` copies the hooks to a stable folder (~/.claude-lean; npx's own cache is
// temporary) and wires them into ~/.claude/settings.json. Everything runs locally; no network calls, no telemetry.
"use strict";
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const PKG = path.resolve(__dirname, "..");
const HOME = process.env.LEAN_HOME || path.join(os.homedir(), ".claude-lean");
const VERSION = require(path.join(PKG, "package.json")).version;
const PARTS = ["hooks", "tools", "skills", "agents", "install.sh", "LICENSE"];
// Lite mode: every request re-sends all tool definitions, MCP servers and skill descriptions. A short task needs few of
// them. Measured on 5 short tasks x 3 (Haiku 5.5): 49.5K -> ~20K tokens per request, $0.0081 -> $0.0021, 15/15 both.
const LITE_TOOLS = process.env.LEAN_LITE_TOOLS || "Read,Edit,Write,Bash,Grep,Glob,Agent,TodoWrite";

const HELP = `claude-lean ${VERSION}: cut Claude Code costs on long sessions

  claude-lean init [--dry-run] [--reader] [--no-filter]   install hooks into ~/.claude (backup first, re-runnable)
  claude-lean uninstall [--reader]                        remove everything it added
  claude-lean report [--days N] [--project NAME]          where your tokens and dollars went
  claude-lean stats                                       what the output filter saved
  claude-lean get <id>                                    full original of a trimmed output
  claude-lean memory                                      what your memory and CLAUDE.md cost per request
  claude-lean doctor                                      check python3, install folder, hooks
  claude-lean lite [--keep-mcp] [--keep-skills] [claude args]
                                                          start Claude Code with only the core tools: ~74% cheaper
                                                          short tasks (tools: LEAN_LITE_TOOLS)

Daily dollar cap: LEAN_DAY_USD=10 claude-lean init
Docs: https://github.com/JacobTheJacobs/claude-lean`;

function python() {
  for (const bin of ["python3", "python"]) {
    const r = spawnSync(bin, ["-c", "import sys; print(sys.version_info >= (3, 8))"], { encoding: "utf8" });
    if (r.status === 0 && r.stdout.trim() === "True") return bin;
  }
  return null;
}

function run(cmd, args) {
  const r = spawnSync(cmd, args, { stdio: "inherit", env: { ...process.env, LEAN_VIA_NPX: "1" } });
  process.exitCode = r.status ?? 1;
}

function sync(dry) {
  if (dry) return console.log(`[dry-run] copy   ${PKG} -> ${HOME}`);
  if (path.resolve(HOME) === PKG) return; // running from the install folder itself
  fs.mkdirSync(HOME, { recursive: true });
  for (const p of PARTS) {
    const src = path.join(PKG, p);
    if (!fs.existsSync(src)) continue;
    fs.rmSync(path.join(HOME, p), { recursive: true, force: true });
    fs.cpSync(src, path.join(HOME, p), { recursive: true });
  }
  fs.writeFileSync(path.join(HOME, "VERSION"), VERSION + "\n");
  console.log(`copied ${HOME}`);
}

function needPython() {
  const py = python();
  if (!py) {
    console.error("claude-lean needs Python 3.8+ on PATH (the hooks are small standard-library Python scripts).");
    process.exit(1);
  }
  return py;
}

function installed(file) {
  const f = path.join(HOME, file);
  if (!fs.existsSync(f)) {
    console.error(`not installed yet: run  npx claude-lean init`);
    process.exit(1);
  }
  return f;
}

function main() {
  const [cmd, ...rest] = process.argv.slice(2);
  switch (cmd) {
    case "init": {
      needPython();
      const dry = rest.includes("--dry-run");
      sync(dry);
      return run("bash", [path.join(dry ? PKG : HOME, "install.sh"), ...rest]);
    }
    case "uninstall": {
      const sh = path.join(fs.existsSync(path.join(HOME, "install.sh")) ? HOME : PKG, "install.sh");
      run("bash", [sh, "--uninstall", ...rest]);
      if (process.exitCode === 0 && !rest.includes("--dry-run") && path.resolve(HOME) !== PKG) {
        fs.rmSync(HOME, { recursive: true, force: true });
        console.log(`removed ${HOME}`);
      }
      return;
    }
    case "report":
      return run(needPython(), [installed("tools/report.py"), ...rest]);
    case "stats":
      return run(needPython(), [installed("tools/squeeze.py"), "stats"]);
    case "memory":
      return run(needPython(), [installed("tools/memcheck.py")]);
    case "get":
      return run(needPython(), [installed("tools/squeeze.py"), "get", ...rest]);
    case "doctor": {
      const py = python();
      const settings = path.join(process.env.CLAUDE_DIR || path.join(os.homedir(), ".claude"), "settings.json");
      let hooked = false;
      try { hooked = fs.readFileSync(settings, "utf8").includes(HOME); } catch {}
      const rows = [
        ["python3 3.8+", !!py],
        [`installed in ${HOME}`, fs.existsSync(path.join(HOME, "install.sh"))],
        [`hooks in ${settings}`, hooked],
      ];
      for (const [k, ok] of rows) console.log(`${ok ? "ok  " : "MISS"}  ${k}`);
      process.exitCode = rows.every((r) => r[1]) ? 0 : 1;
      return;
    }
    case "lite": {
      const keepMcp = rest.includes("--keep-mcp");
      const keepSkills = rest.includes("--keep-skills");
      const pass = rest.filter((x) => x !== "--keep-mcp" && x !== "--keep-skills");
      const args = ["--tools", LITE_TOOLS];
      if (!keepMcp) args.push("--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}');
      if (!keepSkills) args.push("--disable-slash-commands");
      const r = spawnSync(process.env.LEAN_CLAUDE || "claude", [...args, ...pass], { stdio: "inherit" });
      if (r.error) console.error(`could not start claude: ${r.error.message}`);
      process.exitCode = r.status ?? 1;
      return;
    }
    case "-v":
    case "--version":
      return console.log(VERSION);
    case undefined:
    case "-h":
    case "--help":
    case "help":
      return console.log(HELP);
    default:
      console.error(`unknown command: ${cmd}\n\n${HELP}`);
      process.exitCode = 1;
  }
}

main();
