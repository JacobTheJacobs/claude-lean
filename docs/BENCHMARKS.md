# Claude Lean benchmarks

Every benchmark we ran, including the ones that went against us. Each comes from a script in
[`evals/`](../evals) or from the public [THOL](https://github.com/pi-infected/token-harness-optimizer-leaderboard)
harness, and can be re-run.

## SWE-bench

Plain Claude Code vs Claude Lean (`init`, `LEAN_WEB_AGY=1`) on real GitHub issues, graded by the official SWE-bench
harness. Sonnet 4.6, the code-compression-bench prompt, max 100 turns, one run per task, 2026-11-23/24.

| | Tasks | Solved, plain / Lean | Cost, plain / Lean | Time, plain / Lean |
|---|--:|--:|--:|--:|
| SWE-bench Lite | 10 | 6 / 5 | $10.17 / $3.99 (-61%) | 76 / 21 min |
| SWE-bench Verified | 33 | 20 / 20 | $24.78 / $25.38 (+2%) | 135 / 137 min |
| Total | 43 | 26 / 25 | $34.95 / $29.37 (-16%) | 211 / 158 min |

Earlier, the first 10 Verified tasks: plain 8, Lean 6 solved, Lean 25% cheaper (grading logs lost to a reboot, not in the table).

- **Variance.** Lean was cheaper on 19 of 33 Verified tasks; four hard tasks that ran 50-100 turns cancel that out.
  Rerunning the two worst gave plain $0.80 then $3.57 and Lean $2.72 then $1.26 on the same task, so one run per task
  can't resolve a few percent.
- **Losses studied.** Lean lost django-15973 (a guard where the error showed up instead of a fix at the cause) and
  sphinx-8548 (fixed only base classes in the same module). 0.2.8 adds "root cause first" and "make it general"; on
  rerun Lean solved both. sympy-16503 still fails (plain solved it 1 of 2 times).
- **Test rule kept.** Without the rule against editing existing tests, Lean cost more on both hard tasks ($2.54 and $4.72).

## 1. THOL: every tool on the board

| Tool (version) | Short tasks (10) | Heavy tasks (7) | All 17 | Runs passed |
|---|--:|--:|--:|--:|
| **Claude Lean** (0.2.5) * | **+12.5%** | **+34.7%** | **+22.4%** | 51/51 |
| tokenade (0.8.13) | +9.9% | +38.9% | +23.2% | 170/170 |
| claude-token-efficient (b32fa8b) | -0.3% | +11.6% | +4.8% | 170/170 |
| ponytail (main) | +4.7% | +3.5% | +4.2% | 170/170 |
| caveman (v1.9.0) | -7.2% | +13.6% | +1.9% | 170/170 |
| graphify (0.8.49) | -0.8% | +3.3% | +0.9% | 170/170 |
| edgee (v0.2.13) | -13.6% | +14.7% | -0.9% | 169/170 |
| squeez (1.22.1) | -7.0% | +6.9% | -1.0% | 170/170 |
| code-review-graph (2.3.6) | -8.5% | +8.5% | -1.1% | 170/170 |
| codegraph (0.9.9) | -14.7% | +7.6% | -4.9% | 170/170 |
| rtk (v0.42.3) | -3.9% | -7.1% | -5.2% | 170/170 |
| lean-ctx (3.8.4) | -33.6% | -10.3% | -23.4% | 170/170 |
| headroom (0.27.0) | -57.7% | -52.8% | -55.7% | 170/170 |

Cost reduction vs plain Claude Code (higher is better), geometric mean over tasks, Sonnet 4.6. Every other row is
the THOL board as published (10 runs per task, Claude Code 2.1.206). \* Claude Lean: our local run of the same
harness and tasks, 3 runs per task, Claude Code 2.1.239, 2026-11-22; not an official board entry yet.

Claude Lean per run vs plain: output tokens -18%, cache reads -32%. Biggest wins: Django settings inventory -59%,
ledger debugging -49%, PDF report -49%, web research -46% ($3.13 → $1.70, same score). Tasks that cost more: Django
code questions +10% and seo audit +5%, both inside run-to-run noise. An earlier 0.2.4 build without the web search
hook scored +16.9% / +26.9% / +21.2%.

## 2. Our evals (Haiku 5.5)

Same graded tasks, Haiku 5.5, clean Claude Code setup, two runs per cell (2026-11-20, `evals/compare.py`, 238 tasks;
measured before the web, read and MCP hooks were added):

same graded tasks, Haiku 5.5, clean Claude Code setup, two runs per cell (2026-11-20, `evals/compare.py`, 238 tasks; measured before the web, read and MCP hooks were added, which the THOL run above includes):

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

## 3. In dollars, and on a heavy setup

The comparison above, in dollars:

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

Raw results: [`evals/short-results.jsonl`](../evals/short-results.jsonl). To measure long sessions yourself:

```bash
python3 evals/long.py --reps 2         # 10 tasks in a row, Haiku, about $0.20
```

Each session stops at `--budget` dollars (default $2), so a re-run can't surprise you.

## 4. vs JFrog Boost (old)

> **Old result (Claude Lean 0.2.2, 2026-11-19).** This compared an earlier build whose main idea, a fresh session per task, turned out to cost more (see [What we got wrong](#6-what-we-got-wrong)); that approach is gone. Current numbers are in sections 1 and 2. A re-run against JFrog Boost with 0.2.4 is pending.

Same graded tasks, same machine, Haiku 5.5. JFrog Boost v0.17.5 was installed with `boost init --claude` in a separate HOME (`evals/vs.py`). Every run is counted:

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

## 5. Tested and rejected

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

## 6. What we got wrong

Until 0.2.3 this page led with "long sessions cost 65% less" ($4.97 → $1.74 on Opus 5.5). Our eval resumed one Claude Code session per task for the plain side, and a resumed session reports `total_cost_usd` as a running total for the whole session. We added those running totals, so every earlier step was counted again at each step. Measured per step, the plain session cost $0.77, not $4.97, and the fresh-session setup cost more.

The fix is in `evals/run.py` (`step_usd`), every saved result keeps the original figure as `usd_reported`, and the tables above use the corrected numbers. The short-task results were never affected: each task there is a single fresh call.
