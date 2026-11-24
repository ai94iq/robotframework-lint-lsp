# Using robotframework-lint with coding agents

This guide sets up the language server and the auto-fix hook for each agent,
and says what the agent should do with the findings. Measured results are in
[benchmarks.html](benchmarks.html).

## What you get in each agent

| Agent | Diagnostics after edits | Auto-fix hook | Keyword navigation | Status |
|---|---|---|---|---|
| Claude Code | yes, pushed after Edit and Write | yes | yes, through the LSP tool | tested, 200+ runs |
| opencode | yes, through its `lsp` config | no | no | config documented, not working in our test |
| Crush | yes, through its `lsp` config | no | no | config documented, not tested |
| Codex CLI | only through an LSP to MCP bridge | no | through the bridge | not tested |
| GLM coding plan | depends on the host CLI | depends on the host CLI | depends on the host CLI | see GLM below |

The hook is a Claude Code plugin feature. In other agents, run the fixes
yourself or from the agent's own hook system (see "Auto-fix without Claude
Code").

## Install

```bash
python -m venv .venv
.venv/Scripts/python -m pip install robotframework-lint-lsp==1.2.0   # Windows
.venv/bin/python -m pip install robotframework-lint-lsp==1.2.0       # Linux, macOS
```

This installs two commands. Put the venv's `Scripts` or `bin` folder on
`PATH` before you start the agent.

| Command | What it does |
|---|---|
| `robotframework-lint-lsp` | stdio language server, language id `robotframework` |
| `robotframework-lint-autofix` | PostToolUse hook: reads the hook JSON on stdin, fixes the edited file |

## Claude Code

This repo is a Claude Code plugin: `.claude-plugin/plugin.json`, `.lsp.json`
for the server and `hooks/hooks.json` for the auto-fix hook. The step-by-step
install with expected results is in the README:
[If you are an agent installing this](../README.md#if-you-are-an-agent-installing-this).

Try it for one session:

```bash
claude --plugin-dir /path/to/robotframework-lint
```

Keep it: add the repo to a plugin marketplace you control, then

```bash
claude plugin install robotframework-lint-lsp@<marketplace> --scope user
```

`.lsp.json` maps `.robot` and `.resource` to the server and passes the
settings in `initializationOptions`:

```json
{
  "robotframework": {
    "command": "robotframework-lint-lsp",
    "extensionToLanguage": { ".robot": "robotframework", ".resource": "robotframework" },
    "initializationOptions": { "maxDiagnostics": 20, "minSeverity": "warning", "select": [], "ignore": [] }
  }
}
```

Check that both parts run:

```bash
claude --plugin-dir /path/to/robotframework-lint --debug-file debug.log -p "add a test to tests/login.robot"
grep -E "LSP Diagnostics: Delivering|robotframework-lint-autofix" debug.log
```

You should see `Delivering N file(s) with M diagnostic(s)` and
`PostToolUse:Edit [robotframework-lint-autofix] ... finished with status 0`.

Known behaviour of Claude Code's LSP client, as of November 2026:

- Diagnostics are pushed, not awaited: they can arrive on the next tool result
  rather than the edit that caused them.
- A finding identical to one already delivered is not shown again.
- It never asks the server for code actions, so fixes must come from the hook
  or the message text.

## opencode

Add an `lsp` block to `opencode.json` ([opencode LSP docs](https://opencode.ai/docs/lsp/)):

```json
{
  "lsp": {
    "robotframework": {
      "command": ["robotframework-lint-lsp"],
      "extensions": [".robot", ".resource"],
      "initialization": { "maxDiagnostics": 20, "minSeverity": "warning" }
    }
  }
}
```

opencode calls the options `initialization`, not `initializationOptions`.
In our test the server was listed as enabled but opencode never started it,
and `opencode --print-logs` showed no spawn. Check the logs before relying
on it.

## Crush

Add the server with the `crushrc` form from the [Crush README](https://github.com/charmbracelet/crush):

```text
lsp add robotframework --command "robotframework-lint-lsp"
```

The older `crush.json` `lsp` key still works but is deprecated. We have not
confirmed how Crush maps `.robot` and `.resource` to the server or passes
init options; check Crush's current docs.

## Codex CLI

Codex has no built-in LSP client ([openai/codex#8745](https://github.com/openai/codex/issues/8745)
is open). Use an LSP to MCP bridge, such as
[lsp-mcp](https://github.com/CesarPetrescu/lsp-mcp), and register the bridge
in `~/.codex/config.toml`:

```toml
[mcp_servers.lsp_bridge]
command = "/absolute/path/to/lsp-mcp"
args = []  # the bridge's stdio arguments, from its README
```

Then register `robotframework-lint-lsp` in the bridge's own config. We have
not tested this path. Through a bridge the agent pulls diagnostics with a
tool call, so it behaves like the robocop MCP arm in the benchmarks: more
turns than a pushed LSP.

## GLM coding plan

GLM is a model plan, not an agent. Z.ai lists the tools it runs in, including
Claude Code, opencode, Crush, Kilo Code, Cline and Codex
([Z.ai tool list](https://docs.z.ai/devpack/tool/others)). Set up the LSP in
the host tool as above. With Claude Code on GLM, the plugin, LSP and hook work
the same way; only the model endpoint changes.

## Auto-fix without Claude Code

Run the same safe fixes the hook runs, after the agent edits a file:

```bash
robocop format --select ReplaceWithVAR path/to/file.robot
robocop check --fix --select DEPR03 --select DEPR04 --select DEPR07 --select DEPR08 \
  --select DEPR09 --select DEPR10 --select DEPR11 --select MISC04 --select MISC09 \
  --select VAR01 path/to/file.robot
```

Or call `robotframework-lint-autofix` from any hook system that sends
`{"tool_input": {"file_path": "..."}}` on stdin.

## What the agent should do with findings

Put these lines in the project's agent instructions (`CLAUDE.md`,
`AGENTS.md` or the tool's equivalent):

```markdown
- Robot Framework files are linted after each edit. Fix every reported
  finding before you finish; do not add `# robocop: off` or disable rules.
- A finding that ends with "fix all: <command>" can be fixed by running that
  command on the file.
- An "overflow N more findings" line means the list was cut: fix the shown
  findings, then save to see the rest.
- Run `robot --dryrun` and the suite after lint fixes; a lint fix must not
  change test results.
```

## Diagnostic format

Each finding is one line, at most 120 characters:

```text
DEPR05 Set Test Variable used instead of VAR; fix all: robocop format --select ReplaceWithVAR <file>
LEN03 Keyword 'Open Login Page' has too many keywords inside (12/10)
overflow 7 more findings not shown (maxDiagnostics 20)
```

| Setting | Default | Meaning |
|---|---|---|
| `maxDiagnostics` | 20 | findings per file, then one `overflow` line |
| `minSeverity` | `warning` | `info`, `warning` or `error`; fixable Info rules are raised to warning |
| `select`, `ignore` | `[]` | robocop rule ids to keep or drop; an empty `select` keeps all rules |
| `groupFindings` | `false` | one diagnostic per rule; off because it left more findings unfixed |
