# Claude Lean

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/JacobTheJacobs/claude-lean/blob/master/LICENSE)
[![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen)](https://github.com/JacobTheJacobs/claude-lean/blob/master/install.sh)
[![Cost: ~20% cheaper](https://img.shields.io/badge/cost-~20%25%20cheaper-brightgreen)](#benchmark)
[![SWE-bench Verified: 20/33, same as plain](https://img.shields.io/badge/SWE--bench%20Verified-20%2F33%20same%20as%20plain-brightgreen)](#benchmark)
[![Time: -24%](https://img.shields.io/badge/time-%E2%88%9224%25-orange)](#benchmark)

<img src="https://raw.githubusercontent.com/JacobTheJacobs/claude-lean/master/docs/demo.gif" alt="Terminal demo: the installer adds Claude Lean's settings; a 3-prompt chat sends 4 requests (~40K tokens) instead of 7 (~85K); SWE-bench Verified 20/33 solved like plain Claude Code in 103 instead of 135 minutes." width="820">

**Claude Code, about 20% cheaper and 24% faster. Same tasks solved.** No new instructions for Claude: Claude Lean only
switches off what you pay for and don't use. Every saving below was measured; features without a measured saving say so.

- **SWE-bench Verified:** 20 of 33 solved, same as plain Claude Code, in 24% less time.
- **Short chats:** half as much sent. A 3-prompt session went from 7 requests and ~85K tokens to 4 requests and ~40K
  (-53%), with identical answers.

### Benchmark

Real GitHub issues, graded by the official SWE-bench harness. 33 tasks, Sonnet 4.6, same prompt, one run per task.
Plain Claude Code and Claude Lean each solved 20.

Both solved the same 18 tasks plus one more each (plain: django-15973, Claude Lean: sphinx-7440); those two flip from run
to run either way. The same task can cost 2-5x more from one run to the next, so one run gives a rough cost figure. The
benchmark runs Claude without a chat window, so it doesn't include the background requests Claude Lean turns off in
interactive sessions.

| Feature | What it does | Measured |
|---|---|---|
| Background requests off | Turns off next-prompt suggestions, session titles, recaps, subagent progress summaries, idle compaction and idle check-ins. You lose the grey suggested-prompt text and auto tab titles. | 7 requests → 4; each suggestion re-sent the whole conversation |
| ListAgents off | Removes a tool Claude almost never needs | ~500 tokens off every request |
| Short skill descriptions | Caps each skill's description at 200 characters; skills still load in full when used | ~2,900 tokens off every request |
| Fast mode per session | `/fast` stays on only for the session you turn it on in. Without this, Claude Code saves it and every later session runs in fast mode, which is billed at a higher rate. Answers are the same. | Not measured: fast mode's higher price is Anthropic's list price |
| Cache warning | Warns you before Claude edits CLAUDE.md, AGENTS.md or a settings file, which re-writes the whole prompt cache | Warning only |
| `--pin` | Turns off auto-updates. An update changes the prompt, re-writes the cache, and can quietly change what you pay. | Opt-in |
| `--cache-1h` | 1-hour prompt cache. API keys only: a Claude subscription already gets 1 hour. 1-hour cache writes cost more. | Opt-in |

Measured and left out (no saving on SWE-bench or in 30 days of real sessions): output filter for test/build
commands, unchanged re-read note, MCP result compaction, blocking generated files. Also left out: free web search (Google via `agy`, or free engines). On a THOL web-research run agy's quota ran out after 22 searches and most free engines blocked repeated searches, so the paid search ran anyway.

```
npx claude-lean init [--pin] [--cache-1h]   # install (backs up ~/.claude/settings.json; never overrides your own values)
npx claude-lean uninstall                   # remove everything Claude Lean added
npx claude-lean doctor                      # check the install
```
