#!/usr/bin/env node
// claude-lean CLI. `npx claude-lean init` copies Claude Lean to a stable folder (~/.claude-lean; npx's own cache is
// temporary) and runs its installer, which edits ~/.claude/settings.json. Everything runs locally; no network calls.
"use strict";
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const PKG = path.resolve(__dirname, "..");
const HOME = process.env.LEAN_HOME || path.join(os.homedir(), ".claude-lean");
const VERSION = require(path.join(PKG, "package.json")).version;
const PARTS = ["hooks", "install.sh", "LICENSE"];

const HELP = `claude-lean ${VERSION}: cut Claude Code costs without changing how Claude works

  claude-lean init [--pin] [--cache-1h]   install into ~/.claude/settings.json (backup first, re-runnable)
  claude-lean uninstall                   remove everything it added
  claude-lean doctor                      check python3, install folder, settings

Docs: https://github.com/JacobTheJacobs/claude-lean`;

function python() {
  for (const bin of ["python3", "python"]) {
    const r = spawnSync(bin, ["-c", "import sys; print(sys.version_info >= (3, 8))"], { encoding: "utf8" });
    if (r.status === 0 && r.stdout.trim() === "True") return bin;
  }
  return null;
}

function run(cmd, args) {
  const r = spawnSync(cmd, args, { stdio: "inherit" });
  return (process.exitCode = r.status ?? 1);
}

function installedVersion() {
  try { return fs.readFileSync(path.join(HOME, "VERSION"), "utf8").trim(); } catch { return null; }
}

// Claude Lean before 0.3 installed many hooks that point into ~/.claude-lean. Replacing that folder without removing
// them first would leave settings.json calling scripts that no longer exist, so its own uninstaller runs first.
function removeOldLean() {
  const v = installedVersion();
  const sh = path.join(HOME, "install.sh");
  if (!v || !/^0\.[0-2]\./.test(v) || !fs.existsSync(sh)) return true;
  console.log(`removing Claude Lean ${v} first`);
  if (run("bash", [sh, "--uninstall"]) !== 0) return false;
  fs.rmSync(HOME, { recursive: true, force: true });
  fs.rmSync(path.join(os.homedir(), ".cache", "claude-lean"), { recursive: true, force: true });
  return true;
}

function sync() {
  if (path.resolve(HOME) === PKG) return; // running from the install folder itself
  fs.mkdirSync(HOME, { recursive: true });
  for (const p of PARTS) {
    fs.rmSync(path.join(HOME, p), { recursive: true, force: true });
    fs.cpSync(path.join(PKG, p), path.join(HOME, p), { recursive: true });
  }
  fs.writeFileSync(path.join(HOME, "VERSION"), VERSION + "\n");
  console.log(`copied ${HOME}`);
}

function main() {
  const [cmd, ...rest] = process.argv.slice(2);
  switch (cmd) {
    case "init": {
      if (!python()) {
        console.error("claude-lean needs Python 3.8+ on PATH (the installer and hook are standard-library Python).");
        return (process.exitCode = 1);
      }
      if (!removeOldLean()) return;
      sync();
      return run("bash", [path.join(HOME, "install.sh"), ...rest]);
    }
    case "uninstall": {
      const sh = path.join(fs.existsSync(path.join(HOME, "install.sh")) ? HOME : PKG, "install.sh");
      if (run("bash", [sh, "--uninstall"]) === 0 && path.resolve(HOME) !== PKG) {
        fs.rmSync(HOME, { recursive: true, force: true });
        console.log(`removed ${HOME}`);
      }
      return;
    }
    case "doctor": {
      const settings = path.join(process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude"), "settings.json");
      let hooked = false;
      try { hooked = fs.readFileSync(settings, "utf8").includes("CLAUDE_LEAN_V2_ADDED"); } catch {}
      const rows = [
        ["python3 3.8+", !!python()],
        [`installed in ${HOME}`, fs.existsSync(path.join(HOME, "install.sh"))],
        [`settings in ${settings}`, hooked],
      ];
      for (const [k, ok] of rows) console.log(`${ok ? "ok  " : "MISS"}  ${k}`);
      process.exitCode = rows.every((r) => r[1]) ? 0 : 1;
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
