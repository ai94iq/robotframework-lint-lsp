"""PostToolUse hook: apply safe robocop fixes to a Robot file right after an agent edits it.

A/B runs showed agents read "fix all: <command>" hints but never ran them, so the
fixable findings stayed. Fixing here costs the agent no turns. Silent by design:
the LSP push reports whatever is left.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .hints import FIX_COMMANDS

ROBOT_SUFFIXES = {".robot", ".resource"}
TIMEOUT_S = 60


def fix_file(path: Path) -> None:
    robocop = [sys.executable, "-m", "robocop"]
    check_rules = [rule for rule, cmd in FIX_COMMANDS.items() if cmd.startswith("robocop check")]
    selects = [arg for rule in check_rules for arg in ("--select", rule)]
    # Argument lists, never a shell: the path comes from the hook payload.
    for args in (["format", "--select", "ReplaceWithVAR", "--silent"], ["check", "--fix", *selects]):
        subprocess.run([*robocop, *args, "--", str(path)], capture_output=True, timeout=TIMEOUT_S, check=False)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        path = Path(payload["tool_input"]["file_path"])
    except (ValueError, KeyError, TypeError):
        return 0
    if path.suffix.lower() in ROBOT_SUFFIXES and path.is_file():
        try:
            fix_file(path)
        except (OSError, subprocess.TimeoutExpired):
            pass  # a failed fix must never block the agent's edit
    return 0


if __name__ == "__main__":
    sys.exit(main())
