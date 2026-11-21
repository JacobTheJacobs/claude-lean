---
description: Where your tokens and dollars went (--days N, --project NAME, --compare [DATE] for before vs after)
argument-hint: "[--days N] [--project NAME] [--compare [DATE]]"
allowed-tools: Bash(python3:*)
disable-model-invocation: true
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/tools/report.py" $ARGUMENTS`

Show the report above to the user verbatim. Do nothing else.
