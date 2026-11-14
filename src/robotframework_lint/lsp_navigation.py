"""LSP handlers for document symbols, definition, references and hover."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from lsprotocol import types

from .navigation import Location, WorkspaceIndex, document_symbols

# A huge checkout must not stall startup; files past the cap index when opened.
MAX_FILES = 2000
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "results"}
SUFFIXES = {".robot", ".resource"}
SYMBOL_KIND = {"test": types.SymbolKind.Method, "keyword": types.SymbolKind.Function,
               "variable": types.SymbolKind.Variable}


def _robot_files(root: Path):
    for path in root.rglob("*"):
        if path.suffix in SUFFIXES and not SKIP_DIRS.intersection(path.relative_to(root).parts):
            yield path


def scan_workspace(index: WorkspaceIndex, root_uri: str | None) -> None:
    if not root_uri or not root_uri.startswith("file:"):
        return
    root = Path(url2pathname(urlparse(root_uri).path))
    for count, path in enumerate(_robot_files(root)):
        if count >= MAX_FILES:
            return
        try:
            index.update(path.as_uri(), path.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # one unparsable file must not stop the scan
            continue


def _range(line: int, start: int, end: int) -> types.Range:
    return types.Range(types.Position(line, start), types.Position(line, end))


def _location(loc: Location) -> types.Location:
    return types.Location(uri=loc.uri, range=_range(loc.line, loc.start, loc.end))


def register(server) -> None:
    @server.feature(types.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def on_symbols(ls, params: types.DocumentSymbolParams):
        doc = ls.workspace.get_text_document(params.text_document.uri)
        suffix = ".resource" if doc.uri.endswith(".resource") else ".robot"
        return [types.DocumentSymbol(name=s.name, kind=SYMBOL_KIND[s.kind],
                                     range=types.Range(types.Position(s.line, 0), types.Position(s.end_line, 0)),
                                     selection_range=_range(s.line, 0, 0))
                for s in document_symbols(doc.source, suffix)]

    @server.feature(types.TEXT_DOCUMENT_DEFINITION)
    def on_definition(ls, params: types.DefinitionParams):
        found = ls.index.definition(params.text_document.uri, params.position.line, params.position.character)
        return _location(found) if found else None

    @server.feature(types.TEXT_DOCUMENT_REFERENCES)
    def on_references(ls, params: types.ReferenceParams):
        found = ls.index.references(params.text_document.uri, params.position.line, params.position.character)
        return [_location(loc) for loc in found]

    @server.feature(types.TEXT_DOCUMENT_HOVER)
    def on_hover(ls, params: types.HoverParams):
        text = ls.index.hover(params.text_document.uri, params.position.line, params.position.character)
        if text is None:
            return None
        return types.Hover(contents=types.MarkupContent(kind=types.MarkupKind.PlainText, value=text))
