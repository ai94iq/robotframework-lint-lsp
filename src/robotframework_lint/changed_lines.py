"""Lines of an open buffer that differ from the file's text at git HEAD.

Findings on the other lines were there before the agent's work, so the server ranks them
last and tags them "(old)". Git is read as data only: an argument list, no shell, a time
limit, and fsmonitor off so the repo's config cannot start a program.
"""

from __future__ import annotations

import difflib
import subprocess
from pathlib import Path

GIT_TIMEOUT_S = 5


def head_text(path: Path) -> str | None:
    """The file's text at HEAD; None when git, the repo or the tracked file is missing."""
    command = ["git", "-c", "core.fsmonitor=false", "-C", str(path.parent), "show", f"HEAD:./{path.name}"]
    try:
        shown = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, timeout=GIT_TIMEOUT_S,
                               check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if shown.returncode != 0:
        return None
    return shown.stdout.decode("utf-8", errors="replace")


def changed_lines(path: Path, text: str) -> set[int] | None:
    """0-based buffer lines added or edited since HEAD; a deletion marks the line after it."""
    committed = head_text(path)
    if committed is None:
        return None
    before = committed.replace("\r\n", "\n").splitlines()
    after = text.replace("\r\n", "\n").splitlines()
    changed: set[int] = set()
    for tag, _, _, j1, j2 in difflib.SequenceMatcher(None, before, after).get_opcodes():
        if tag != "equal":
            changed.update(range(j1, max(j2, j1 + 1)))
    return changed
