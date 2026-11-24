"""Navigation through a resource import chain, from a parent folder of several projects."""

import shutil
import subprocess
import sys
from pathlib import Path

from robotframework_lint.navigation import WorkspaceIndex
from test_lsp_navigation import _frame, _read_result

CHAIN = (Path(__file__).parent / "samples" / "chain").resolve()
PROBE = CHAIN / "repo" / "probes" / "probe.robot"
CLIENT = (CHAIN / "repo" / "collections" / "x" / "x_api_client.resource").as_uri()
ON_GET_CONTRACT = {"line": 10, "character": 16}
ON_CONTRACT_VAR = {"line": 10, "character": 33}


def _probe_only() -> WorkspaceIndex:
    """Only the probe is indexed: imports must load from disk on demand."""
    index = WorkspaceIndex()
    index.update(PROBE.as_uri(), PROBE.read_text(encoding="utf-8"))
    return index


def _clone_first() -> WorkspaceIndex:
    """A second project defines the same keyword and is indexed first."""
    index = WorkspaceIndex()
    clone = CHAIN / "clone" / "client.resource"
    index.update(clone.as_uri(), clone.read_text(encoding="utf-8"))
    index.update(PROBE.as_uri(), PROBE.read_text(encoding="utf-8"))
    return index


def test_definition_follows_import_chain():
    location = _probe_only().definition(PROBE.as_uri(), **ON_GET_CONTRACT)
    assert (location.uri, location.line) == (CLIENT, 1)


def test_imported_definition_beats_other_project():
    location = _clone_first().definition(PROBE.as_uri(), **ON_GET_CONTRACT)
    assert location.uri == CLIENT


def test_hover_on_imported_keyword():
    text = _probe_only().hover(PROBE.as_uri(), **ON_GET_CONTRACT)
    assert text == "Get Contract(${id})\nFetches a contract by id."


def test_references_to_same_file_keyword():
    refs = _probe_only().references(PROBE.as_uri(), line=17, character=2)
    assert sorted(r.line for r in refs) == [11, 12, 13]


def test_definition_of_suite_variable():
    location = _probe_only().definition(PROBE.as_uri(), **ON_CONTRACT_VAR)
    assert (location.uri, location.line, location.start) == (PROBE.as_uri(), 5, 0)


def test_hover_on_suite_variable():
    assert _probe_only().hover(PROBE.as_uri(), **ON_CONTRACT_VAR) == "${CONTRACT}    C-100"


def _symbols_after_open(parent: Path, query: str) -> list:
    """Server rooted at a parent folder of two projects: open the probe, then search the workspace."""
    probe = parent / PROBE.relative_to(CHAIN)
    proc = subprocess.Popen([sys.executable, "-m", "robotframework_lint.lsp"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    opened = {"textDocument": {"uri": probe.as_uri(), "languageId": "robotframework", "version": 1,
                               "text": probe.read_text(encoding="utf-8")}}
    try:
        for message in ({"id": 0, "method": "initialize", "params": {"processId": None, "rootUri": parent.as_uri(),
                                                                      "capabilities": {}}},
                        {"method": "initialized", "params": {}},
                        {"method": "textDocument/didOpen", "params": opened},
                        {"id": 1, "method": "workspace/symbol", "params": {"query": query}}):
            proc.stdin.write(_frame({"jsonrpc": "2.0", **message}))
        proc.stdin.flush()
        return _read_result(proc.stdout, 1)
    finally:
        proc.kill()


def test_parent_root_indexes_open_files_project(tmp_path):
    parent = tmp_path / "chain"
    shutil.copytree(CHAIN, parent)
    symbols = _symbols_after_open(parent, "Get Contract")
    client = parent / "repo" / "collections" / "x" / "x_api_client.resource"
    assert [s["location"]["uri"] for s in symbols] == [client.as_uri()]
