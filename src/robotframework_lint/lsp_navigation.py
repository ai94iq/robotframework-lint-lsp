"""LSP handlers for document symbols, definition, references and hover."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from lsprotocol import types

from .navigation import Location, WorkspaceIndex, document_symbols

# A huge checkout must not stall startup; files past the cap index when opened.
MAX_FILES = 2000
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "results"}
SUFFIXES = {".robot", ".resource"}
PROJECT_MARKERS = (".git", "pyproject.toml", "robot.toml")
# A generated or binary file posing as .robot must not fill memory; open files still lint.
MAX_BYTES = 1_000_000
SYMBOL_KIND = {"test": types.SymbolKind.Method, "keyword": types.SymbolKind.Function,
               "variable": types.SymbolKind.Variable}


def _robot_files(root: Path):
    """Prunes skipped dirs before descending and never follows links out of the tree."""
    stack = [root]
    while stack:
        try:
            entries = list(os.scandir(stack.pop()))
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir() and entry.name not in SKIP_DIRS:
                stack.append(Path(entry.path))
            elif entry.is_file() and Path(entry.name).suffix in SUFFIXES and entry.stat().st_size <= MAX_BYTES:
                yield Path(entry.path)


def project_root(path: Path) -> Path | None:
    """Nearest folder at or above path that holds a project marker."""
    return next((folder for folder in (path, *path.parents)
                 if any((folder / marker).exists() for marker in PROJECT_MARKERS)), None)


def scan_project_of(index: WorkspaceIndex, scanned: set[Path], uri: str) -> None:
    """Index the open file's project once, so a parent folder of many checkouts never fills the cap."""
    if not uri.startswith("file:"):
        return
    path = Path(url2pathname(urlparse(uri).path))
    root = project_root(path.parent) or path.parent
    if root not in scanned:
        scanned.add(root)
        _scan(index, root)


def scan_workspace(index: WorkspaceIndex, scanned: set[Path], root_uri: str | None) -> None:
    """Index the client's root only inside a project; a parent of many checkouts waits for opened files."""
    if not root_uri or not root_uri.startswith("file:"):
        return
    root = Path(url2pathname(urlparse(root_uri).path))
    if project_root(root) is not None:
        scanned.add(root)
        _scan(index, root)


def _scan(index: WorkspaceIndex, root: Path) -> None:
    for count, path in enumerate(_robot_files(root)):
        if count >= MAX_FILES:
            return
        try:
            index.update(path.as_uri(), path.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # one unparsable file must not stop the scan
            continue


def _range(line: int, start: int, end: int) -> types.Range:
    return types.Range(types.Position(line, start), types.Position(line, end))


def _location(ls, loc: Location) -> types.Location:
    """Index columns are code points; the client counts in the negotiated encoding."""
    codec = ls.workspace.position_codec
    client_range = codec.range_to_client_units(ls.index.lines(loc.uri), _range(loc.line, loc.start, loc.end))
    return types.Location(uri=loc.uri, range=client_range)


def _at(ls, params) -> tuple[str, int, int]:
    uri = params.text_document.uri
    position = ls.workspace.position_codec.position_from_client_units(ls.index.lines(uri), params.position)
    return uri, position.line, position.character


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
        found = ls.index.definition(*_at(ls, params))
        return _location(ls, found) if found else None

    @server.feature(types.TEXT_DOCUMENT_REFERENCES)
    def on_references(ls, params: types.ReferenceParams):
        found = ls.index.references(*_at(ls, params))
        return [_location(ls, loc) for loc in found]

    @server.feature(types.WORKSPACE_SYMBOL)
    def on_workspace_symbol(ls, params: types.WorkspaceSymbolParams):
        return [types.WorkspaceSymbol(name=f.name, kind=types.SymbolKind.Function, location=_location(ls, f.location))
                for f in ls.index.find(params.query)]

    @server.feature(types.TEXT_DOCUMENT_HOVER)
    def on_hover(ls, params: types.HoverParams):
        text = ls.index.hover(*_at(ls, params))
        if text is None:
            return None
        return types.Hover(contents=types.MarkupContent(kind=types.MarkupKind.PlainText, value=text))
