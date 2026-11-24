"""LSP stdio roundtrip for symbols, definition, references and hover."""

import json
import subprocess
import sys
from pathlib import Path

NAV = (Path(__file__).parent / "samples" / "nav").resolve()
SUITE = (NAV / "suite.robot").as_uri()
RESOURCE = (NAV / "common.resource").as_uri()
ON_SAY_HELLO = {"textDocument": {"uri": SUITE}, "position": {"line": 7, "character": 6}}


def _frame(payload: dict) -> bytes:
    body = json.dumps(payload).encode()
    return f"Content-Length: {len(body)}\r\n\r\n".encode() + body


def _read_result(stream, request_id: int):
    while True:
        length = 0
        while (line := stream.readline().strip()):
            if line.lower().startswith(b"content-length"):
                length = int(line.split(b":")[1])
        message = json.loads(stream.read(length))
        if message.get("id") == request_id:
            return message["result"]


def _ask(requests: list[tuple[str, dict]], root: Path = NAV, encodings: list[str] | None = None) -> list:
    """Start the server on a folder, send requests in order, return results."""
    general = {"positionEncodings": encodings} if encodings else {}
    proc = subprocess.Popen([sys.executable, "-m", "robotframework_lint.lsp"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        proc.stdin.write(_frame({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
            "processId": None, "rootUri": root.as_uri(), "capabilities": {"general": general}}}))
        proc.stdin.write(_frame({"jsonrpc": "2.0", "method": "initialized", "params": {}}))
        for request_id, (method, params) in enumerate(requests, start=1):
            proc.stdin.write(_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}))
        proc.stdin.flush()
        return [_read_result(proc.stdout, i) for i in range(1, len(requests) + 1)]
    finally:
        proc.kill()


def test_navigation_over_stdio():
    symbols, definition, references, hover = _ask([
        ("textDocument/documentSymbol", {"textDocument": {"uri": RESOURCE}}),
        ("textDocument/definition", ON_SAY_HELLO),
        ("textDocument/references", {**ON_SAY_HELLO, "context": {"includeDeclaration": False}}),
        ("textDocument/hover", ON_SAY_HELLO),
    ])
    assert [s["name"] for s in symbols] == ["${GREETING}", "Say Hello", "Open Shop"]
    assert (definition["uri"], definition["range"]["start"]["line"]) == (RESOURCE, 5)
    assert sorted((r["uri"], r["range"]["start"]["line"]) for r in references) == sorted([(RESOURCE, 12), (SUITE, 7)])
    assert hover["contents"]["value"] == "Say Hello(${name})\nLogs a greeting to the given name."


def test_workspace_symbol_over_stdio():
    (found,) = _ask([("workspace/symbol", {"query": "open shop"})])
    assert [(s["name"], s["location"]["uri"]) for s in found] == [("Open Shop", RESOURCE)]


UTF = (Path(__file__).parent / "samples" / "nav_utf").resolve()
UTF_URI = (UTF / "k.resource").as_uri()


def _call_site(encoding: str, column: int) -> tuple[int, int]:
    on_call = {"textDocument": {"uri": UTF_URI}, "position": {"line": 5, "character": column + 1}}
    definition, refs = _ask([("textDocument/definition", on_call),
                             ("textDocument/references", {**on_call, "context": {"includeDeclaration": False}})],
                            root=UTF, encodings=[encoding])
    return definition["range"]["start"]["line"], refs[0]["range"]["start"]["character"]


def test_utf8_columns_count_bytes():
    # "Say Hello" starts after ${ä😀}= : 14 code points, 18 utf-8 bytes
    assert _call_site("utf-8", 18) == (1, 18)


def test_utf16_columns_count_code_units():
    assert _call_site("utf-16", 15) == (1, 15)


def test_scan_skips_ignored_dirs_and_huge_files(tmp_path, monkeypatch):
    from robotframework_lint import lsp_navigation
    from robotframework_lint.navigation import WorkspaceIndex

    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.robot").write_text("*** Keywords ***\nHidden\n    No Operation\n")
    (tmp_path / "big.robot").write_text("*** Keywords ***\nBig\n    No Operation\n" + "#" * 2000)
    (tmp_path / "ok.robot").write_text("*** Keywords ***\nShown\n    No Operation\n")
    (tmp_path / "robot.toml").write_text("")
    monkeypatch.setattr(lsp_navigation, "MAX_BYTES", 1000)
    visited = []
    real = lsp_navigation.os.scandir
    monkeypatch.setattr(lsp_navigation.os, "scandir", lambda p: visited.append(Path(p).name) or real(p))
    index = WorkspaceIndex()
    lsp_navigation.scan_workspace(index, set(), tmp_path.as_uri())
    assert "node_modules" not in visited
    assert index.find("Shown") and not index.find("Big") and not index.find("Hidden")
