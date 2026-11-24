"""PostToolUse hook: apply safe robocop fixes to a Robot file right after an agent edits it.

A/B runs showed agents read "fix all: <command>" hints but never ran them, so the
fixable findings stayed. Fixing here costs the agent no turns. Silent by design:
the LSP push reports whatever is left.
"""

from __future__ import annotations

import difflib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from .hints import FIX_COMMANDS
from .project_config import rule_active, rule_filter

ROBOT_SUFFIXES = {".robot", ".resource"}
# Two robocop runs must finish inside the hook's 120 s budget.
TIMEOUT_S = 50


def edited_ranges(text: str, tool_input: dict) -> list[tuple[int, int]] | None:
    """Line ranges an Edit or MultiEdit wrote; None for a Write, which owns the whole file."""
    if "new_string" in tool_input:
        written = [tool_input["new_string"]]
    elif "edits" in tool_input:
        written = [edit.get("new_string", "") for edit in tool_input["edits"]]
    else:
        return None
    text = text.replace("\r\n", "\n")
    ranges = []
    for block in written:
        block = block.replace("\r\n", "\n")
        at = text.find(block) if block else -1
        if at >= 0:
            start = text.count("\n", 0, at)
            ranges.append((start, start + block.count("\n") + 1))
    return ranges


def keep_edited_hunks(original: str, fixed: str, ranges: list[tuple[int, int]]) -> str:
    before = original.splitlines(keepends=True)
    after = fixed.splitlines(keepends=True)
    kept = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, before, after, autojunk=False).get_opcodes():
        inside = any(i1 < end and max(i2, i1 + 1) > start for start, end in ranges)
        kept += after[j1:j2] if tag != "equal" and inside else before[i1:i2]
    return "".join(kept)


def fix_runs(path: Path) -> list[list[str]]:
    """Robocop argument lists for the fixes the file's folder keeps; an empty select would fix every rule."""
    active = [rule for rule in FIX_COMMANDS if rule_active(rule, *rule_filter(path))]
    selects = [arg for rule in active if FIX_COMMANDS[rule].startswith("robocop check") for arg in ("--select", rule)]
    runs = []
    if any(FIX_COMMANDS[rule].startswith("robocop format") for rule in active):
        runs.append(["format", "--select", "ReplaceWithVAR", "--silent"])
    if selects:
        runs.append(["check", "--fix", "--custom-rules", "robotframework_lint", *selects])
    return runs


def fix_file(path: Path, ranges: list[tuple[int, int]] | None = None) -> None:
    # -I: the hook runs inside the edited repo, which must not shadow robocop with its own module.
    robocop = [sys.executable, "-I", "-m", "robocop"]
    runs = fix_runs(path)
    if not runs:
        return
    original = path.read_text(encoding="utf-8", newline="")
    # A temp copy keeps robocop from reading the repo's config, which can name Python rule files.
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / f"buffer{path.suffix}"
        copy.write_text(original, encoding="utf-8", newline="")
        # TMPDIR can sit under a folder with its own robocop config; an explicit empty one wins.
        config = Path(tmp) / "robocop.toml"
        config.write_text("", encoding="utf-8")
        # Argument lists, never a shell: the path comes from the hook payload.
        for args in runs:
            subprocess.run([*robocop, *args, "--config", str(config), "--root", tmp, "--", str(copy)], cwd=tmp,
                           capture_output=True, timeout=TIMEOUT_S, check=False)
        fixed = copy.read_text(encoding="utf-8")  # robocop writes the OS line ending
    if "\r\n" in original:
        fixed = fixed.replace("\n", "\r\n")
    if ranges is not None:
        fixed = keep_edited_hunks(original, fixed, ranges)
    # The agent may have written again while robocop ran; never overwrite the newer text.
    if fixed != original and path.read_text(encoding="utf-8", newline="") == original:
        path.write_text(fixed, encoding="utf-8", newline="")


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        tool_input = payload["tool_input"]
        path = Path(tool_input["file_path"])
    except (ValueError, KeyError, TypeError):
        return 0
    if path.suffix.lower() in ROBOT_SUFFIXES and path.is_file():
        try:
            ranges = edited_ranges(path.read_text(encoding="utf-8", newline=""), tool_input)
            if ranges != []:
                fix_file(path, ranges)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass  # a failed fix must never block the agent's edit
    return 0


if __name__ == "__main__":
    sys.exit(main())
