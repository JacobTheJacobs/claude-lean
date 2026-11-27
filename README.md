# Claude Lean

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/JacobTheJacobs/claude-lean/blob/master/LICENSE)
[![Dependencies: none](https://img.shields.io/badge/dependencies-none-brightgreen)](https://github.com/JacobTheJacobs/claude-lean/blob/master/install.sh)
[![Cost: ~20% cheaper](https://img.shields.io/badge/cost-~20%25%20cheaper-brightgreen)](#results)
[![SWE-bench Verified: 20/33, same as plain](https://img.shields.io/badge/SWE--bench%20Verified-20%2F33%20same%20as%20plain-brightgreen)](#results)
[![Time: -24%](https://img.shields.io/badge/time-%E2%88%9224%25-orange)](#results)

**Claude Code, ~20% cheaper and 24% faster. Same tasks solved.**

Claude Lean only turns off things you pay for and don't use.
No new instructions for Claude. No telemetry. One command.

```bash
npx claude-lean init
```

<img src="https://raw.githubusercontent.com/JacobTheJacobs/claude-lean/master/docs/demo.gif" alt="Terminal demo: the installer adds Claude Lean's settings; a 3-prompt chat sends 4 requests (~40K tokens) instead of 7 (~85K); SWE-bench Verified 20/33 solved like plain Claude Code in 103 instead of 135 minutes." width="820">

## Results

| Test | Result |
|------|--------|
| **SWE-bench Verified** (33 tasks, Sonnet 4.6) | Same 20 solved. 24% faster. |
| **THOL** (17 tasks × 3, local run) | 12% cheaper. |
| **3-prompt chat** | 7 requests / ~85K tokens → 4 requests / ~40K (−53%). Same answers. |

The benchmarks don't include the interactive background requests that Claude Lean turns off, so real interactive
savings are higher.

## What it turns off

| Feature | Effect | Measured |
|---------|--------|----------|
| Background requests | Next-prompt suggestions, session titles, recaps, idle check-ins | 7 → 4 requests |
| ListAgents | Removes a tool Claude almost never uses | ~500 tokens/request |
| Long skill descriptions | Caps descriptions at 200 chars (full skill still loads when used) | ~2,900 tokens/request |
| Persistent fast mode | `/fast` only lasts for the current session | Not measured (Anthropic pricing) |
| Cache rewrite warning | Warns before edits that invalidate the prompt cache | Warning only |

Optional flags:
- `--background-only`: only turn off background requests; nothing Claude sees changes
- `--pin`: disable auto-updates
- `--cache-1h`: force 1-hour cache (API keys only)

## Install / Uninstall

```bash
npx claude-lean init          # install (backs up settings, never overrides yours)
npx claude-lean uninstall     # remove everything it added
npx claude-lean doctor        # check the install
```

## Contributing

Issues and PRs welcome. A change that claims to save tokens needs a before/after measurement. See [CONTRIBUTING.md](https://github.com/JacobTheJacobs/claude-lean/blob/master/CONTRIBUTING.md).

## License

MIT
