<div align="center">

# Claude Lean

### 61% cheaper than plain Claude Code.

**61% cheaper on SWE-bench Lite and 3.6x faster, 22% cheaper on the public THOL leaderboard tasks, every THOL task passing.** One command, open source, no account, no telemetry.

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

### SWE-bench: plain Claude Code vs Claude Lean

Real GitHub issues, graded by the official SWE-bench harness. Sonnet 4.6, same prompt, one run per task.

| | Tasks | Solved, plain / Lean | Cost, plain / Lean | Time, plain / Lean |
|---|--:|--:|--:|--:|
| SWE-bench Lite | 10 | 6 / 5 | $10.17 / **$3.99 (-61%)** | 76 / **21 min** |
| SWE-bench Verified | 33 | 20 / 20 | $24.78 / $25.38 (+2%) | 135 / 137 min |
| **Total** | **43** | **26 / 25** | **$34.95 / $29.37 (-16%)** | **211 / 158 min** |

On Verified, Lean was cheaper on 19 of 33 tasks; a few hard tasks that ran long cancel it out. The same task can cost
2-5x more from one run to the next, so read the Verified cost as even. 0.2.8 added two rules after studying the tasks
Lean missed; on rerun it solved 2 of them (django-15973, sphinx-8548). Details: [docs/BENCHMARKS.md](https://github.com/JacobTheJacobs/claude-lean/blob/master/docs/BENCHMARKS.md#swe-bench).

### THOL: every token-saving tool on the board

[THOL](https://github.com/pi-infected/token-harness-optimizer-leaderboard), the public token-optimizer leaderboard: 17 real tasks on Sonnet 4.6, cost reduction vs plain Claude Code (higher is better).

| Tool | Short tasks (10) | Heavy tasks (7) | All 17 | Runs passed |
|---|--:|--:|--:|--:|
| **Claude Lean** (0.2.5) * | **+12.5%** | +34.7% | +22.4% | 51/51 |
| tokenade (0.8.13) | +9.9% | **+38.9%** | **+23.2%** | 170/170 |
| claude-token-efficient | -0.3% | +11.6% | +4.8% | 170/170 |
| ponytail | +4.7% | +3.5% | +4.2% | 170/170 |
| caveman (v1.9.0) | -7.2% | +13.6% | +1.9% | 170/170 |
| graphify | -0.8% | +3.3% | +0.9% | 170/170 |
| edgee | -13.6% | +14.7% | -0.9% | 169/170 |
| squeez | -7.0% | +6.9% | -1.0% | 170/170 |
| code-review-graph | -8.5% | +8.5% | -1.1% | 170/170 |
| codegraph | -14.7% | +7.6% | -4.9% | 170/170 |
| rtk (v0.42.3) | -3.9% | -7.1% | -5.2% | 170/170 |
| lean-ctx | -33.6% | -10.3% | -23.4% | 170/170 |
| headroom | -57.7% | -52.8% | -55.7% | 170/170 |

\* Our local run of the same harness and tasks (3 runs per task); every other row is the board as published. Lean and tokenade are within noise of each other.

Our own evals (Haiku 5.5, 238 graded tasks, all passed): `claude-lean lite` -57% short / -34% long / -60% noisy builds. **All benchmarks, including the ones that went against us: [docs/BENCHMARKS.md](https://github.com/JacobTheJacobs/claude-lean/blob/master/docs/BENCHMARKS.md).**

## What it does

| | |
|---|---|
| **Slim prompt** | Turns off 6 Claude Code features most sessions never use, in every request. `lite` starts with core tools only. |
| **Output budget** | ~300 tokens of rules: root cause first, smallest general change, short answers, no subagent fan-out, batch tool calls, narrow tests. |
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

**Does it lower quality?** Barely, in what we measured: all 51 THOL runs passed; on SWE-bench Lean solved 25 of 43 tasks to plain's 26. Every hook has an off switch.

**Does anything leave my machine?** Only web search queries, sent to public search engines and GitHub instead of Anthropic's search. `LEAN_WEB_SEARCH=0` turns that off. No telemetry. Details: [privacy](https://github.com/JacobTheJacobs/claude-lean/blob/master/docs/FEATURES.md#security--privacy).

**Why is my bill high when Claude writes so little?** Every request re-reads the whole context. Claude Lean makes that context smaller.

## License

MIT. Built by [JacobTheJacobs](https://github.com/JacobTheJacobs) with [Claude Code](https://claude.com/claude-code). [Changelog](https://github.com/JacobTheJacobs/claude-lean/blob/master/CHANGELOG.md) · [Contributing](https://github.com/JacobTheJacobs/claude-lean/blob/master/CONTRIBUTING.md) · [Issues](https://github.com/JacobTheJacobs/claude-lean/issues)
