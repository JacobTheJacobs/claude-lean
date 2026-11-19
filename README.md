# Claude Lean: Claude Code cost optimizer

**Long Claude Code sessions cost 65% less, with the same quality. Free, local, and it adds zero tokens to your requests.**

Open source down to the last line. No binary, no account, no telemetry, no network calls.

```bash
npx claude-lean init
```

[![npm](https://img.shields.io/npm/v/claude-lean?color=cb3837&logo=npm)](https://www.npmjs.com/package/claude-lean) [![CI](https://github.com/JacobTheJacobs/claude-lean/actions/workflows/ci.yml/badge.svg)](https://github.com/JacobTheJacobs/claude-lean/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) [![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-3776ab?logo=python&logoColor=white)](tools/report.py) [![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen)](#install) [![Runs locally](https://img.shields.io/badge/runs-100%25%20local-success)](#privacy) [![Claude Code](https://img.shields.io/badge/Claude%20Code-hooks%20%7C%20skills-d97757)](#whats-in-it) [![GitHub stars](https://img.shields.io/github/stars/JacobTheJacobs/claude-lean?style=flat&color=yellow)](https://github.com/JacobTheJacobs/claude-lean)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/hero-dark.svg">
  <img src="docs/hero-light.svg" alt="Claude Lean: cost of one 10-task Claude Code session on Opus 5.5. Plain $4.97, with Claude Lean $1.74, 65% less, 20/20 tasks passed in both.">
</picture>

## Result

| 10 tasks in one session, Opus 5.5 | Tasks passed | Cost per session |
|---|:-:|--:|
| Plain Claude Code | 20/20 | $4.97 |
| **With Claude Lean** | **20/20** | **$1.74 (-65%)** |

40 graded tasks, 2026-11-12. Details in [Eval](#eval).

## Every request: slim (on by default)

Claude Code sends the definitions of features you may never use with every request. `init` turns off the six heaviest through Claude Code's own switches (in the `env` block of settings.json):

| Switch | Tokens per request |
|---|--:|
| `CLAUDE_CODE_DISABLE_ARTIFACT` | 13,500 |
| `CLAUDE_CODE_DISABLE_WORKFLOWS` | 8,100 |
| `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS` | 2,400 |
| `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS` | 1,100 |
| `CLAUDE_CODE_DISABLE_CRON`, `_ADVISOR_TOOL` | 500 |

Per request: 49.5K -> 24.9K tokens. 5 short tasks x 3 on Haiku 5.5: $0.0078 -> $0.0053 per task (**-32%**), 15/15 passed in both. The gain is in cache writes, so it shows on short or fresh sessions; on the 10-task Haiku session it made no measurable difference. MCP servers, skills, web tools and subagents stay. `init --no-slim` skips it; uninstall removes only the switches it added.

## Short tasks: `claude-lean lite`

On a short task the bill is the fixed overhead each request re-sends: every tool definition, MCP server and skill description. In a typical setup that is ~50K tokens before you type a word; a short task needs a handful of tools.

```bash
npx claude-lean lite              # Claude Code with only Read, Edit, Write, Bash, Grep, Glob, Agent, TodoWrite
npx claude-lean lite --keep-mcp   # keep your MCP servers (--keep-skills keeps skills)
```

| 5 short tasks x 3, Haiku 5.5 | Passed | Cost per task | Tokens per request |
|---|:-:|--:|--:|
| Full setup | 15/15 | $0.0081 | ~49.5K |
| **`claude-lean lite`** | **15/15** | **$0.0021 (-74%)** | ~20K |

On a clean install (no MCP servers or skills), the first request drops from 17.2K to 5.4K tokens (o200k tokenizer, Claude Code 2.1.239, measured the way [hibench](https://hibench.dev/rankings/) does). Since 0.2.1 `lite` also applies the slim switches.

Bug fix, new function, code lookup, log count, find a definition; 2026-11-19. Use it for quick jobs; start normally when you need web, MCP or skills.

## Why it works

Every request re-sends the whole session. By task 10 of a long session, each request re-reads ~175K tokens of old history, and that re-reading is most of the bill, not the code written. Starting fresh per task keeps each request near the starting size: about 17K tokens on a clean install, more with MCP servers and skills.

So Claude Lean watches the session size and tells you when a fresh start pays off. On short sessions it stays silent and costs nothing.

## Eval

Same 10 tasks, in order, on a test repo (a Python package, 12 modules, a 20,000-line log): a bug fix, a new function, then 8 lookups and counts over the code and the log. Each answer is checked by a script (`evals/check.py`). Claude Code 2.1.322, Opus 5.5, 2 sessions per setup.

- **Plain:** one continuous session, every task resumes the last.
- **Lean:** a fresh session per task (what `/clear` does) + the Haiku `reader` agent.

Average cost of each task:

| # | Task | Plain | Lean | Passed (plain / Lean) |
|--:|---|--:|--:|:-:|
| 1 | bug fix | $0.18 | $0.18 | 2/2 · 2/2 |
| 2 | add a function | $0.23 | $0.16 | 2/2 · 2/2 |
| 3 | find a code location | $0.31 | $0.17 | 2/2 · 2/2 |
| 4 | count log errors | $0.40 | $0.17 | 2/2 · 2/2 |
| 5 | count functions in 12 files | $0.52 | $0.22 | 2/2 · 2/2 |
| 6 | error breakdown as JSON | $0.56 | $0.15 | 2/2 · 2/2 |
| 7 | count warnings | $0.61 | $0.17 | 2/2 · 2/2 |
| 8 | count functions in a file | $0.67 | $0.16 | 2/2 · 2/2 |
| 9 | find a definition | $0.72 | $0.16 | 2/2 · 2/2 |
| 10 | count one error type | $0.77 | $0.19 | 2/2 · 2/2 |
| | **Total** | **$4.97** | **$1.74** | **20/20 · 20/20** |

Plain gets more expensive with every task because it re-reads everything before it; Lean stays flat. The same small task costs 4x more at step 10 of a long session than in a fresh one.

Same eval on **Haiku 5.5** (2026-11-19, 2 sessions per setup): plain $0.169 per session, Lean $0.058 (**-66%**), 20/20 tasks passed in both.

Reproduce (spends real tokens; every session is capped at `--budget`, default $2):

```bash
python3 evals/long.py --reps 2 --model claude-opus-5-5 --arms plain,lean    # about $13
python3 evals/long.py --reps 2                                               # Haiku, about $0.50
python3 evals/filter.py --reps 3                                             # output filter on a 400-test suite
```

Output filter, honestly: it cuts a 400-test pytest run or a 350-line `make` log by 90%+, but on a single task that is ~1% of the bill, because each request re-sends ~45K tokens of fixed overhead. The filter matters when big outputs pile up in a long session.

## vs JFrog Boost

Same graded tasks, same machine, Haiku 5.5, JFrog Boost v0.17.5 installed with `boost init --claude` in a throwaway HOME (2026-11-19, `evals/vs.py`):

| 10-task session | Passed | $ per session |
|---|:-:|--:|
| Plain Claude Code | 18/20 | $0.193 |
| JFrog Boost | 18/20 | $0.208 (+8%) |
| **Claude Lean** | 15/20 | **$0.053 (-72%)** |
| Claude Lean + JFrog Boost | 19/20 | $0.056 (-71%) |

| Noisy output (400-test pytest, 350-line make) | Passed | $ per task |
|---|:-:|--:|
| Plain | 4/4 | $0.006 |
| JFrog Boost | 4/4 | $0.008 (+49%) |
| **Claude Lean** | 4/4 | $0.005 (-4%) |

Lean's 15/20 was wrong counts in single runs; a rerun of the same suite scored plain 20/20 ($0.143), Lean 20/20 ($0.054, -63%). JFrog's own local log (`history.db`) recorded **0 filtered commands** across 95 sessions: its terminal filter (`boost-cli-filtering`) was switched off by its remote feature flags on a fresh install. Its trace spans held only a span type and a process id.

## Tested and rejected

Measured on the 10-task session (2 sessions each, 2026-11-19), so you don't have to:

| Lever | Result | Passed |
|---|--:|:-:|
| Compact early (`CLAUDE_CODE_AUTO_COMPACT_WINDOW=100000`, `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50`) | +35% ($0.171 -> $0.230) | 20/20 |
| Opus 5.5 advisor on Sonnet 5.5 (`--advisor claude-opus-5-5`) | +24% ($0.84 -> $1.04) | 20/20 both |
| Sonnet 5.5 instead of Haiku 5.5, fresh sessions | 14x ($0.058 -> $0.84) | 19/20 vs 20/20 |
| Opus 5.5: subagents on Haiku (`CLAUDE_CODE_SUBAGENT_MODEL`) | -2% ($1.81 -> $1.78), noise: routine tasks spawn no subagents | 20/20 both |
| Opus 5.5: `--effort low` instead of medium | -6.5% ($1.81 -> $1.69) | 20/20 both |

Compaction calls cost more than they save at these sizes, and the advisor adds Opus calls without a quality gain on routine tasks. Low effort saves a little on routine work but risks quality on hard tasks, so it stays your call. All of these may behave differently on long, hard work; measure yours with `python3 evals/levers.py`.

## Install

Needs Node 18+ and Python 3.8+ (macOS, Linux, WSL).

```bash
npx claude-lean init              # --dry-run to preview, --reader for the Haiku agent, --no-filter to skip the output filter
```

It copies the hooks to `~/.claude-lean` and merges them into `~/.claude/settings.json`, with a backup first. Your own hooks and settings stay. Safe to re-run. New Claude Code sessions pick it up.

| Command | |
|---|---|
| `npx claude-lean report --days 7` | where your tokens and dollars went |
| `npx claude-lean stats` | what the output filter saved |
| `npx claude-lean get <id>` | full original of a trimmed output |
| `npx claude-lean doctor` | check the install |
| `npx claude-lean uninstall` | remove everything it added |
| `LEAN_DAY_USD=10 npx claude-lean init` | add a daily dollar cap |

Without npm: `git clone https://github.com/JacobTheJacobs/claude-lean.git && claude-lean/install.sh`.

## What's in it

| Part | What it does | Tokens added per request |
|---|---|---|
| `hooks/session_guard.py` | Past 100K tokens of context (`LEAN_CLEAR_AT`), shows you: "new task? `/clear` first". Silent below that. | 0 |
| `tools/report.py` | Shows where your money went: cache reads vs writes vs output, per model, project, session. | 0 |
| `skills/lean/` | Smallest-change checklist and short answers, loaded only when called. | 0 until called |
| `agents/reader.md` (`init --reader`) | Haiku 5.5 helper for bulky reads (many files, big logs). | ~550 |
| `hooks/squeeze_hook.py` + `tools/squeeze.py` | Trims noisy build/install output (npm, pip, cargo, go, docker, make, ...): drops progress bars, download chatter, repeats; keeps every error and summary. The original is saved; `claude-lean get <id>` returns it. If the agent fetches originals of one tool 3 times, that tool's filter turns off. `claude-lean stats` shows the savings. | 0 |
| `skills/handoff/` + `hooks/handoff_hook.py` | Say "handoff" before `/clear`: Claude saves a ~15-line note (goal, done, state, next steps), and the next session in that folder starts with it. Keeps the /clear savings without the forgetting. Used once, expires in 12h. | 0; the note (~300) only after a handoff |
| `tools/audit.py` (`claude-lean audit`) | Lists the skills and MCP servers you load on every request but never used (from your own session logs). Claude Code caps the skill listing, so parking saves little (23 skills: ~200 tokens per request); it mainly keeps the list relevant. `--disable-unused` parks unused skills in `~/.claude/skills-disabled`; `--restore` brings them back. | 0 |
| `tools/memcheck.py` (`claude-lean memory`) | Shows what your memory index and CLAUDE.md add to every request, per project, and flags indexes over 1K tokens. Read-only. | 0 |
| `hooks/cache_guard.py` | Warns before a mid-session CLAUDE.md or settings edit, which re-writes the whole cache. | 0 |
| `hooks/budget.py` (optional) | Daily dollar cap: `LEAN_DAY_USD=5 npx claude-lean init`. | 0 |

## Habits that save the most

1. **`/clear` between unrelated tasks.** The measured 65%. Mid-task, say "handoff" first so the next session picks up where you left off.
2. **`/compact` by hand** when one task has to stay in one long session. Forcing automatic compaction earlier did not pay in our test (+35%, see above).
3. **Don't edit CLAUDE.md, settings, model or effort mid-session.** Each change re-writes the whole cached prompt; Anthropic measured 20-50x the cost of the same text sent as a message.
4. **Ask for short answers.** Output costs 5x input.
5. **Run `npx claude-lean report --days 7` weekly.** If cache reads dominate, your sessions are too long.

Sources: Anthropic's [cost guide](https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence) and [cookbook](https://platform.claude.com/cookbook/cost-optimization-cost-optimization).

## FAQ

**Why is my Claude Code bill high when I write little code?** Each request re-reads the whole context. A 300K-token session re-read 50 times is 15M tokens.

**Does it help short tasks?** The long-session guard does nothing there. Slim (-32%) and `claude-lean lite` (-74%) do: they cut the fixed overhead every request carries.

**Does the output filter change exit codes?** Yes. A filtered command runs through a pipe, so Claude sees the filter's exit code (0) even when tests fail. Every error and summary line is kept, so the failure still shows in the output. `--no-filter` skips the filter; dev servers and watchers are never filtered.

**Can I use Haiku for subagents?** Yes, with a named agent file (`model: haiku`) like `agents/reader.md`. `fork` subagents always use your main model.

## Privacy

Everything runs on your machine. No network calls, no telemetry. `report.py` and `audit.py` read `~/.claude/projects`. The output filter keeps the last 200 trimmed command outputs in `~/.cache/claude-lean/out` (owner-only), and a handoff note stays in `~/.cache/claude-lean/handoff` until it is used or 12 hours pass. `uninstall` deletes that folder.

## Contributing

Filters for more commands are the most useful addition. See [CONTRIBUTING.md](CONTRIBUTING.md); `npm test` runs everything.

## License

MIT. See [CHANGELOG.md](CHANGELOG.md) for releases.
