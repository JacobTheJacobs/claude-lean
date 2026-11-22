<div align="center">

# Claude Lean

### Spend less on Claude Code. Keep the quality.

Every Claude Code request carries a fixed load before your prompt: the system prompt and every tool definition, ~17-50K tokens. Claude Lean cuts it. On THOL's 17 real tasks (Sonnet 4.6) the default install costs **22% less** than plain Claude Code, and **35% less on the heavy tasks**, with every task passing. On our own evals **`claude-lean lite` costs 34-60% less**, and the default install costs 37% less on short tasks and 30% less on noisy builds, and writes a quarter fewer output tokens in long sessions. On a real setup, the first request of a fresh session drops by about a third.

One command. Runs locally. Open source, no account, no telemetry.

[![npm](https://img.shields.io/npm/v/claude-lean?color=cb3837&logo=npm)](https://www.npmjs.com/package/claude-lean)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/JacobTheJacobs/claude-lean/blob/master/LICENSE)
[![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen)](#security--privacy)
[![No telemetry](https://img.shields.io/badge/telemetry-none-success)](#security--privacy)

**[Get started](#get-started)** · **[How it works](#how-it-works)** · **[Capabilities](#capabilities)** · **[Benchmark](#benchmark)** · **[CI](#agents-in-ci)** · **[vs JFrog Boost](#vs-jfrog-boost)** · **[Changelog](https://github.com/JacobTheJacobs/claude-lean/blob/master/CHANGELOG.md)**

<img src="https://raw.githubusercontent.com/JacobTheJacobs/claude-lean/master/docs/demo.gif" alt="Terminal demo: npx claude-lean init installs the hooks; a 417-line pytest run is trimmed to 13 lines with the failure kept; claude-lean lite sends 5,442 tokens instead of 17,243 before you type; a short task costs $0.0021 instead of $0.0081." width="820">

<sub>Every frame is real output from claude-lean.</sub>

</div>

## Results

**[THOL](https://github.com/pi-infected/token-harness-optimizer-leaderboard)** (Token Harness Optimizer Leaderboard: 17 real tasks, Sonnet 4.6, 3 runs each, isolated sessions; our local runs on Claude Code 2.1.239, 2026-11-22). Cost reduction vs plain Claude Code, geometric mean over tasks, every run passed:

| | Short tasks (10) | Heavy tasks (7, the board's headline) | All 17 |
|---|--:|--:|--:|
| **Claude Lean `init`** (0.2.4) | **+12.5%** | **+34.7%** | **+22.4%** |
| tokenade 0.8.13 (THOL board, its own run on Claude Code 2.1.206) | +9.9% | +38.9% | +23.2% |

Per run vs plain: output tokens -18%, cache reads -32%. Biggest wins: Django settings inventory -59%, ledger debugging -49%, PDF report -49%, web research -46% ($3.13 → $1.70, same score). Tasks that cost more: Django code questions +10% and seo audit +5%, both inside run-to-run noise (one expensive run each). An earlier build without the web search hook scored +16.9% / +26.9% / +21.2%. These are our local runs, not an official board entry yet.

Same graded tasks, Haiku 5.5, clean Claude Code setup, two runs per cell (2026-11-20, `evals/compare.py`, 238 tasks):

| Cost vs plain Claude Code | Short task | Long session (10 tasks) | Noisy build/test output | Passed |
|---|--:|--:|--:|--:|
| **`claude-lean lite`** | **-57%** | **-34%** | **-60%** | 34/34 |
| **Claude Lean `init`** (slim + output filter + output budget) | **-37%** | -2% | **-30%** | 34/34 |
| [ponytail](https://github.com/DietrichGebert/ponytail) 5.3.3 | +7% | +5% | +29% | 33/34 |
| [caveman](https://github.com/JuliusBrussee/caveman) v4.1.0 | +11% | +6% | +15% | 34/34 |

Where the saving comes from, tokens vs plain Claude Code:

| | Input, short | Output, short | Input, long | Output, long |
|---|--:|--:|--:|--:|
| `lite` | -71% | -15% | -50% | +2% |
| `init` | -49% | -11% | -19% | **-25%** |
| ponytail | 0% | +13% | +4% | +6% |
| caveman | +4% | -33% | +10% | -27% |

caveman cuts output as much as we do, but its own prompt costs more than that saves on these tasks. Differences under ~10% are run-to-run noise, so read the long-session `init` result as "no saving in cost". Each tool was installed the way its README says (both as Claude Code plugins). The output budget was then a ~120-token rule set added at session start (`hooks/terse_hook.py`, now ~280 tokens); without it, `init` measured -21% / +7% / -19% in the same run.

**On a real setup** (the author's machine: many skills and plugins, a project with memory), the first request of a fresh session went from 46,018 to 29,179 tokens (-37%), and its cost on a warm cache from $0.0031 to $0.0004: without slim, part of the prompt start changes on every run and misses the cache. Check yours with `claude-lean report --compare`.

> **Correction (0.2.3):** earlier versions said long sessions cost 65% less with a fresh session per task. That number came from a bug in our eval: a resumed Claude Code session reports its cost as a running total, and we added those totals up. Measured per step, one continuous session is *cheaper* when tasks run back to back (cached history is billed at a tenth of the input price). Details in [What we got wrong](#what-we-got-wrong).

> **Note:** every number here comes from an eval in [`evals/`](https://github.com/JacobTheJacobs/claude-lean/tree/master/evals) that you can re-run yourself. When a result went against us, it's on this page too.

## Get started

### 🧩 Claude Code plugin

Inside Claude Code:

```
/plugin marketplace add JacobTheJacobs/claude-lean
/plugin install lean@claude-lean
/lean:slim on
```

The plugin brings the output budget, the web search, read, MCP, retry-loop and compaction hooks, the long-session guard, handoff notes, the cache guard, both skills and the `/lean:report`, `/lean:audit` and `/lean:memory` commands. Plugins can't set environment switches, so `/lean:slim on` writes the 6 slim settings to `~/.claude/settings.json` (backed up first; `/lean:slim off` undoes it). Plugins can't add permission rules or a status line either, so the output filter, the generated-file deny rules, the cost status line and `lite` need the npm install below. Use the plugin or `npx claude-lean init`, not both: the hooks would run twice.

### ⌨️ npm

```bash
npx claude-lean init
```

That's it. Your next Claude Code session uses it. Preview the changes with `--dry-run`, undo them with `npx claude-lean uninstall`.

### 📦 Without npm

```bash
git clone https://github.com/JacobTheJacobs/claude-lean.git && claude-lean/install.sh
```

Needs Python 3.8+ on macOS, Linux or WSL, plus Node 18+ for `npx`.

## Works with

| Agent | Command | What gets installed |
|---|---|---|
| Claude Code, plugin | `/plugin install lean@claude-lean` | 3 hooks, 2 skills, 4 `/lean:` commands. `/lean:slim on` adds the 6 settings. |
| Claude Code | `npx claude-lean init` | 4 hooks, 2 skills and 6 settings in `~/.claude/settings.json` (backed up first) |
| Claude Code, quick jobs | `npx claude-lean lite` | Nothing. Starts Claude Code with only the core tools. |

Your own hooks, settings, MCP servers and skills are left alone. Run `init` again any time to update.

## How it works

Claude Code has no memory between requests, so each one re-sends everything: the system prompt, every tool definition, and the conversation so far. Prompt caching bills the repeated part at a tenth of the input price, but every new session pays full price to write its starting load into the cache first.

```
                 ┌──────────────── every request ────────────────┐
  plain          │ tool definitions 17-50K │ conversation so far │
                 └───────────────────────────────────────────────┘
                 ┌─────────────┬─────────────────────┐
  Claude Lean    │ slim / lite │ conversation so far │   noisy output trimmed before it lands
                 └─────────────┴─────────────────────┘
```

Claude Lean shrinks the parts that don't need to be there:

1. **Fixed overhead.** Six built-in Claude Code switches drop features most sessions never use. `lite` goes further for quick jobs.
2. **Noise.** A 400-test pytest run arrives as 13 lines. Every failure and summary stays; the full original is one command away.
3. **Focus.** Past 100K tokens a hook reminds you that `/clear` keeps an unrelated task focused, and "handoff" carries a short note across.

## Capabilities

### Save tokens

- **Long-session guard.** Once a session passes 100K tokens (`LEAN_CLEAR_AT`), you get one line suggesting `/clear` before unrelated work. It's shown to you, never sent to the model, and stays silent on short sessions. It's about focus, not cost: back-to-back work is cheaper in one session.
- **Handoff.** Say "handoff" before `/clear`. Claude saves a short note (goal, progress, next steps), and the next session in that folder starts with it. Used once; expires after 12 hours. It's for continuity, not cost: writing the note is an extra request.
- **Slim.** On by default. Turns off Artifacts, Workflows, git instructions, background tasks, cron and the advisor tool, which cuts a typical setup from 49.5K to 24.9K tokens per request. Skip it with `--no-slim`.
- **Lite.** `npx claude-lean lite` starts Claude Code with just Read, Edit, Write, Bash, Grep, Glob, Agent and TodoWrite: no MCP servers, no skills. On a clean install that's 5.4K tokens before you type instead of 17.2K. `--keep-mcp` and `--keep-skills` bring those back.
- **Output filter.** For pytest, jest, npm, pip, cargo, go, docker, make and more. Drops progress bars, download chatter, passing tests and repeated lines; keeps errors, tracebacks and summaries. Dev servers and watchers are never touched.
- **Output budget.** About 280 tokens of standing rules at session start: smallest change, 1-3 line answers, edit instead of rewriting, do the reading yourself instead of fanning out to subagents, batch independent tool calls, text before screenshots. `--no-terse` keeps only the subagent, web and batching rules.
- **Web search budget.** Claude Code's WebSearch is a separate model request that re-sends the conversation as uncached input (~$0.07 a search on Sonnet). The hook serves searches itself from public search engines plus GitHub's repository search, skips pages an earlier search already showed, blocks repeated queries, and caps the paid searches at 15 per session (`LEAN_WEB_SEARCHES`; `LEAN_WEB_SEARCH=0` turns its own search off). On THOL's web research task the cap alone cut cost 36% with a higher score.
- **Read guard.** A full read of a file over 1,000 lines (`LEAN_READ_LINES`) is paused once and Claude is pointed at Grep or a line range; repeating the read goes through. A re-read of an unchanged file returns a one-line note instead of the whole file again (`LEAN_READ_DEDUPE=0` to turn off). Reads were 36% of the author's own spend.
- **Generated files.** `node_modules`, minified JS/CSS and source maps are denied to Read (`--no-deny` to keep them readable).
- **MCP results.** JSON from MCP tools loses its nulls, empty fields and indentation before Claude sees it; every other value stays exactly as it was (`LEAN_MCP_COMPACT=0`).
- **Retry loops.** When the same command fails a third time with the same error, Claude gets one note to change approach (`LEAN_LOOP_AT`).
- **Compaction.** When Claude Code compacts a long session, the summary is told to keep paths, commands, errors, decisions and the next step, and to drop file contents and logs.
- **Audit.** `npx claude-lean audit` finds skills and MCP servers you load on every request but never use, and shows how much each skill adds to the context once it runs. `audit --profile` turns off, for one project only, the personal skills and user MCP servers that project never used (`--unprofile` undoes it).
- **Status line.** Session cost, context fill, cache hit rate and your 5-hour limit, as you work. Added only when you have no status line of your own (`--no-statusline` to skip).
- **Pasted prompts.** A prompt over ~10K tokens gets a one-line note to you: save big logs to a file and let Claude search them.
- **Expired cache.** Coming back after the prompt cache expired (1 hour on a subscription, 5 minutes with an API key) to a long session, you get a one-line note: this message rewrites the whole cache, so a handoff and `/clear` may be cheaper.
- **Repeated fetches.** Fetching the same page with the same question twice in a session points Claude at the earlier answer. Failing edits get the retry-loop note too.
- **Hidden context and broken hooks.** `audit` shows what gets added to your context without you asking (skill listings, invoked skills, hook output), hooks that fail on every call, and a verbose output style. `memory` counts files your CLAUDE.md pulls in with `@imports`.
- **Memory check.** `npx claude-lean memory` shows what your memory files and CLAUDE.md add to every request.
- **Where the money went.** `npx claude-lean report` now also estimates what each tool's results cost while they sat in the context, and shows fast-mode spend.

Every lever we know of, what Claude Lean covers and what it doesn't yet: [docs/COST-MAP.md](docs/COST-MAP.md).

### Stay safe

- **Nothing is lost.** Every trimmed output is saved, and `npx claude-lean get <id>` brings back the original. If Claude needs the originals from one tool three times, that tool's filter switches itself off.
- **Never in the way.** A failing hook exits quietly instead of breaking your session. The filter never approves a command, so your permission rules still apply.
- **Cache guard.** Warns you before a mid-session edit to CLAUDE.md or settings, which forces the whole prompt cache to be rebuilt.
- **Clean uninstall.** `npx claude-lean uninstall` removes exactly what it added, cache included.

**Does it work on your machine?** `report --compare` reads your own logs and compares fresh sessions before and after the install. The first request of a fresh session is pure fixed overhead (system prompt, tools, skills), so its change is exactly what Claude Lean removed; cost per request and per session also move with what you worked on. Resumed sessions and scratch runs are left out. Give it a few days of normal use.

### Agents in CI

Running Claude Code in GitHub Actions? Add Claude Lean before the step that starts it:

```yaml
- uses: JacobTheJacobs/claude-lean@v0.2.2
  # with:
  #   filter: "false"   # keep raw command output
  #   slim: "false"     # keep every Claude Code feature
- uses: anthropics/claude-code-action@v1
  # ...
```

It writes the same settings as `npx claude-lean init` into the runner's `~/.claude`, so slim and the output filter apply to every Claude Code run in that job.

CI pays the cold start on every run: a fresh runner writes the whole prompt start to cache again each time. Three settings matter more there than on your laptop:

- `--max-turns N` stops a stuck job before it loops for an hour.
- A narrow `--allowedTools` (for example `Read,Edit,Grep,Glob,Bash(npm test:*)`) keeps unused tool definitions out of every request.
- `npx claude-lean lite -p "..."` starts with core tools only: 5.4K tokens before the prompt instead of 17.2K.

### See the impact

```bash
npx claude-lean report --days 7       # where your money went: by model, project and session, with fixes
npx claude-lean report --compare      # your own fresh sessions, before vs after you installed Claude Lean
npx claude-lean stats                 # what the output filter saved, per tool
LEAN_DAY_USD=10 npx claude-lean init  # daily spending cap: warns at 80%, stops at 100%
```

## Benchmark

The clean comparison above, in dollars:

| | Short task | Long session | Noisy task | Passed |
|---|--:|--:|--:|:-:|
| Plain Claude Code | $0.0038 | $0.0248 | $0.0042 | 34/34 |
| Claude Lean `init` | $0.0024 | $0.0277 | $0.0024 | 34/34 |
| `claude-lean lite` | $0.0011 | $0.0169 | $0.0015 | 34/34 |

On a heavier setup (the author's: many skills and plugins, 49.5K tokens per request), 5 short tasks x 3 runs each:

| Short task, heavy setup | Passed | Plain | With Claude Lean |
|---|:-:|--:|--:|
| Slim (on by default) | 15/15 both | $0.0078 | **$0.0053 (-32%)** |
| `claude-lean lite` | 15/15 both | $0.0081 | **$0.0021 (-74%)** |

The output filter, honestly: it cuts a 400-test pytest run or a 350-line `make` log by over 90%, but on a single task that's only 1-4% of the bill, and in our long-session test it never fired, because Claude already pipes test output through `grep` or `tail` on its own.

Raw results: [`evals/short-results.jsonl`](https://github.com/JacobTheJacobs/claude-lean/blob/master/evals/short-results.jsonl). To measure long sessions yourself:

```bash
python3 evals/long.py --reps 2         # 10 tasks in a row, Haiku, about $0.20
```

Each session stops at `--budget` dollars (default $2), so a re-run can't surprise you.

### vs JFrog Boost

Same graded tasks, same machine, Haiku 5.5. JFrog Boost v0.17.5 was installed with `boost init --claude` in a separate HOME (2026-11-19, `evals/vs.py`). Every run is counted:

| 10 tasks in a row | Passed | Cost per session |
|---|:-:|--:|
| Plain Claude Code, one session | 88/90 | $0.029 |
| JFrog Boost, one session | 35/40 | $0.028 (-3%) |
| Claude Lean as tested: a fresh session per task | 80/90 | $0.052 (+80%) |
| Same + JFrog Boost | 38/40 | $0.051 (+79%) |

| Noisy output (400-test pytest, 350-line make) | Passed | Cost per task |
|---|:-:|--:|
| Plain Claude Code | 14/14 | $0.0057 |
| JFrog Boost | 8/8 | $0.0065 (+14%) |
| Claude Lean | 14/14 | $0.0055 (-4%) |
| Claude Lean + JFrog Boost | 8/8 | $0.0047 (-17%) |

- **Long sessions.** Neither tool saved money. JFrog Boost was within noise of plain (-3%). Our fresh-session-per-task approach cost 80% more: that's the measurement error described below, and the reason it's gone.
- **Noisy single tasks.** Claude Lean's filter came out 4% cheaper, JFrog Boost 14% more expensive.
- **Quality.** All 10 of the fresh-session misses came in the first two batches, 8 of them counts over the 20,000-line log. The two later batches passed 50 of 50.
- **Why JFrog Boost didn't save here.** Its own local log (`history.db`) recorded 0 filtered commands across 95 sessions: on a fresh install, its remote feature flags had its terminal filter (`boost-cli-filtering`) switched off.

### Tested and rejected

We measured these on a 10-task session (2 sessions each) so you don't have to:

| Lever | Result | Passed |
|---|--:|:-:|
| A fresh session per task (`/clear` between tasks), Haiku 5.5 | +109% ($0.028 → $0.058) | 20/20 both |
| A fresh session per task, Opus 5.5 | +126% ($0.77 → $1.74) | 20/20 both |
| Fresh session per step on 6 follow-up tasks that build on each other (`evals/chain.py`) | +60% ($0.017 → $0.028) | 18/18 all |
| Same, plus a handoff note before each fresh session | +129% ($0.017 → $0.039) | 18/18 all |
| Output filter over 10 fix-and-rerun steps in one session (`evals/pileup.py`) | no effect: never fired | 20/20 both |
| Compact early (`CLAUDE_CODE_AUTO_COMPACT_WINDOW=100000`, `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50`) | +32% | 20/20 |
| Opus 5.5 advisor on Sonnet 5.5 (`--advisor claude-opus-5-5`) | +24% | 20/20 both |
| Sonnet 5.5 instead of Haiku 5.5 | 14x the cost | 19/20 vs 20/20 |
| Opus 5.5 with subagents on Haiku (`CLAUDE_CODE_SUBAGENT_MODEL`) | -2%, noise | 20/20 both |
| Opus 5.5 at `--effort low` instead of medium | -6.5% | 20/20 both |

Why the filter never fired: left to itself, Claude already trims test output (`pytest -v 2>&1 | grep FAILED`, `| tail -n 80`), and the filter leaves piped commands alone. Both sessions were effectively the same setup, so their 9% cost gap shows the run-to-run noise in these evals: treat differences under ~10% as noise. Long, hard work may behave differently. Measure your own with `python3 evals/levers.py`.

## Habits that save the most

1. **Use `claude-lean lite` for quick jobs.** The measured 74%.
2. **Keep back-to-back work in one session.** Cached history is cheap; a new session pays to rebuild its cache. `/clear` when you switch to something unrelated.
3. **Leave CLAUDE.md, settings, model and effort alone mid-session.** Each change forces the whole cached prompt to be rebuilt.
4. **Ask for short answers.** Output tokens cost 5x input tokens.
5. **Check `npx claude-lean report --days 7` weekly.** It shows where the money actually went.

Sources: Anthropic's [cost guide](https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence) and [cookbook](https://platform.claude.com/cookbook/cost-optimization-cost-optimization).

## What we got wrong

Until 0.2.3 this page led with "long sessions cost 65% less" ($4.97 → $1.74 on Opus 5.5). Our eval resumed one Claude Code session per task for the plain side, and a resumed session reports `total_cost_usd` as a running total for the whole session. We added those running totals, so every earlier step was counted again at each step. Measured per step, the plain session cost $0.77, not $4.97, and the fresh-session setup cost more.

The fix is in `evals/run.py` (`step_usd`), every saved result keeps the original figure as `usd_reported`, and the tables above use the corrected numbers. The short-task results were never affected: each task there is a single fresh call.

## Security & privacy

- **Local, with one exception.** No telemetry, no account, nothing about you or your code is sent anywhere. The one network feature is web search: when Claude runs a WebSearch, the hook sends that search query (only the query) to public search engines (DuckDuckGo, Brave, Bing, Marginalia, Mojeek, Yahoo) and, for project queries, GitHub's API, instead of Claude Code's own search, which sends it to Anthropic. Set `LEAN_WEB_SEARCH=0` to keep Claude Code's search; the 15-search cap still applies.
- **Readable.** Plain Python and JavaScript using only the standard library. No binary, no dependencies. What's on GitHub is exactly what npm installs.
- **Your logs stay put.** `report` and `audit` read `~/.claude/projects` and print to your terminal.
- **What it stores.** The last 200 trimmed outputs, in `~/.cache/claude-lean/out` (readable only by you), and a handoff note until it's used or 12 hours pass. `uninstall` deletes both.
- **Your permissions still apply.** The filter can rewrite a command, but never approves one.

## FAQ

**Why is my bill high when Claude writes so little code?** Each request re-reads the whole context. A 300K-token session re-read 50 times is 15 million tokens, mostly at the cached rate, plus a full-price cache write every time the prompt start changes.

**Does it help short tasks?** Yes. The long-session guard stays out of the way there, but slim (-32%) and `lite` (-74%) cut the fixed overhead every request carries.

**Does the output filter change exit codes?** Yes. A filtered command runs through a pipe, so Claude sees exit code 0 even when tests fail. Every error and summary line is kept, so the failure still shows. To skip the filter, use `init --no-filter`.

**Can subagents run on Haiku?** Yes, with a named agent file (`model: haiku`) like [`agents/reader.md`](https://github.com/JacobTheJacobs/claude-lean/blob/master/agents/reader.md); install it with `init --reader`. `fork` subagents always use your main model.

## Contributing

Filters for more commands help the most. See [CONTRIBUTING.md](https://github.com/JacobTheJacobs/claude-lean/blob/master/CONTRIBUTING.md); `npm test` runs every test. Report bugs or request a filter in [issues](https://github.com/JacobTheJacobs/claude-lean/issues).

## License

Built by [JacobTheJacobs](https://github.com/JacobTheJacobs) with [Claude Code](https://claude.com/claude-code).

MIT. Release notes are in [CHANGELOG.md](https://github.com/JacobTheJacobs/claude-lean/blob/master/CHANGELOG.md).
