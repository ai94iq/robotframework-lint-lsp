"""PostToolUse hook: apply safe robocop fixes to a Robot file right after an agent edits it.

A/B runs showed agents read "fix all: <command>" hints but never ran them, so the
fixable findings stayed. Fixing here costs the agent no turns. Silent by design:
the LSP push reports whatever is left.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from .hints import FIX_COMMANDS

ROBOT_SUFFIXES = {".robot", ".resource"}
# Two robocop runs must finish inside the hook's 120 s budget.
TIMEOUT_S = 50


def fix_file(path: Path) -> None:
    # -I: the hook runs inside the edited repo, which must not shadow robocop with its own module.
    robocop = [sys.executable, "-I", "-m", "robocop"]
    check_rules = [rule for rule, cmd in FIX_COMMANDS.items() if cmd.startswith("robocop check")]
    selects = [arg for rule in check_rules for arg in ("--select", rule)]
    original = path.read_text(encoding="utf-8", newline="")
    # A temp copy keeps robocop from reading the repo's config, which can name Python rule files.
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / f"buffer{path.suffix}"
        copy.write_text(original, encoding="utf-8", newline="")
        # Argument lists, never a shell: the path comes from the hook payload.
        for args in (["format", "--select", "ReplaceWithVAR", "--silent"], ["check", "--fix", *selects]):
            subprocess.run([*robocop, *args, "--", str(copy)], cwd=tmp,
                           capture_output=True, timeout=TIMEOUT_S, check=False)
        fixed = copy.read_text(encoding="utf-8")  # robocop writes the OS line ending
    if "\r\n" in original:
        fixed = fixed.replace("\n", "\r\n")
    if fixed != original:
        path.write_text(fixed, encoding="utf-8", newline="")


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        path = Path(payload["tool_input"]["file_path"])
    except (ValueError, KeyError, TypeError):
        return 0
    if path.suffix.lower() in ROBOT_SUFFIXES and path.is_file():
        try:
            fix_file(path)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass  # a failed fix must never block the agent's edit
    return 0


if __name__ == "__main__":
    sys.exit(main())
