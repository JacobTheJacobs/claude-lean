# Changelog

## [0.2.7] - 2026-11-23

### Fixed
- Slim no longer turns off Claude Code's git instructions. With them off, Claude failed SWE-bench django-13297 0/6
  (same wrong fix, then edited the existing test to match); with them on it solved it 6/6. Costs 2.4K tokens per request.
  Run `init` again (or `slim on`) to update.
- `lite` now really sets the slim switches (it set them without the `CLAUDE_CODE_DISABLE_` prefix, so they did nothing).
- `LEAN_WEB_AGY=1`: web search adds Google results through `agy` (opt-in; waits up to 45 s).
- Output budget: one rule against editing existing tests to make a change pass.

## [0.2.6] - 2026-11-23

### Changed
- Web search hook sends an honest client name by default; browser headers only with `LEAN_WEB_BROWSER=1`. With the
  honest name only GitHub's API answers from most machines, so general searches fall back to Claude Code's own search
  (still capped at 15). 0.2.0-0.2.5 were removed from npm on 2026-11-22, likely by npm's automated scan.

## [0.2.5] - 2026-11-22

### Changed
- Web search engine state moved from shared /tmp to ~/.cache/claude-lean (a predictable /tmp file could be
  pre-created by another user on a shared machine).
- Short README (GitHub and npm): one THOL table with every tool; all benchmarks in docs/BENCHMARKS.md, every
  feature in docs/FEATURES.md. Claude Lean row updated to the full 0.2.4 run (+22.4% overall).

## [0.2.4] - 2026-11-20

### Added
- Expired-cache note (session_guard): returning to a long session after the cache TTL (1 h subscription, 5 min API
  key; `LEAN_CACHE_TTL`) shows what the next message rewrites.
- WebFetch: the same URL and question fetched again points at the earlier answer. Retry-loop note covers Edit.
- `audit`: context added without asking (skill listings, invoked skills, hook output), hooks failing on every call,
  verbose output styles. `memory`: counts CLAUDE.md `@imports`.
- Rules: narrowest test first; filter background watchers to events you act on.
- Plugin: MCP compaction hook was missing; added. `report`: Haiku 5.5 priced as Claude Code reports it ($5/$25).
- `audit --profile [DIR]`: per-project `skillOverrides` off and `mcp__<server>__*` deny rules for skills and user MCP
  servers that project never used (`--unprofile` undoes it); `audit` shows each skill's size once it runs.
- Cost status line (`tools/statusline.py`): cost, context fill, cache hit rate, 5-hour limit; only added when none.
- Pasted-prompt note (session_guard): a prompt over 40K characters gets a one-line note to the user.
- Read guard also pauses files over 100 KB (notebooks, one-line JSON); faster transcript scan.
- Web search honors `allowed_domains`. README privacy section now says the search hook sends queries to public
  search engines and GitHub (it said "no network calls"); `LEAN_WEB_SEARCH=0` keeps Claude Code's search.
- MCP compaction keeps top-level fields and empty lists (`"items": []` means nothing found); drops only nested null/"".
- Rule: extract PDF text before reading a PDF when only the text matters. README: CI cost settings.
- Python 3.8: web_guard no longer uses a 3.9-only argument.
- Read guard (`hooks/read_guard.py`): a full read of a file over 1,000 lines is paused once with its size and a hint
  to Grep or read a range; an identical re-read of an unchanged file (no compaction since) returns a one-line note.
  Measured on the author's logs: Read results were 36% of spend.
- Deny rules for `node_modules`, minified JS/CSS and source maps (`--no-deny` to skip; uninstall removes only ours).
- MCP result compaction (`hooks/mcp_compact.py`): drops null/empty JSON fields and indentation, every other value kept.
- Retry-loop note (`hooks/loop_guard.py`, PostToolUseFailure): the third identical failure of a command gets one note.
- Compaction instructions (`hooks/compact_hook.py`, PreCompact): keep paths, commands, errors, decisions, next step.
- Web search: GitHub's repository search API joins the public engines for project queries; pages an earlier search
  already showed are listed only as a count.
- Output budget: edit instead of rewriting, to-do list only for 4+ steps, batch independent tool calls, page text
  before screenshots (~280 tokens in all).
- `report`: estimated cost of each tool's results while in context; fast-mode spend; the long-context tip no longer
  recommends a fresh session per task (measured to cost more).
- docs/COST-MAP.md: every cost lever, with status.
- No-subagent rule in the output budget: "do the reading yourself with Grep, Glob and Read". Slim alone made Claude start
  9-10 Explore subagents on reading tasks (THOL Django questions +109%); with the rule, 0 of 3 runs fanned out and the task
  costs 9% less than plain. Kept under `--no-terse` / `LEAN_TERSE=0`.
- THOL (Sonnet 4.6, 17 tasks, 3 runs each, Claude Code 2.1.239): +12.5% short, +34.7% heavy, +22.4% overall cost
  reduction vs plain (tokenade's board figures: +9.9% / +38.9% / +23.2%); every run passed.
- Claude Code plugin: `/plugin marketplace add JacobTheJacobs/claude-lean`, then `/plugin install lean@claude-lean`.
  Long-session guard, handoff, cache guard, both skills, and `/lean:slim`, `/lean:report`, `/lean:audit`,
  `/lean:memory`. The output filter stays npm-only (its rewritten command needs a permission rule a plugin can't add).
- `tools/slim.py` (`/lean:slim on|off`): adds or removes the 6 slim settings; `install.sh` now uses it too.
- Output budget (`hooks/terse_hook.py`, on by default, `--no-terse` to skip, `LEAN_TERSE=0` per session): ~120 tokens (now ~280) of
  standing rules at session start (smallest change, 1-3 line final answers, never trim correctness). Long sessions
  write 25% fewer output tokens; short tasks -37% cost vs -21% without it.
- Measured against ponytail 5.3.3 and caveman v4.1.0 on a clean base (Haiku 5.5, 238 tasks): `init` -37% / -2% / -30%
  (short / long / noisy), `lite` -57% / -34% / -60%, ponytail +7% / +5% / +29%, caveman +11% / +6% / +15%.
- `install.sh`, `slim.py` and `doctor` honor `CLAUDE_CONFIG_DIR`.
- `claude-lean report --compare [DATE]`: your own fresh sessions before vs after installing (first-request size,
  cost per request and per session), from your logs.
- `evals/compare.py`: Claude Lean vs caveman v4.1.0 vs RTK v1.2.1 on the same graded tasks. `lite` -44% to -61% in
  every suite, ahead of both; plain `init` -2% to -24%; caveman +7% to -21%; RTK -1% to -14% (Haiku 5.5, 170 tasks,
  all passed).

### Fixed
- Evals launched from a machine with Claude Lean installed inherited its slim switches in every arm (Claude Code
  exports settings `env` into the shells it starts). `evals/run.py` now strips them; the first five-way run is kept,
  marked, and shown separately in the README.

### Measured (clean setup, Haiku 5.5, every task passed)
- `init`: short tasks -36%, noisy output -44%, long session +12% (noise). `lite`: -70%, -64%, -32%.
- Real setup, fresh session's first request: 46,018 -> 29,179 tokens (-37%); warm-cache cost $0.0031 -> $0.0004.

## [0.2.3] - 2026-11-20

### Fixed: the long-session claim was wrong
- Earlier versions said long sessions cost 65% less with a fresh session per task ($4.97 -> $1.74 on Opus 5.5). The
  evals resumed one Claude Code session for the plain side, and a resumed session reports `total_cost_usd` as a running
  total for the whole session. We added those running totals, so earlier steps were counted again at every step.
- Measured per step, one continuous session is cheaper when tasks run back to back: Haiku 5.5 $0.028 vs $0.058 for a
  fresh session per task (+109%), Opus 5.5 $0.77 vs $1.74 (+126%). Cached history is billed at a tenth of the input
  price; each new session pays to write its starting context again.
- All eval scripts now count each step's own cost (`evals/run.py` `step_usd`). Saved results keep the original figure as
  `usd_reported`. Short-task results (-32% slim, -74% `lite`) were single fresh calls and are unaffected.
- The long-session guard no longer promises savings; it suggests `/clear` for focus before unrelated work.
- README, demo GIF and package description lead with the short-task results. The 65% images are gone.
- Evals run with `--setting-sources project,local`, so the machine's own installed hooks can't leak into any arm.
- New evals: `evals/chain.py` (dependent follow-up tasks, with and without handoff) and `evals/pileup.py` (output
  filter over a long fix-and-rerun session).

## [0.2.2] - 2026-11-20

### Added
- GitHub Action (`action.yml`): `uses: JacobTheJacobs/claude-lean@v0.2.2` installs Claude Lean on a CI runner before
  Claude Code starts. Inputs `filter` and `slim` (both on by default).

### Changed
- README rewritten: one results table for long and short sessions, CI section, vs JFrog Boost with every batch.
- The release workflow skips the npm step when the `NPM_TOKEN` secret is missing.

## [0.2.1] - 2026-11-20

### Fixed
- `report` and the daily cap crashed on Python 3.8 and 3.9 (`str | None` needs 3.10). Tests now run on 3.8.
- The output filter no longer touches commands that keep running (`npm run dev`, `npm start`, `--watch`, `cargo run`,
  `docker compose up`): it prints only after exit, so their output was hidden. `npm run` is filtered only for
  build, test, lint and check scripts; `uv run pytest` and `poetry run pytest` are now filtered.
- If the filter fails (full disk, broken cache), the command's output passes through unchanged.
- Install folders with spaces (`/Users/John Doe`) work: hook commands and the handoff skill quote their paths.
- The daily cap reads only what was appended to each transcript since the last check, instead of re-reading every
  log (seconds to minutes on multi-gigabyte logs).
- CI runs on `master`.

### Changed
- `lite` also applies the slim switches (first request on a clean install: 17.2K -> 5.4K tokens).
- `uninstall` removes `~/.cache/claude-lean` (saved outputs, handoff notes). Saved outputs are owner-only.

## [0.2.0] - 2026-11-19

### Added
- `claude-lean audit`: skills and MCP servers loaded on every request but unused in your logs; park unused skills
  reversibly (`--disable-unused`, `--restore`). Saving is small (~200 tokens for 23 skills): Claude Code caps the listing.
- Handoff: the `handoff` skill saves a short note before `/clear`; `hooks/handoff_hook.py` loads it into the next
  session in the same folder once. The long-session guard now suggests it.
- `claude-lean memory`: what the memory index and CLAUDE.md cost on every request, per project.
- Slim, on by default: `init` sets six `CLAUDE_CODE_DISABLE_*` switches that drop ~24K tokens of unused feature
  definitions from every request (49.5K -> 24.9K). Short tasks -32%, 15/15 passed in both. `--no-slim` skips it.
- `claude-lean lite`: starts Claude Code with only the core tools, no MCP, no skills. Short tasks -74%
  ($0.0081 -> $0.0021 per task on Haiku 5.5, 15/15 passed in both).
- `evals/vs.py`: head to head with JFrog Boost (plain, jfrog, lean, lean+jfrog).
- npm package: `npx claude-lean init`, plus `uninstall`, `report`, `stats`, `get`, `doctor`.
- Output filter (`hooks/squeeze_hook.py`, `tools/squeeze.py`): trims noisy npm, pip, cargo, go, docker and make output and
  keeps every error and summary line. Originals are saved locally and come back with `claude-lean get <id>`. A tool's
  filter turns itself off after its originals are fetched 3 times.
- The installer now merges the hooks into `~/.claude/settings.json` for you, with a backup first, `--dry-run`,
  `--uninstall` and `--no-filter`. Safe to re-run. `LEAN_DAY_USD=N` adds the daily cap.
- Tests (Python unittest + node:test) and CI on Linux and macOS.
- Eval: `--budget` dollar cap per session (default $2), Haiku default, `evals/filter.py`.

### Changed
- Renamed from Claude Boost to Claude Lean. Env vars are now `LEAN_*`, the cache is `~/.cache/claude-lean`, and
  `tools/boost.py` is now `tools/report.py`.

## [0.1.0] - 2026-11-12

### Added
- Long-session guard, cache guard, daily budget hook, usage report, lean skill and Haiku reader agent.
- Long-session eval on Opus 5.5: -65% per 10-task session, 20/20 tasks passed in both setups.
