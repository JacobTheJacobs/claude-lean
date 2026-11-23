# Claude Lean features

Everything Claude Lean does, with its off switch. Short version: [README](../README.md).

## Works with

| Agent | Command | What gets installed |
|---|---|---|
| Claude Code, plugin | `/plugin install lean@claude-lean` | 10 hooks, 2 skills, 4 `/lean:` commands. `/lean:slim on` adds the 7 settings. |
| Claude Code | `npx claude-lean init` | 11 hooks (12 with `LEAN_DAY_USD`), 2 skills, 7 settings, 4 deny rules and a status line in `~/.claude/settings.json` (backed up first) |
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

1. **Fixed overhead.** Six built-in Claude Code switches drop features most sessions never use, and a seventh stops each new session from re-writing ~6K tokens of cache. `lite` goes further for quick jobs.
2. **Noise.** A 400-test pytest run arrives as 13 lines. Every failure and summary stays; the full original is one command away.
3. **Focus.** Past 100K tokens a hook reminds you that `/clear` keeps an unrelated task focused, and "handoff" carries a short note across.

## Save tokens

- **Long-session guard.** Once a session passes 100K tokens (`LEAN_CLEAR_AT`), you get one line suggesting `/clear` before unrelated work. It's shown to you, never sent to the model, and stays silent on short sessions. It's about focus, not cost: back-to-back work is cheaper in one session.
- **Handoff.** Say "handoff" before `/clear`. Claude saves a short note (goal, progress, next steps), and the next session in that folder starts with it. Used once; expires after 12 hours. It's for continuity, not cost: writing the note is an extra request.
- **Slim.** On by default. Turns off Artifacts, Workflows, git instructions, background tasks, cron and the advisor tool, which cuts a typical setup from 49.5K to 24.9K tokens per request. It also turns off the per-session attribution header, so a new session or subagent reads the system prompt from cache instead of re-writing ~6K tokens (measured on Claude Code 2.1.330). Skip it with `--no-slim`.
- **Lite.** `npx claude-lean lite` starts Claude Code with just Read, Edit, Write, Bash, Grep, Glob, Agent and TodoWrite: no MCP servers, no skills. On a clean install that's 5.4K tokens before you type instead of 17.2K. `--keep-mcp` and `--keep-skills` bring those back.
- **Output filter.** For pytest, jest, npm, pip, cargo, go, docker, make and more. Drops progress bars, download chatter, passing tests and repeated lines; keeps errors, tracebacks and summaries. Dev servers and watchers are never touched.
- **Output budget.** About 280 tokens of standing rules at session start: smallest change, 1-3 line answers, edit instead of rewriting, do the reading yourself instead of fanning out to subagents, batch independent tool calls, text before screenshots. `--no-terse` keeps only the subagent, web and batching rules.
- **Web search budget.** Claude Code's WebSearch is a separate model request that re-sends the conversation as uncached input (~$0.07 a search on Sonnet). The hook serves searches itself from public search engines plus GitHub's repository search, skips pages an earlier search already showed, blocks repeated queries, and caps the paid searches at 15 per session (`LEAN_WEB_SEARCHES`; `LEAN_WEB_SEARCH=0` turns its own search off). It identifies itself honestly as `claude-lean`, which only GitHub's API and some engines accept; `LEAN_WEB_BROWSER=1` sends a browser's headers instead, which more engines answer (the THOL web result, $3.13 → $1.70, used that). On THOL's web research task the cap alone cut cost 36% with a higher score. `LEAN_WEB_AGY=1` adds Google results through Google's own Antigravity CLI (`agy`) when it's installed and signed in: legitimate, on your Antigravity quota, but slow (18-50 s a search).
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

## Stay safe

- **Nothing is lost.** Every trimmed output is saved, and `npx claude-lean get <id>` brings back the original. If Claude needs the originals from one tool three times, that tool's filter switches itself off.
- **Never in the way.** A failing hook exits quietly instead of breaking your session. The filter never approves a command, so your permission rules still apply.
- **Cache guard.** Warns you before a mid-session edit to CLAUDE.md or settings, which forces the whole prompt cache to be rebuilt.
- **Clean uninstall.** `npx claude-lean uninstall` removes exactly what it added, cache included.

**Does it work on your machine?** `report --compare` reads your own logs and compares fresh sessions before and after the install. The first request of a fresh session is pure fixed overhead (system prompt, tools, skills), so its change is exactly what Claude Lean removed; cost per request and per session also move with what you worked on. Resumed sessions and scratch runs are left out. Give it a few days of normal use.

## Agents in CI

Running Claude Code in GitHub Actions? Add Claude Lean before the step that starts it:

```yaml
- uses: JacobTheJacobs/claude-lean@master
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

## See the impact

```bash
npx claude-lean report --days 7       # where your money went: by model, project and session, with fixes
npx claude-lean report --compare      # your own fresh sessions, before vs after you installed Claude Lean
npx claude-lean stats                 # what the output filter saved, per tool
LEAN_DAY_USD=10 npx claude-lean init  # daily spending cap: warns at 80%, stops at 100%
```

## Habits that save the most

1. **Use `claude-lean lite` for quick jobs.** The measured 74%.
2. **Keep back-to-back work in one session.** Cached history is cheap; a new session pays to rebuild its cache. `/clear` when you switch to something unrelated.
3. **Leave CLAUDE.md, settings, model and effort alone mid-session.** Each change forces the whole cached prompt to be rebuilt.
4. **Ask for short answers.** Output tokens cost 5x input tokens.
5. **Check `npx claude-lean report --days 7` weekly.** It shows where the money actually went.

Sources: Anthropic's [cost guide](https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence) and [cookbook](https://platform.claude.com/cookbook/cost-optimization-cost-optimization).

## Security & privacy

- **Local, with one exception.** No telemetry, no account, nothing about you or your code is sent anywhere. The one network feature is web search: when Claude runs a WebSearch, the hook sends that search query (only the query) to public search engines (DuckDuckGo, Brave, Bing, Marginalia, Mojeek, Yahoo) and, for project queries, GitHub's API, instead of Claude Code's own search, which sends it to Anthropic. Set `LEAN_WEB_SEARCH=0` to keep Claude Code's search; the 15-search cap still applies.
- **Readable.** Plain Python and JavaScript using only the standard library. No binary, no dependencies. What's on GitHub is exactly what npm installs.
- **Your logs stay put.** `report` and `audit` read `~/.claude/projects` and print to your terminal.
- **What it stores.** The last 200 trimmed outputs, in `~/.cache/claude-lean/out` (readable only by you), and a handoff note until it's used or 12 hours pass. `uninstall` deletes both.
- **Your permissions still apply.** The filter can rewrite a command, but never approves one.
