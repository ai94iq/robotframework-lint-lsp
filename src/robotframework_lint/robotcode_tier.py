"""Opt-in robotcode tier: findings robocop cannot see (unresolved keywords, variables, imports).

robotcode resolves imports from the file's real location with the project's own
Python, so unlike robocop it runs on the saved file in the workspace and imports
the project's libraries. That is why it is off unless robotcodeCommand is set.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from lsprotocol import types

MAX_FINDINGS = 5
MAX_MESSAGE = 120
TIMEOUT_S = 60  # a cold robotcode run measured 11.6 s on 40 files
ERROR = 1


def analyze(command: list[str], path: Path, root: Path) -> list[types.Diagnostic]:
    """Run robotcode on one saved file; return its errors as capped LSP diagnostics."""
    if not path.resolve().is_relative_to(root.resolve()):
        return []
    try:
        # Argument list, never a shell: the path comes from the client.
        result = subprocess.run([*command, "--format", "json", "analyze", "code", str(path)],
                                cwd=root, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                timeout=TIMEOUT_S, check=False)
        report = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return []
    findings = report.get("diagnostics", {}) if isinstance(report, dict) else {}
    errors = [f for found in findings.values() for f in found if f.get("severity") == ERROR]
    return [_to_lsp(f) for f in errors[:MAX_FINDINGS]]


def _to_lsp(finding: dict) -> types.Diagnostic:
    start, end = finding["range"]["start"], finding["range"]["end"]
    message = f"{finding.get('code', 'robotcode')} {finding.get('message', '')}"
    if len(message) > MAX_MESSAGE:
        message = message[: MAX_MESSAGE - 3] + "..."
    return types.Diagnostic(
        range=types.Range(types.Position(start["line"], start["character"]),
                          types.Position(end["line"], end["character"])),
        message=message,
        severity=types.DiagnosticSeverity.Error,
        code=finding.get("code"),
        source="robotcode",
    )
