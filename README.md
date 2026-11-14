# robotframework-lint

Extra [Robocop](https://github.com/MarketSquare/robotframework-robocop) rules
for Robot Framework 7.5. When Robocop and the Robot Framework docs disagree,
these rules follow Robot Framework.

## Install

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"   # Windows
.venv/bin/python -m pip install -e ".[dev]"       # Linux, macOS
```

Pinned: robotframework 7.5.1, robotframework-robocop 9.4.0, pytest 9.2.0.

## Run

```bash
robocop check --custom-rules robotframework_lint path/to/tests
```

The installed package registers the `robotframework_lint` Robocop plugin, so
the rules load by plugin name, no path needed. Run only these rules with
`--select RFL001 --select RFL002`.

## Rules

| ID | Name | Source |
|---|---|---|
| RFL001 | for-in-zip-without-mode | [RF 7.0 release notes](https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.0.rst) |
| RFL002 | deprecated-standard-library (Telnet) | [RF 7.5 release notes](https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst) |
| RFL003 | deprecated-tag-pattern (`XORY`, `&`) | [RF 7.5 release notes](https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst) |
| RFL004 | deprecated-translation (French `Unités de test`, Finnish `Tagit`) | [RF 7.5 release notes](https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst) |
| RFL005 | doc-tags-without-empty-row (`Tags:` in keyword docs) | [RF 7.5 release notes](https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst) |
| RFL006 | deprecated-argument-name (`list_=`, `time_=`) | [RF 7.5 release notes](https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst) |

RFL003 asks Robot Framework's own `TagPatterns` whether a pattern is deprecated,
so it reports exactly what RF 7.5.1 warns about. That includes all-caps tags
holding an operator word, such as `-DONOTX` or `-ORANGE`: RF reads them as
`DO NOT X` and `OR ANGE`. Write such tags in lower case.

RFL004 reads the deprecated terms from Robot Framework's own language
definitions. It reports a term only when RF parsed it as a header or setting,
that is, when the file's language is French or Finnish (`language: fr` or
`language: fi` in the file, or `--language`).

## LSP server (Claude Code and other agents)

`robotframework-lint-lsp` is a stdio language server. It lints the open
buffer in process with the robocop defaults plus these rules, on open, save
and change (debounced 0.4 s). Output is kept small for AI agents:

- one line per finding: `RULEID message`, at most 120 characters
- at most 20 findings per file (`maxDiagnostics`)
- warnings and errors only by default (`minSeverity`: info, warning, error)
- identical findings on one line reported once; no related information

Settings go in `initializationOptions`: `maxDiagnostics`, `minSeverity`,
`select`, `ignore`. For Claude Code, copy `.lsp.json` from this repo into
your plugin; it maps `.robot` and `.resource` to `robotframework`.

## Tests

```bash
python -m pytest
```

## License

MIT
