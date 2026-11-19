# Contributing

Small, measured changes win here. The project's promise is that it saves money and adds nothing to requests, so:

- **Zero dependencies.** Hooks and tools use only the Python 3.8+ standard library; the CLI uses only Node built-ins.
- **Hooks must never break a session.** Catch everything and exit 0. Anything a hook prints should go to the user
  (`systemMessage`), not to the model, unless the change adds tokens on purpose and says how many.
- **Claims need numbers.** A change that says it saves tokens comes with an eval run (`evals/`) or a before/after.

## Run the tests

```bash
npm test          # python3 -m unittest discover -s tests && node --test tests/cli.test.js
```

## Add a filter

Noisy commands live in `NOISY` in `hooks/squeeze_hook.py`; drop and keep patterns in `NOISE` and `SIGNAL` in
`tools/squeeze.py`. Add a test in `tests/test_hooks.py` with a real (trimmed) sample of the command's output that
shows the error lines survive.

## Release

Bump `version` in `package.json`, add a `CHANGELOG.md` section, merge, then push the tag `vX.Y.Z`.
