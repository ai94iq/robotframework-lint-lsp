# CLAUDE.md

Guidance for coding agents working in this repository.

## Project overview

robotframework-lint-lsp is a Robot Framework linter for coding agents. One PyPI package (`robotframework-lint-lsp`, import name `robotframework_lint`) and one Claude Code plugin come from this repo:

- a robocop rule pack (RFL001 to RFL007);
- `robotframework-lint-lsp`, a stdio language server (pygls) with short diagnostics and navigation;
- `robotframework-lint-autofix`, a PostToolUse hook that applies robocop's safe fixes after each Edit or Write.

## Repository map

| Path | Holds |
|---|---|
| `.claude-plugin/` | Plugin metadata and marketplace entry |
| `.lsp.json`, `hooks/hooks.json` | LSP config for Claude Code; PostToolUse hook (120 s timeout) |
| `src/robotframework_lint/rules/` | Robocop rules, one module per topic |
| `src/robotframework_lint/lsp.py`, `lsp_navigation.py`, `navigation.py` | Server, diagnostics, workspace scan, keyword index |
| `src/robotframework_lint/hints.py` | Rule id to one-line fix command |
| `src/robotframework_lint/autofix.py` | The PostToolUse hook |
| `tests/`, `tests/samples/` | pytest; `.robot` fixtures |
| `docs/` | `agents.md`, benchmarks (`docs/benchmarks/`), GitHub Pages |
| `.github/workflows/release.yml` | Publish to PyPI on a GitHub release |

## Commands

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Linux, macOS: .venv/bin/python
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m robocop check --custom-rules robotframework_lint path/to/tests
claude plugin validate .
```

## Adding a rule

1. Find the source first: a Robot Framework release note or user guide line. A rule without a cited source is not added.
2. Add a `Rule` subclass to the matching module in `rules/`, or a new module. Copy the shape of `rules/imports.py`: a docstring quoting the source with incorrect and correct code, `name`, the next free `rule_id` (`RFL008`, ...), `message`, `severity`, `added_in_version`.
3. Add samples in `tests/samples/` (one that fires, one that does not) and a test that runs the real robocop CLI on them, like `tests/test_deprecated_library.py`. See it fail before the rule exists.
4. If robocop can fix it, add the fix command to `hints.py`.
5. Add the rule to the Rules table in `README.md`.

## Rules for changes

- **Agent output.** One line per finding, 120 characters at most, 20 findings per file by default. Changes to what the agent sees need an A/B run (`docs/benchmarks/`). The harness calls the paid `claude` CLI: ask before running it.
- **Temp copy.** The hook and the server lint a temp copy, never the repo in place: keep `-I`, the temp cwd, `--config`/`--root` in the temp dir and `ignore_file_config=True`. Exception: the opt-in `robotcodeCommand` tier (`robotcode_tier.py`) runs on the saved file; it is off by default, uses an argument list and never a shell. The project's own lists come in as data only: `project_config.py` reads `select` and `ignore` from the nearest `robocop.toml` or `pyproject.toml` up to the project root, never `custom_rules`. The server reads the file's HEAD text with `git show` (`changed_lines.py`: argument list, 5 s limit, fsmonitor off) to tag findings on unchanged lines `(old)`.
- **Hook.** The hook never blocks or fails an edit: it exits 0 and never writes over a newer edit.
- **Pins.** Dependencies are exact pins; bump them on purpose, with the full suite.
- **ASCII.** Plain ASCII in code and docs, except real data such as translated Robot Framework terms.

## Releasing

1. Bump `version` in `pyproject.toml` and `.claude-plugin/plugin.json`.
2. Commit, then create a GitHub release `vX.Y.Z`. `release.yml` runs the tests, builds, and uploads to PyPI through trusted publishing.
