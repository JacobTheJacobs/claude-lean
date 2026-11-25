# Contributing

Small, measured changes win here. The project's promise is that it saves money without changing what Claude is told or shown, so:

- **Zero dependencies.** The installer and hook use only the Python 3.8+ standard library; the CLI uses only Node built-ins.
- **Hooks must never break a session.** Catch everything and exit 0. Anything a hook prints should go to the user
  (`systemMessage`), not to the model, unless the change adds tokens on purpose and says how many.
- **Claims need numbers.** A change that says it saves tokens comes with a before/after (requests logged through a
  proxy, or a benchmark run against plain Claude Code).
- **No behavior changes.** No instructions for Claude, no filtering or rewriting of tool output.

## Run the tests

```bash
npm test          # python3 -m unittest discover -s tests && node --test tests/cli.test.js
```

## Release

Bump `version` in `package.json`, add a `CHANGELOG.md` section, merge, push, run `npm publish`, then create the `vX.Y.Z` release on GitHub.
