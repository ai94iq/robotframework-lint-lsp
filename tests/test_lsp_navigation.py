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


def _ask(requests: list[tuple[str, dict]]) -> list:
    """Start the server on the nav folder, send requests in order, return results."""
    proc = subprocess.Popen([sys.executable, "-m", "robotframework_lint.lsp"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        proc.stdin.write(_frame({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
            "processId": None, "rootUri": NAV.as_uri(), "capabilities": {}}}))
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
