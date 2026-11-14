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

## Tests

```bash
python -m pytest
```

## License

MIT
