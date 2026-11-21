#!/usr/bin/env python3
"""Claude Lean status line: what this session costs, as you work.

    Opus 5.5 | $1.84 | context 38% | cache 94% | 5h limit 22%

Cost is Claude Code's own list-price estimate (on a subscription it is usage, not a bill). Context is how full the
window is: every turn re-reads it. Cache is the share of the prompt read from cache (below ~80%, something keeps
rebuilding it). Installed by `claude-lean init` only when you have no status line of your own."""
import json
import sys


def get(d, *path):
    for k in path:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def main():
    try:
        d = json.load(sys.stdin)
    except ValueError:
        d = {}
    parts = [get(d, "model", "display_name") or get(d, "model", "id") or "Claude"]
    usd = get(d, "cost", "total_cost_usd")
    if isinstance(usd, (int, float)):
        parts.append(f"${usd:.2f}")
    ctx = get(d, "context_window", "used_percentage")
    if isinstance(ctx, (int, float)):
        parts.append(f"context {ctx:.0f}%")
    pc = get(d, "prompt_cache")              # field names vary by version: take the first numeric "hit" value
    hit = next((v for k, v in pc.items() if "hit" in k and isinstance(v, (int, float))), None) \
        if isinstance(pc, dict) else None
    if isinstance(hit, (int, float)):
        parts.append(f"cache {hit * 100 if hit <= 1 else hit:.0f}%")
    five = get(d, "rate_limits", "five_hour", "used_percentage")
    if isinstance(five, (int, float)):
        parts.append(f"5h limit {five:.0f}%")
    if get(d, "fast_mode"):
        parts.append("fast mode (premium price)")
    print(" | ".join(parts))


if __name__ == "__main__":
    main()
