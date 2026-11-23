# Claude Code cost map

Every place a Claude Code session spends money, what Claude Lean does about each one, what it doesn't do yet, and
what we tested and dropped. It is the roadmap for Claude Lean.

Status labels:

- **DONE**: shipped and measured.
- **PARTIAL**: shipped but only covers part of the cost.
- **MISSING**: not built.
- **REJECTED**: measured, and it cost more or saved nothing.
- **VERIFY**: a claim we have not checked yet.
- **BLOCKED**: needs something Claude Code doesn't ship yet.

Numbers come from our evals (`evals/`, Haiku 5.5) and our local THOL runs (Sonnet 4.6, Claude Code 2.1.239), unless
a line says otherwise.

---

## 1. Where the money goes

One Claude Code request is billed as:

```
uncached input x 1   +   cache write x 1.25 (5-min cache) or x 2 (1-hour cache)   +   cache read x 0.1   +   output x 5
```

The multipliers are relative to the input price. Sonnet 4.6 per million tokens:

| Input | Output | Cache write (5 min) | Cache write (1 hour) | Cache read |
|--:|--:|--:|--:|--:|
| $3 | $15 | $3.75 | $6 | $0.30 |

Web search adds a fee of $10 per 1,000 searches. Haiku 4.5 costs $1 input and $5 output.

A session is a loop of these requests. Every turn re-reads the whole conversation from cache, and it writes whatever
is new to cache. Cost therefore comes from six things:

1. **The fixed start of the prompt** (system prompt, tool definitions, skills, CLAUDE.md, memory). It is written to
   cache once and read again on every turn.
2. **Growth of the conversation.** Each tool result is written once, then read on every later turn.
3. **The number of turns.** Every tool call is another turn, and every turn re-reads everything.
4. **Output**, including thinking, at 5 times the input price.
5. **Hidden extra requests:**
   - each web search is a separate model request;
   - WebFetch and the auto-mode safety check run on Haiku;
   - subagents and compaction summaries are requests of their own.
6. **Cache misses.** Anything that changes the start of the prompt makes the next request write it all again.

Where the money went in our THOL runs, per run, plain Claude Code compared with Claude Lean `init`:

| | Short tasks | Long tasks |
|---|---|---|
| Output tokens | 2.8K vs 2.1K | 9.5K vs 7.7K |
| Cache reads | 136K vs 85K | 466K vs 295K |
| Cache writes | 12.5K vs 11.7K | 30.8K vs 27.4K |

Web research was the exception. About 45% of its cost was the hidden web-search requests: 250K-475K tokens of
uncached input per run.

---

## 2. Summary

| # | Area | Lever | Status | Measured effect |
|---|---|---|---|---|
| A1 | Fixed prompt | Slim: turn off 6 unused Claude Code features | DONE | short tasks -32% |
| A2 | Fixed prompt | `lite`: core tools only, no MCP, no skills | DONE | short -57%, long -34%, noisy builds -60% |
| A3 | Fixed prompt | Audit unused skills and MCP servers | DONE | small (the skill list is capped) |
| A4 | Fixed prompt | Memory and CLAUDE.md size check | DONE | depends on the user's setup |
| A5 | Fixed prompt | Per-project MCP and plugin profiles | DONE: `audit --profile` | per project: unused personal skills off, unused user MCP servers denied |
| A6 | Fixed prompt | Trim long skill and agent descriptions | DONE (audit shows description sizes) |  |
| B1 | Cache | Warn before edits that rebuild the cache | DONE | |
| B2 | Cache | Keep the prompt start stable across sessions | DONE (slim) | first request on a warm cache: $0.0031 → $0.0004 |
| B3 | Cache | 5-minute vs 1-hour cache choice | VERIFY | settings exist from Claude Code 2.1.242 (`CLAUDE_CODE_PROMPT_CACHE_TTL`, `FORCE_PROMPT_CACHING_5M`); not measured yet |
| B4 | Cache | Warn on model, effort or MCP changes mid-session | BLOCKED | needs the PostModelSwitch hook event, not in Claude Code 2.1.239 |
| C1 | Conversation growth | Output filter for Bash logs | DONE (npm only) | noisy builds -30% |
| C2 | Conversation growth | Replace identical re-reads with a short note | DONE, not cost-measured yet | live-tested: re-read replaced by a one-line note, edits still work |
| C3 | Conversation growth | Large-file read guard (read a range or search instead) | DONE, not cost-measured yet | live-tested |
| C4 | Conversation growth | Never read generated files (`node_modules`, lockfiles, builds) | DONE (npm only), not cost-measured yet |  |
| C5 | Conversation growth | Compact MCP results | DONE, not cost-measured yet | live-tested: demo MCP result 1.3K → 0.5K characters |
| C6 | Conversation growth | Screenshots: read text first, fewer images | DONE (rule), not cost-measured yet |  |
| C7 | Conversation growth | Compact web-search results; skip URLs already shown | DONE, THOL test pending |  |
| C8 | Conversation growth | Compaction timing | REJECTED (compact early: +32%) | |
| C9 | Conversation growth | Steer what the compaction summary keeps | DONE, not cost-measured yet |  |
| D1 | Turns | No subagent fan-out rule | DONE | THOL Django question task +109% → -9% |
| D2 | Turns | Batch independent tool calls in one turn | DONE (rule), not cost-measured yet |  |
| D3 | Turns | Stop retry loops (the same failing command again and again) | DONE, not cost-measured yet | live-tested: note arrives on the 3rd identical failure |
| D4 | Turns | Long-session note, `/clear` advice, handoff | DONE | measured: a fresh session per task costs more |
| E1 | Output | Output budget rules | DONE | long-session output -25%; THOL output -19% to -25% |
| E2 | Output | Thinking and effort level per task | PARTIAL | `--effort low` on Opus -6.5% (noise level) |
| E3 | Output | Edit instead of rewriting whole files | DONE (rule), not cost-measured yet |  |
| E4 | Output | Less to-do list and progress chatter | DONE (rule), not cost-measured yet |  |
| F1 | Model choice | Haiku `reader` agent for read-only lookups | DONE (opt-in) | |
| F2 | Model choice | Subagents on Haiku | REJECTED | -2%, noise |
| F3 | Model choice | Opus advisor | REJECTED | +24% |
| F4 | Model choice | Pick the model by task | ADVICE ONLY | switching mid-session rebuilds the cache; the choice is the user's |
| F5 | Model choice | Fast mode warning | DONE (report line) |  |
| G1 | Web | Web rule (fetch pages rather than many searches) | DONE | -6% vs plain |
| G2 | Web | Search cap (15 paid searches per session) | DONE | web research -36%, score 0.57 vs 0.50 |
| G3 | Web | Own search through public engines instead of paid WebSearch | DONE, THOL test pending | 0 paid searches in a live test |
| G4 | Web | GitHub's official search API as a second source | DONE, THOL test pending |  |
| G5 | Web | Fetch pages ourselves, without the Haiku summary | MISSING | |
| H1 | MCP | Load tools only when needed | built into Claude Code | |
| H2 | MCP | Compact MCP results | DONE | same as C5 |
| H3 | MCP | Turn MCP servers on per project | DONE | same as A5 |
| I1 | Computer use | Read text first, fewer screenshots | DONE (rule) | same as C6 |
| I2 | Computer use | Shrink screenshots | MISSING | |
| J1 | Billing | Daily dollar cap | DONE | |
| J2 | Billing | Cost report, and before/after comparison | DONE | |
| J3 | Billing | Cost by tool (which tool cost what) | DONE (estimate) | author's logs, 2 days: Read results 36% of spend, Bash 4% |
| K1 | CI | GitHub Action with lean defaults | DONE (ready, not released) | |
| L1 | Hidden requests | Measure the auto-mode check, titles and summaries | VERIFY | |
| M1 | Visibility | Cost status line (cost, context, cache hit rate, 5-hour limit) | DONE (npm only) | |
| M2 | Prompt | Note on pasted prompts over ~10K tokens | DONE | |
| M3 | Conversation growth | Pause reads of files over 100 KB (notebooks, one-line JSON) | DONE | closes a gap in C3 |
| M4 | Conversation growth | Large skills stay in context after they run | DONE (audit shows the size) | one skill on the author's machine is ~9K tokens |
| M5 | Conversation growth | PDFs: extract text first when only text matters | DONE (rule) | |
| M6 | Conversation growth | Grep in content mode returning thousands of lines | MISSING | check whether Claude Code already caps it (VERIFY) |
| M7 | Web | Compact Claude Code's own search results when it falls back | MISSING | small: the search's cost is already paid |
| K2 | CI | Cost settings for CI (`--max-turns`, narrow tools, lite) | DONE (README) | |
| N1 | Cache | Note when you return after the cache expired, or resume a long session | DONE | 1 h subscription, 5 min API key |
| N2 | Turns | Background watchers wake Claude per event (each wake re-reads everything) | DONE (rule) | |
| N3 | Turns | Failing edits in a loop | DONE (retry-loop note covers Edit) | |
| N4 | Web | Same page fetched twice | DONE | |
| N5 | Turns | Full test suite on every change | DONE (rule) | |
| N6 | Fixed prompt | Context added without asking (listings, invoked skills, hook output) | DONE (`audit`) | author: skill listing ~10K and invoked skills ~10K tokens per session |
| N7 | Output | Verbose output styles | DONE (`audit`) | |
| N8 | Fixed prompt | CLAUDE.md `@imports` | DONE (`memory`) | |
| N9 | Setup | Hooks that fail on every call | DONE (`audit`) | author: ~41,000 failures in 3 days from one broken hook |
| G6 | Web | Google results through a stealth headless browser (Obscura) | DROPPED | Claude Code's safety check blocked testing it as unauthorized access; it works by getting past Google's bot protection |

---

## 3. Details

### A. The fixed start of the prompt (paid on every request)

Every request carries the system prompt and every tool definition (17-50K tokens). With caching it is read at a tenth
of the price on most turns, but it is written in full at the start of every session and after every cache miss.

- **A1 Slim (DONE).** Sets `CLAUDE_CODE_DISABLE_{ARTIFACT,WORKFLOWS,BACKGROUND_TASKS,CRON,ADVISOR_TOOL}`. Git instructions were dropped from the
  list on 2026-11-23: with them off, SWE-bench django-13297 failed 0/6; with them on, 6/6 (plain, no-slim, slim minus git).
  - Measured per request: Artifact 13.5K, Workflows 8.1K, git instructions 2.4K, background tasks 1.1K, cron 0.3K and
    advisor 0.2K tokens.
  - Side effect found on THOL: without the subagent rule (D1), slim made Claude fan out to 9-10 Explore subagents.
- **A2 `lite` (DONE).** Starts Claude Code with core tools only and no MCP servers or skills. The first request drops
  from 17.2K to 5.4K tokens. It is the biggest single lever, but it gives up features, so it is a separate command.
- **A3 Audit (DONE).** `tools/audit.py` finds skills and MCP servers unused in the last N days, and can park skills.
  The saving is small because Claude Code caps the skill listing: 23 parked skills went from 49.5K to 49.3K tokens per
  request. The main gain is a shorter, more relevant skill list.
- **A4 Memory check (DONE).** `tools/memcheck.py` sizes every project's MEMORY.md and CLAUDE.md, all of which ride
  along in every request.
- **A5 Per-project profiles (DONE: `claude-lean audit --profile [DIR]`, undo with `--unprofile`).** Writes `skillOverrides` and `mcp__<server>__*` deny rules (a deny rule on a whole server removes its tools from the context) to the project's `.claude/settings.local.json`. Turn on only the MCP servers and plugins a project uses, via project
  `settings.json` (`enabledMcpjsonServers`, plugin enable lists).
  - Payoff: large on heavy setups. The author's machine has many plugins and a 46K-token first request.
  - Next: `claude-lean profile` writes a project `settings.json` from what `audit.py` saw used in that project.
- **A6 Description trimming (DONE in audit).** `audit` already shows each skill's description size. Some skills, plugins and agents ship descriptions of 1-2K characters. The
  listing is capped, but long descriptions still crowd it.
  - Next: have `audit` report the longest descriptions, and say which ones belong to the user (editable) and which to
    plugins (not editable).

### B. The prompt cache

- **B1 Cache guard (DONE).** Warns before an edit to CLAUDE.md, AGENTS.md or settings mid-session, because that
  rebuilds the whole cached prompt.
- **B2 Stable prompt start (DONE through slim).** Without slim, part of the prompt start changed on every run and
  missed the cache. Measured on the author's setup: first request on a warm cache $0.0031 → $0.0004.
- **B3 Cache duration (VERIFY).** Claude Code 2.1.242 added `CLAUDE_CODE_PROMPT_CACHE_TTL` (`5m`/`1h`), `FORCE_PROMPT_CACHING_5M` and `promptCacheTtl`; the default is 1 hour on subscriptions. Our THOL runs used 2.1.239, which predates them. THOL billed cache writes at $6/M, the 1-hour price, which is 2x input instead of
  1.25x.
  - For short sessions, 5-minute writes would be cheaper.
  - Next: check whether Claude Code has a setting for this, and measure short tasks with each. The first run of a fresh
    setup paid +8K tokens of cache writes, which is what pushed THOL's bugfix task to +9%.
- **B4 Mid-session change warning (BLOCKED).** Claude Code's docs list a PostModelSwitch hook event, but 2.1.239 doesn't have it; build this once it ships. Switching model or effort, or turning an MCP server on or off,
  rebuilds the cache. README habit 3 says so, but no hook enforces it.
  - Next: a UserPromptSubmit check that compares the current model and effort with the session's start and warns
    once (a note to the user, no tokens added).

### C. Growth of the conversation (every result is re-read on every later turn)

A tool result costs one cache write, then a cache read on every turn after it. A 10K-token log read 30 turns later
has been paid about 31 times over, at 0.1x per read. Cutting a result early saves much more than its size suggests.

- **C1 Output filter (DONE, npm only).** Trims test and build logs and keeps failures. Noisy builds -30%.
  - It never fired in long sessions, because Claude already pipes to `tail` and `grep` itself.
  - The plugin can't include it: its rewritten command needs a permission rule.
- **C2 Re-read dedupe (DONE: `hooks/read_guard.py`, live-tested; edits still work after a deduped read).** Claude often reads the same file 2-4 times in a session.
  - A PostToolUse hook on Read can replace an identical re-read with "unchanged since your read at turn N", using
    `updatedToolOutput`.
  - Risk: after compaction the earlier copy is gone. So only dedupe when no compaction happened since that read, which
    the hook can see in the transcript.
  - tokenade does this ("identical re-reads become a tiny reference, or just the diff").
- **C3 Large-file guard (DONE: `hooks/read_guard.py`, 1,000 lines by default, `LEAN_READ_LINES`).** A PreToolUse hook on Read: for a file over about 1,500 lines with no
  offset/limit, block once and suggest a range, a Grep, or an outline. Claude can repeat the call to read it all.
- **C4 Never read generated files (DONE, npm install; `--no-deny` to skip).** Add `permissions.deny` rules for `Read(**/node_modules/**)`,
  lockfiles, `dist/` and `build/`, and minified files.
  - The plugin can't add permission rules, so this is npm only (the same limit as C1).
  - Risk: some tasks need a lockfile, so keep the list conservative and give a flag to skip it.
- **C5 MCP result compaction (DONE: `hooks/mcp_compact.py`, lossless mode only; live-tested).** MCP tools often return pretty-printed JSON with nulls, empty fields and long
  lists.
  - A PostToolUse hook (`updatedMCPToolOutput`) can strip nulls and empties, remove the formatting, and shorten lists
    over N items with a "+K more" note.
  - That is mostly lossless; list shortening is the lossy part, so keep it opt-in or set high.
  - tokenade has `mcp_compact.rs`.
- **C6 Screenshots (DONE as a rule; shrinking images is I2).** Each screenshot is an image of about 1-1.5K tokens (VERIFY at today's sizes), and
  they pile up.
  - Rule: read the page as text or through its accessibility tree where possible; screenshot only to check layout;
    not after every click.
  - A hook could shrink images, but that needs an image library and risks quality. See I2.
- **C7 Web results (DONE: pages an earlier search showed are listed only as a count).**
  - Our own search returns up to 15 compact hits, about 1.2K tokens per search.
  - Missing: skip URLs already shown in earlier searches, and compact native WebSearch results when we fall back to
    it (tokenade's `websearch_post`).
- **C8 Compaction timing (REJECTED).** Compacting early (a 100K window, or a 50% threshold) cost +32%: summaries
  cost money and rebuild the cache.
  - tokenade goes the other way: `CLAUDE_CODE_AUTO_COMPACT_WINDOW=700000`, to compact later.
  - Next: measure compacting late on THOL's long tasks (VERIFY).
- **C9 Compaction summary content (DONE: `hooks/compact_hook.py`).** A PreCompact hook can tell the summary what to keep: open decisions,
  file paths, failing tests. A better summary means fewer re-reads after compaction. tokenade has a PreCompact hook.

### D. The number of turns

- **D1 No subagent fan-out (DONE).**
  - Slim on its own led to 9-10 Explore subagents on reading tasks: THOL Django question task +109%, seo-audit +28%.
  - The rule "do the reading yourself" brought them to -9% and -11%.
- **D2 Batch tool calls (DONE as a rule).**
  - A rule: run independent reads, searches and commands together in one turn.
  - Every turn saved is one fewer full re-read of the conversation.
  - Measure the turn count before and after on THOL.
- **D3 Retry-loop breaker (DONE: `hooks/loop_guard.py`, PostToolUseFailure, live-tested).** When the same command fails 3 times with the same error, add a note (through
  PostToolUse additionalContext): "same failure 3 times; read the error, change approach, or ask".
  - tokenade calls this "anti-derailment" and aims it at long debugging tasks.
  - It would help on THOL's long debugging tasks (cascade 0.79 vs tokenade 0.65; pipeline 0.78 vs 0.73).
- **D4 Session length (DONE).** Measured: one continuous session is cheaper than a fresh one per task (+109% on
  Haiku, +126% on Opus for fresh sessions). The guard only tells you to `/clear` between unrelated tasks. Handoff
  notes carry a task across a `/clear`.

### E. Output (5x the input price; thinking counts as output)

- **E1 Output budget (DONE).** About 200 tokens of standing rules at session start: the smallest change, final
  answers of 1-3 lines, no recap, correctness kept. Long-session output -25%; THOL output -19% to -25%.
- **E2 Thinking and effort (PARTIAL).** Thinking is billed as output, and on hard tasks it is often most of the
  output.
  - Measured: `--effort low` on Opus -6.5%, which is noise level on our tasks.
  - Missing: guidance by task type (low for lookups and edits, high for debugging).
  - The effort setting itself is the user's choice; changing it mid-session rebuilds the cache (B4).
- **E3 Edit, don't rewrite (DONE as a rule).** Rule: change files with Edit; use Write only for new files or full
  rewrites. Rewriting a 400-line file to change 3 lines costs about 400 lines of output.
- **E4 To-do and progress chatter (DONE as a rule; no setting disables the tool, `permissions.deny` can).** Each to-do list update is a tool call (a turn) plus output.
  - Rule: use the to-do list only for 4 or more steps.
  - VERIFY whether a Claude Code setting turns it off.

### F. Model choice

- **F1 Haiku reader agent (DONE, opt-in).** Read-only lookups on Haiku (`--reader`).
- **F2 Subagents on Haiku (REJECTED).** Opus with subagents on Haiku (`CLAUDE_CODE_SUBAGENT_MODEL`): -2%, noise.
- **F3 Opus advisor (REJECTED).** +24%.
- **F4 Model by task (MISSING).** Sonnet cost 14x Haiku on our short tasks with the same pass rate (19/20 vs 20/20).
  - Next: a SessionStart or UserPromptSubmit note that suggests Haiku for small mechanical tasks.
  - It must never switch models on its own: switching rebuilds the cache (B4), and it is the user's call.
- **F5 Fast mode (DONE: `report` shows fast-mode spend).** Fast mode is billed at a premium. Next: show it in `report` as its own line.

### G. Web

- **G1 Web rule (DONE).** "One WebSearch costs about five WebFetch calls; fetch the richest page." Web research
  -6%, score 0.59 vs 0.50.
- **G2 Search cap (DONE).** 15 paid searches per session, after which Claude is sent to WebFetch.
  - Web research $3.13 → $1.99 (-36%), score 0.57 vs 0.50.
  - Set with `LEAN_WEB_SEARCHES`.
- **G3 Own search (DONE, THOL test pending).** The hook searches DuckDuckGo, Brave, Bing, Marginalia, Mojeek and
  Yahoo itself, sending a browser's headers. It drops off-topic results and returns the hits in place of the paid
  search; it falls back to the native tool after 8 seconds.
  - Live test: 0 paid searches, correct answer.
  - Weak spot: only DuckDuckGo answers from the test machine; the others block it.
  - Off with `LEAN_WEB_SEARCH=0`.
- **G4 GitHub search API (DONE: joins the engines for project queries; repos under 10 stars dropped).** For project and repo queries, GitHub's official search API returns real repos
  with stars, free, with no browser imitation. Best for code research.
- **G5 Fetch pages ourselves (MISSING).** Native WebFetch has Haiku summarize the page, which is lossy: a long
  awesome-list comes back partial.
  - Fetching the page ourselves and returning compact Markdown improves quality.
  - It can raise cost, because a full page is bigger than a summary, so cap the size.
  - tokenade does this, with per-site readers and a cache.
- **Google (REJECTED).**
  - Google's results page needs JavaScript, so a script gets an "enable JS" page with no results.
  - The official Custom Search JSON API is closed to new customers and shuts down on 2027-01-01.
  - Startpage and Ecosia, which show Google-based results, block scripts.

### H. MCP

- **H1 Loading tools when needed.** Recent Claude Code versions hide MCP tools behind ToolSearch until they are
  needed, so their definitions cost less than they used to. Claude Lean doesn't need to do anything here.
- **H2 Result compaction (DONE).** See C5.
- **H3 Per-project servers (DONE through A5).** See A5. `audit.py` already reports unused servers with the command to remove
  them.

### I. Computer use and the browser

- **I1 Text first (DONE as a rule).** See C6. It's a rule in the output budget, about 30 tokens.
- **I2 Shrink screenshots (MISSING).** A PostToolUse hook downscales images from computer-use and browser tools.
  - Needs Pillow or a similar image library (not standard Python), and risks losing small text.
  - Keep it opt-in, and measure it on a UI task first.

### J. Billing and measurement

- **J1 Daily cap (DONE).** `LEAN_DAY_USD`: a warning at 80%, the prompt blocked at 100%.
- **J2 Reports (DONE).** `claude-lean report` shows spend by day and session; `--compare` shows fresh sessions before
  and after install.
- **J3 Cost by tool (DONE as an estimate in `report`).** On the author's last 2 days: Read results 36% of spend, Bash 4%. Split each session's cost by what caused it:
  - main-loop output and context growth per tool;
  - web-search side requests;
  - Haiku side requests (WebFetch, the auto-mode check);
  - subagents.
  It is how we found the web-search cost on THOL. It would show every user their own top lever.
- **Subscriptions.** On Pro or Max, these dollars are a share of the usage allowance, not a bill. The report should
  say so.

### K. CI

- **K1 GitHub Action (DONE, waiting on a Marketplace release).** Runs Claude Code in CI with the lean defaults.
- **K2 Headless limits (DONE in the README CI section).** Document `--max-turns`, a narrow `--allowedTools` and lite mode for CI jobs.
  - In CI the prompt start is rebuilt on every run, so A2 (`lite`) matters most there.

### L. Hidden side requests (VERIFY)

- **The auto-mode safety check** runs a model request per tool call in auto mode. On long sessions it could matter.
  - Measure it from `modelUsage` in the session logs.
- **Session titles, compaction summaries, WebFetch's Haiku summaries.** Small each. Count them in J3.

---

## 4. Tested and rejected

| Lever | Result | Passed |
|---|--:|:-:|
| A fresh session per task (Haiku 5.5) | +109% | 20/20 both |
| A fresh session per task (Opus 5.5) | +126% | 20/20 both |
| A fresh session per step on chained tasks | +60% | 18/18 |
| The same, with a handoff note | +129% | 18/18 |
| Output filter over 10 fix-and-rerun steps | no effect (never fired) | 20/20 |
| Compact early (100K window, 50% threshold) | +32% | 20/20 |
| Opus advisor on Sonnet | +24% | 20/20 |
| Sonnet instead of Haiku | 14x the cost | 19/20 vs 20/20 |
| Subagents on Haiku under Opus | -2% (noise) | 20/20 |
| Opus `--effort low` | -6.5% (noise level) | 20/20 |
| Prompt rule alone to limit web searches | -6% (Claude only partly follows it) | 3/3 |
| Scraping search engines with a plain user-agent | blocked, or decoy results | — |
| Google results page, Custom Search API | needs JavaScript; API closed to new users | — |
| Slim turning off git instructions (2.4K tokens a request) | lost SWE-bench django-13297 0/6 vs 6/6 | removed from slim |
| Context as images ([pxpipe](https://github.com/teamchong/pxpipe), not tested by us) | their claim: -59-70% on Fable 5 and Gemini; Sonnet/Opus 5.5 read 0-3/15 exact IDs from the images | not adopted: silent wrong reads |

---

## 5. What to build next

Status on 2026-11-21: most of the map is built. What's left, in order:

1. **Measure what was just built.** Read guard, MCP compaction, retry-loop note, compaction instructions and the new
   rules are live-tested but not cost-measured. Run THOL short and long tasks and our evals, then report the numbers,
   good or bad, in the README.
2. **G3/G4/C7 THOL web test** (`claude-lean-search`). It finishes the only area where tokenade beat us.
3. **B3 cache duration.** Once Claude Code 2.1.242+ is installed, measure `CLAUDE_CODE_PROMPT_CACHE_TTL=5m` on short
   tasks. If it saves money, add it to slim for short sessions.
4. **C8 compacting late.** Measure `CLAUDE_CODE_AUTO_COMPACT_WINDOW=700000` on THOL's long tasks.
5. **Plugins per project.** `audit --profile` covers skills and MCP servers; turning plugins off per project (`enabledPlugins`) needs usage detection per plugin.
6. **B4 model-switch note.** When the PostModelSwitch event ships.
7. **G5 fetching pages ourselves, and I2 shrinking screenshots.** Quality-sensitive; opt-in only, after measurement.
8. **F4 model by task, and E2 effort by task.** These stay as advice: switching mid-session rebuilds the cache, and
   the choice is the user's.

Every item ships as a default only after an eval shows a lower cost with the same pass rate: our evals for short,
long and noisy tasks, and THOL for long and web tasks. A result that goes against us goes in the README.

---

### Found while building

- **From the Claude Code Ultimate Guide review (2026-11-23):**
  - `CLAUDE_CODE_ATTRIBUTION_HEADER=false` is now in slim. The header made each new session and subagent re-write
    ~6K tokens of cache (2.1.330: 6,262 written vs 0).
  - `CLAUDE_CODE_SIMPLE_SYSTEM_PROMPT=1` (shorter system prompt and tool descriptions): 19.8K -> 12.6K tokens per
    request. THOL test `claude-lean-v4` pending; a default only if the pass rate holds.
  - Unblocked by Claude Code 2.1.243+: B3 (`promptCacheTtl`, `subagentPromptCacheTtl`) and B4 (`PostModelSwitch`).
  - Now built into Claude Code, overlapping ours: idle compaction (2.1.299), `/skill-doctor` (2.1.261), cache-miss
    cause in `/cost` (2.1.260), a Concise output style (2.1.237).
  - To try: `skillListingMaxDescChars` for large skill listings, `CLAUDE_CODE_SUBAGENT_EFFORT`, a lower
    `BASH_MAX_OUTPUT_LENGTH`.

- **Privacy:** the README said "no network calls". The web search hook sends search queries to public engines and
  GitHub. The README now says so, and `LEAN_WEB_SEARCH=0` keeps Claude Code's own search.
- **MCP compaction** first dropped empty lists, but `"items": []` means "nothing found". It now keeps top-level fields
  and empty lists, and drops only nested null and "" values.
- **Python 3.8** (the minimum we support): `web_guard` used a 3.9-only argument; fixed.
- **Haiku 5.5 price:** `report` priced Haiku 5.5 at $0.10 / $0.50 per million tokens; Claude Code's own cost figures
  on THOL match $5 / $25. A Haiku development run of THOL cost more per run than Sonnet 4.6, so it was stopped after
  11 runs. Sonnet 4.6 stays the measuring model.
- **The plugin** was missing the MCP compaction hook; added.

---

## 6. Open questions

- What do 5-minute vs 1-hour cache writes cost on short tasks (Claude Code 2.1.242+)? (B3)
- Do the new hooks (read guard, MCP compaction, loop note, compaction instructions, rules) lower cost on THOL and our
  evals with the same pass rate? Built and live-tested, not yet cost-measured.
- What does the auto-mode safety check cost per tool call, and does it show in `modelUsage`? (L)
- What does one screenshot cost in tokens at today's sizes? (C6)
- Does compacting late (`CLAUDE_CODE_AUTO_COMPACT_WINDOW=700000`) save money on THOL's long tasks? (C8)
- How long does DuckDuckGo keep answering in a 40-search session before it throttles? (G3)
