"""The workspace scan stops after a bounded walk, even in a tree with no Robot files."""

from robotframework_lint import lsp_navigation
from robotframework_lint.navigation import WorkspaceIndex


def _tree(root, dirs):
    for n in range(dirs):
        (root / f"d{n}").mkdir()
        (root / f"d{n}" / "notes.txt").write_text("x", encoding="utf-8")
    (root / f"d{dirs - 1}" / "late.robot").write_text("*** Test Cases ***\nT\n    No Operation\n", encoding="utf-8")


def test_walk_stops_at_entry_limit(tmp_path, monkeypatch):
    _tree(tmp_path, 30)
    monkeypatch.setattr(lsp_navigation, "MAX_ENTRIES", 10)
    assert list(lsp_navigation._robot_files(tmp_path)) == []


def test_walk_under_limit_finds_files(tmp_path):
    _tree(tmp_path, 30)
    assert [p.name for p in lsp_navigation._robot_files(tmp_path)] == ["late.robot"]


def test_scan_of_big_empty_tree_returns(tmp_path, monkeypatch):
    _tree(tmp_path, 30)
    monkeypatch.setattr(lsp_navigation, "MAX_ENTRIES", 10)
    index = WorkspaceIndex()
    lsp_navigation._scan(index, tmp_path)
    assert index.files == {}
