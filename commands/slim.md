---
description: Turn slim on or off (drops ~24K unused tokens from every request; edits ~/.claude/settings.json, backup first)
argument-hint: "[on|off]"
allowed-tools: Bash(python3:*)
disable-model-invocation: true
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/tools/slim.py" $ARGUMENTS`

Show the output above to the user verbatim. If it changed the settings, add one line: it applies to new Claude Code sessions, and `/lean:slim off` undoes it. Do nothing else.
