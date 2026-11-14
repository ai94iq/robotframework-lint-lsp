# CLAUDE.md

Guidance for coding agents working in this repository.

## Project overview

robotframework-lint-lsp is a Robot Framework linter built for coding agents.
It ships as one PyPI package (`robotframework-lint-lsp`, import name
`robotframework_lint`) and one Claude Code plugin from the same repo:

- a robocop rule pack (RFL001 to RFL006) for Robot Framework 7.5 guidance;
- `robotframework-lint-lsp`, a stdio language server (pygls) that pushes
  short diagnostics and answers navigation requests;
- `robotframework-lint-autofix`, a PostToolUse hook that applies robocop's
  safe fixes after each Edit or Write.

Pinned runtime: Python 3.10+, robotframework 7.5.1, robotframework-robocop
9.4.0, pygls 2.1.1 (`pyproject.toml`).

## Repository structure

```
.claude-plugin/plugin.json       # Plugin metadata (name, version)
.claude-plugin/marketplace.json  # Lets /plugin install from this repo
.lsp.json                        # LSP server config for Claude Code
hooks/hooks.json                 # PostToolUse hook, 120 s timeout
src/robotframework_lint/
  rules/                         # Robocop rules, one module per topic
  lsp.py                         # Server, diagnostics shaping, debounce
  lsp_navigation.py              # Workspace scan and navigation handlers
  navigation.py                  # In-memory keyword index
  hints.py                       # Rule id -> one-line fix command
  autofix.py                     # The PostToolUse hook
tests/                           # pytest; samples/ holds .robot fixtures
docs/                            # agents.md, benchmarks (GitHub Pages)
.github/workflows/release.yml    # Publish to PyPI on a GitHub release
```

## Commands

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Linux, macOS: .venv/bin/python
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m robocop check --custom-rules robotframework_lint path/to/tests
claude plugin validate .
```

## Adding a rule

1. Find the source first: a Robot Framework release note or user guide
   line. A rule without a cited source is not added.
2. Add a `Rule` subclass to the matching module in `rules/` (or a new
   module). Copy the shape of `rules/imports.py`: a docstring that quotes
   the source and shows incorrect and correct code, `name`, the next free
   `rule_id` (`RFL007`, ...), `message`, `severity`, `added_in_version`.
3. Add samples in `tests/samples/` (one that fires, one that does not) and
   a test that runs the real robocop CLI on them, like
   `tests/test_deprecated_library.py`. See it fail before the rule exists.
4. If robocop can fix it, add the fix command to `hints.py`.
5. Add the rule to the Rules table in `README.md`.

## Rules for changes

- Agent-facing output stays small: one line per finding, 120 characters
  at most, 20 findings per file by default. Changes to what the agent sees
  need an A/B run (`docs/benchmarks/`); the harness calls the paid
  `claude` CLI, so ask before running it.
- The hook and the server lint a temp copy, never the repo in place. Keep
  `-I`, the temp cwd, `--config`/`--root` in the temp dir and
  `ignore_file_config=True`: a repo or a folder above TMPDIR must not be
  able to load code or switch rules off.
- The hook must never block or fail an edit: it exits 0 and never writes
  over a newer edit.
- Dependencies are exact pins; bump them on purpose, with the full suite.
- Plain ASCII in code and docs, except real data such as translated
  Robot Framework terms.

## Releasing

1. Bump `version` in `pyproject.toml` and `.claude-plugin/plugin.json`.
2. Commit, then create a GitHub release `vX.Y.Z`. `release.yml` runs the
   tests, builds, and uploads to PyPI through trusted publishing.
