"""The project's own robocop select and ignore lists, read as data from its config files.

Only the select and ignore keys are read: a project config can also name Python rule
files (custom_rules), and the server and the hook never load those.
"""

from __future__ import annotations

import tomllib
from fnmatch import fnmatchcase
from pathlib import Path

PROJECT_MARKERS = (".git", "pyproject.toml", "robot.toml")
CONFIG_FILES = ("robocop.toml", "pyproject.toml")
OUR_RULES = "RFL*"


def project_root(path: Path) -> Path | None:
    """Nearest folder at or above path that holds a project marker."""
    return next((folder for folder in (path, *path.parents)
                 if any((folder / marker).exists() for marker in PROJECT_MARKERS)), None)


def rule_filter(path: Path) -> tuple[list[str], list[str]]:
    """Select and ignore lists of the config nearest to path, never above its project root."""
    root = project_root(path.parent)
    if root is None:
        return [], []
    for folder in (path.parent, *path.parent.parents):
        for name in CONFIG_FILES:
            lint = _lint_table(folder / name)
            if lint is not None:
                return _str_list(lint.get("select")), _str_list(lint.get("ignore"))
        if folder == root:
            break
    return [], []


def rule_active(rule_id: str, select: list[str], ignore: list[str]) -> bool:
    """Whether robocop would run rule_id under these lists; our own rules always stay selected."""
    selected = not select or any(fnmatchcase(rule_id, p) for p in [*select, OUR_RULES])
    return selected and not any(fnmatchcase(rule_id, p) for p in ignore)


def _lint_table(config: Path) -> dict | None:
    """The lint table of a config file; robocop.toml may skip the [tool.robocop] wrapper, as robocop allows."""
    if not config.is_file():
        return None
    try:
        data = tomllib.loads(config.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    tool = data.get("tool")
    section = tool.get("robocop") if isinstance(tool, dict) else None
    if not section and config.name == "robocop.toml":
        section = data
    lint = section.get("lint") if isinstance(section, dict) else None
    return lint if isinstance(lint, dict) else None


def _str_list(value: object) -> list[str]:
    return [str(v) for v in value] if isinstance(value, list) else []
