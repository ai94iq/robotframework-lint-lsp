---
name: robotframework-lint-lsp
description: Use when a .robot or .resource file is edited, when lint findings (RFL or robocop rule IDs) are missing or need reading, or when running the robocop lint CLI on Robot Framework tests.
---

# robotframework-lint-lsp

This plugin lints `.robot` and `.resource` files after each edit. The
language server pushes findings, and the auto-fix hook applies robocop's
safe fixes. Both need the `robotframework-lint-lsp` command on PATH.

## Reading the diagnostics

- Each finding is one line: `RULEID message`, at most 120 characters.
  Example: `DEPR05 Set Test Variable used instead of VAR; fix all: robocop format --select ReplaceWithVAR <file>`.
- At most 20 findings per file. After that, one line says how many were
  cut. Fix the shown ones, save again, and the rest appear.
- A line ending in `fix all: <command>` can be fixed by running that
  command on the file. Run it, then re-read the file.
- Only warnings and errors are shown. Info rules that robocop can fix are
  raised to warning.
- Findings are pushed, so one can arrive on the next tool result, not the
  edit that caused it. A finding already shown is not repeated.

## Fixing findings

- Fix every reported finding before you finish.
- Do not add `# robocop: off` or disable rules to hide a finding.
- After lint fixes, run `robot --dryrun` on the suite. A lint fix must not
  change test results.

## Linting from the command line

Run this when you need the findings for a path without an edit:

```bash
robocop check --custom-rules robotframework_lint path/to/tests
```

`robocop list rules` has no `--custom-rules` flag. To list the RFL rules,
set `custom_rules = ["robotframework_lint"]` under `[tool.robocop.lint]` in
a config file, then run `robocop list rules --config <file>`.

## Rules from this plugin

| ID | Finds |
|---|---|
| RFL001 | `for ... in zip` without `mode=` (auto-fix adds `mode=SHORTEST`) |
| RFL002 | Deprecated Telnet standard library (RF 7.5) |
| RFL003 | Deprecated tag patterns such as `XORY` and `&` (RF 7.5) |
| RFL004 | Deprecated French or Finnish translations of headers and settings (RF 7.5) |
| RFL005 | `Tags:` in keyword documentation without an empty row (RF 7.5) |
| RFL006 | Deprecated argument names such as `list_=` and `time_=` (RF 7.5) |

## Troubleshooting: no diagnostics

Check in this order and stop at the first failure:

1. PATH: run `which robotframework-lint-lsp` (Windows: `where
   robotframework-lint-lsp`). No path means the server is not installed or
   not on PATH. Install it with `uv tool install robotframework-lint-lsp==1.1.0`
   and fix PATH. Do not change PATH without the user's approval.
2. Plugin: run `claude plugin list`. The row for `robotframework-lint-lsp`
   must show `Status: enabled`. If not, run
   `claude plugin install robotframework-lint-lsp@robotframework-lint-lsp --scope user`.
3. Reload: ask the user to run `/reload-plugins` or restart Claude Code.
   An agent cannot do this itself. Wait for the user to confirm.

To confirm the server runs, the user can start a session with
`claude --debug-file debug.log` and search the log for
`LSP Diagnostics: Delivering`.

Install steps and expected results: the "If you are an agent installing
this" section of the repo README.
