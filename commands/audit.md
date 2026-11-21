---
description: Skills and MCP servers you load on every request but never use (--days N; --disable-unused, --disable NAME, --restore)
argument-hint: "[--days N] [--disable-unused | --disable NAME.. | --restore [NAME..]]"
allowed-tools: Bash(python3:*)
disable-model-invocation: true
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/tools/audit.py" $ARGUMENTS`

Show the output above to the user verbatim. Do nothing else.
