<div align="center">

# Claude Lean

### Spend less on Claude Code. Keep the quality.

**22% cheaper than plain Claude Code on the public THOL leaderboard tasks, 35% on the heavy ones, every task passing.** One command, open source, no account, no telemetry.

[![npm](https://img.shields.io/npm/v/claude-lean?color=cb3837&logo=npm)](https://www.npmjs.com/package/claude-lean)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/JacobTheJacobs/claude-lean/blob/master/LICENSE)
[![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen)](https://github.com/JacobTheJacobs/claude-lean/blob/master/docs/FEATURES.md#security--privacy)

<img src="https://raw.githubusercontent.com/JacobTheJacobs/claude-lean/master/docs/demo.gif" alt="Terminal demo: npx claude-lean init installs the hooks; a 417-line pytest run is trimmed to 13 lines with the failure kept; claude-lean lite sends 5,442 tokens instead of 17,243 before you type." width="820">

</div>

## Install

```bash
npx claude-lean init          # your next Claude Code session uses it; --dry-run to preview, uninstall to undo
```

Or as a Claude Code plugin (no output filter, deny rules or status line; plugins can't add those):

```
/plugin marketplace add JacobTheJacobs/claude-lean
/plugin install lean@claude-lean
/lean:slim on
```

Needs Python 3.8+ (macOS, Linux, WSL) and Node 18+ for `npx`. Use one of the two, not both.

## Results

[THOL](https://github.com/pi-infected/token-harness-optimizer-leaderboard), the public token-optimizer leaderboard: 17 real tasks on Sonnet 4.6, cost reduction vs plain Claude Code, every tool on the board.



Our own evals (Haiku 5.5, 238 graded tasks, all passed): `claude-lean lite` -57% short / -34% long / -60% noisy builds. **All benchmarks, including the ones that went against us: [docs/BENCHMARKS.md](https://github.com/JacobTheJacobs/claude-lean/blob/master/docs/BENCHMARKS.md).**

## What it does

| | |
|---|---|
| **Slim prompt** | Turns off 6 Claude Code features most sessions never use, in every request. `lite` starts with core tools only. |
| **Output budget** | ~300 tokens of rules: smallest change, short answers, no subagent fan-out, batch tool calls, narrow tests. |
| **Web search** | Serves searches from public engines and GitHub instead of the paid WebSearch request; caps paid searches at 15. |
| **Reads** | Pauses huge file reads once; an unchanged re-read becomes a one-line note; skips `node_modules` and minified files. |
| **Tool output** | Trims noisy test/build logs (originals kept), compacts MCP JSON, notes repeated failures. |
| **Long sessions** | Better compaction summaries; notes when the cache expired; handoff notes across `/clear`. |
| **See the cost** | Status line, `report` (by model, project, session, tool), `audit` (unused skills/MCP, hidden context, broken hooks), daily cap. |

Every feature, setting and off switch: [docs/FEATURES.md](https://github.com/JacobTheJacobs/claude-lean/blob/master/docs/FEATURES.md). Every cost lever we know of: [docs/COST-MAP.md](https://github.com/JacobTheJacobs/claude-lean/blob/master/docs/COST-MAP.md).

## Commands

```bash
npx claude-lean report --days 7    # where your money went
npx claude-lean audit              # unused skills and MCP servers, hidden context, broken hooks
npx claude-lean lite               # Claude Code with core tools only, for quick jobs
npx claude-lean uninstall          # removes exactly what it added
```

## FAQ

**Does it lower quality?** Not in what we measured: all 51 THOL runs passed, scores equal to or above plain Claude Code. Every hook has an off switch.

**Does anything leave my machine?** Only web search queries, sent to public search engines and GitHub instead of Anthropic's search. `LEAN_WEB_SEARCH=0` turns that off. No telemetry. Details: [privacy](https://github.com/JacobTheJacobs/claude-lean/blob/master/docs/FEATURES.md#security--privacy).

**Why is my bill high when Claude writes so little?** Every request re-reads the whole context. Claude Lean makes that context smaller.

## License

MIT. Built by [JacobTheJacobs](https://github.com/JacobTheJacobs) with [Claude Code](https://claude.com/claude-code). [Changelog](https://github.com/JacobTheJacobs/claude-lean/blob/master/CHANGELOG.md) · [Contributing](https://github.com/JacobTheJacobs/claude-lean/blob/master/CONTRIBUTING.md) · [Issues](https://github.com/JacobTheJacobs/claude-lean/issues)
