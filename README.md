# robotframework-lint-lsp

Robot Framework lint for coding agents. The agent edits a `.robot` file.
Safe fixes are applied right after the edit. Only the findings left come
back to the agent, one short line each.

[![PyPI](https://img.shields.io/pypi/v/robotframework-lint-lsp)](https://pypi.org/project/robotframework-lint-lsp/)
[![Python](https://img.shields.io/pypi/pyversions/robotframework-lint-lsp)](https://pypi.org/project/robotframework-lint-lsp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

- Language server (`robotframework-lint-lsp`): robocop findings plus the
  RFL rules below, sent after every edit. Each finding is one short line.
  It also gives definition, references, hover and workspace symbols for
  your own keywords.
- Auto-fix hook (`robotframework-lint-autofix`): after each Edit or Write
  it applies robocop's safe fixes (`VAR` syntax, inline `IF`, one
  assignment style). The agent spends no turns on them.
- Rule pack: six robocop rules from the Robot Framework 7.5 release notes
  that robocop doesn't check yet.

## Contents

- [Does it help?](#does-it-help)
- [Install](#install)
- [What the agent gets](#what-the-agent-gets)
- [Settings](#settings)
- [Rules](#rules)
- [Other agents and editors](#other-agents-and-editors)
- [Development](#development)

## Does it help?

Measured on one task (write two suites with keywords, then run them),
robocop 9.4.0 default findings left in the final files:

| Model | No lint | robocop MCP | This plugin |
|---|---|---|---|
| Haiku (25 runs per arm) | 18.5 | 13.2 | 4.7 |
| Sonnet (3 runs) | 12.0 | -- | 2.0 |
| Opus (3 runs) | 11.0 | -- | 0 |

On Haiku and Sonnet it costs about 10 percent more than no lint. It costs
less than the robocop MCP on all three models. Every run, version and chart:
[benchmarks](https://ai94iq.github.io/robotframework-lint-lsp/benchmarks.html)
([source](docs/benchmarks)).

## Install

Needs Python 3.10 or later and Claude Code 2.1.275 or later.

1. Install the package where your agent can run it:

   ```bash
   pip install robotframework-lint-lsp
   ```

   It pins robotframework 7.5.1, robotframework-robocop 9.4.0 and
   pygls 2.1.1. To keep those pins apart, install it in a venv on PATH.

2. Add the plugin in Claude Code:

   ```text
   /plugin install robotframework-lint-lsp --marketplace ai94iq/robotframework-lint-lsp
   ```

3. Restart Claude Code. Edit any `.robot` or `.resource` file. The
   findings come back with the edit result.

To check it works, run `claude --debug-file debug.log`, then
`grep "LSP Diagnostics: Delivering" debug.log`.

Lint on the command line, without the agent:

```bash
robocop check --custom-rules robotframework_lint path/to/tests
```

`robocop list rules` has no `--custom-rules` flag. To list the RFL rules,
put `custom_rules = ["robotframework_lint"]` under `[tool.robocop.lint]`
in a config file and run `robocop list rules --config <file>`.

## What the agent gets

| Feature | Behaviour |
|---|---|
| Diagnostics | On open, save and change (debounced 0.4 s). One line per finding, `RULEID message`, at most 120 characters. At most 20 per file, then one line saying how many were cut. Warnings and errors only. |
| Fix hints | A finding robocop can fix ends with `fix all: <command>`; fixable Info rules are raised to Warning so the agent sees them. |
| Auto-fix | The PostToolUse hook runs robocop's safe fixes on the edited file in an isolated temp copy, keeps your line endings, and never overwrites a newer edit. |
| Navigation | Definition and references matched the way Robot matches names (`say_hello` finds `Say Hello`); hover shows the signature and first doc line; workspace symbols rank exact, then prefix, then substring. At most 50 results. |

On start the server indexes up to 2000 `.robot` and `.resource` files
under the workspace root, skipping `.git`, `.venv`, `node_modules`,
`results`, links and files over 1 MB. Library keywords such as `Log` are
not indexed.

## Settings

Set them in `initializationOptions` of your `.lsp.json`:

| Option | Default | Meaning |
|---|---|---|
| `maxDiagnostics` | 20 | Findings per file before the overflow line |
| `minSeverity` | `warning` | `info`, `warning` or `error` |
| `select` | all | Rule IDs to report only |
| `ignore` | none | Rule IDs to drop |
| `groupFindings` | off | One line per rule with its line numbers |
| `robotcodeCommand` | off | Command list for `robotcode` in your project venv, for example `["D:/proj/.venv/Scripts/robotcode"]`. On save it adds up to 5 errors robocop cannot see: unresolved keywords, variables and imports |

`robotcodeCommand` runs on the saved file in your workspace, not a temp
copy, and robotcode imports your project's libraries to resolve them. Set
it only for projects whose code you trust. Point it at the project's own
venv: a venv without the project's libraries reports false import errors.

## Rules

| ID | Name | Source |
|---|---|---|
| RFL001 | for-in-zip-without-mode (auto-fix adds `mode=SHORTEST`) | [RF 7.0](https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.0.rst) |
| RFL002 | deprecated-standard-library (Telnet) | [RF 7.5](https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst) |
| RFL003 | deprecated-tag-pattern (`XORY`, `&`) | [RF 7.5](https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst) |
| RFL004 | deprecated-translation (French `Unités de test`, Finnish `Tagit`) | [RF 7.5](https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst) |
| RFL005 | doc-tags-without-empty-row (`Tags:` in keyword docs) | [RF 7.5](https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst) |
| RFL006 | deprecated-argument-name (`list_=`, `time_=`) | [RF 7.5](https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst) |

RFL003 asks Robot Framework's own `TagPatterns`, so it reports exactly what
RF 7.5.1 warns about, including all-caps tags such as `-DONOTX` that RF
reads as `DO NOT X`. RFL004 reports a term only when RF parsed it as a
header or setting, that is, in a French or Finnish file.

## Other agents and editors

Setup for opencode, Crush, Codex, GLM and any LSP client, and how to call
the hook from other hook systems: [docs/agents.md](docs/agents.md).

## Development

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"   # Windows: .venv/Scripts/python
.venv/bin/python -m pytest
```

Releases publish to PyPI from a GitHub release through trusted publishing
(`.github/workflows/release.yml`).

## License

MIT
