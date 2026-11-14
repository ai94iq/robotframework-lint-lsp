""".lsp.json matches Claude Code's strict lspServers schema."""

import json
from pathlib import Path

LSP_JSON = Path(__file__).parent.parent / ".lsp.json"
# Claude Code rejects the whole file on any key outside this set.
ALLOWED = {"command", "extensionToLanguage", "args", "transport", "env", "initializationOptions", "settings",
           "workspaceFolder", "startupTimeout", "shutdownTimeout", "requestTimeout", "restartOnCrash",
           "maxRestarts", "diagnostics"}


def test_only_known_keys():
    (server,) = json.loads(LSP_JSON.read_text(encoding="utf-8")).values()
    assert set(server) <= ALLOWED


def test_restart_and_startup_limits_set():
    (server,) = json.loads(LSP_JSON.read_text(encoding="utf-8")).values()
    assert server["restartOnCrash"] is True
    assert server["maxRestarts"] == 3
    assert server["startupTimeout"] == 30000
