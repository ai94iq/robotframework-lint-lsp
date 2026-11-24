"""Workspace index for document symbols, definition, references and hover.

Pure functions over buffer text so the LSP layer stays thin. Positions are
0-based lines and columns, as LSP sends them. A name resolves first through
the file's own resource imports, then to the indexed file nearest to it, so a
second checkout of the same project never wins over the imports.
"""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass
from urllib.parse import urlparse
from urllib.request import url2pathname

from .nav_model import (MAX_RESULTS, Definition, FileIndex, Location, Symbol, document_symbols, index_file, key,
                        VARIABLE_PREFIX, variable_at)

__all__ = ["Found", "Location", "Symbol", "WorkspaceIndex", "document_symbols"]

MAX_HOVER = 200
MAX_IMPORTED = 200
MAX_BYTES = 1_000_000


@dataclass(frozen=True)
class Found:
    name: str
    location: Location


def _read(uri: str) -> str | None:
    """A resource on disk that the index has not seen yet; None when unreadable or too big."""
    path = url2pathname(urlparse(uri).path)
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def _shared_prefix(first: str, second: str) -> int:
    return next((i for i, (a, b) in enumerate(zip(first, second)) if a != b), min(len(first), len(second)))


class WorkspaceIndex:
    """Keyword and variable definitions and keyword calls across every indexed file."""

    def __init__(self) -> None:
        self.files: dict[str, FileIndex] = {}

    def update(self, uri: str, text: str) -> None:
        self.files[uri] = index_file(uri, text)

    def lines(self, uri: str) -> list[str]:
        """Source lines, so the LSP layer can convert columns to the client's encoding."""
        index = self.files.get(uri)
        return index.lines if index else []

    def _name_at(self, uri: str, line: int, character: int) -> str | None:
        index = self.files.get(uri)
        if index is None:
            return None
        for loc, name in zip(index.calls, index.names):
            if loc.line == line and loc.start <= character <= loc.end:
                return name
        defined = next((k for k, d in index.definitions.items()
                        if d.location.line == line and d.location.start <= character <= d.location.end), None)
        if defined or line >= len(index.lines):
            return defined
        return variable_at(index.lines[line], character)

    def _load(self, uri: str) -> FileIndex | None:
        if uri not in self.files:
            text = _read(uri)
            if text is None:
                return None
            self.update(uri, text)
        return self.files[uri]

    def _imported(self, uri: str):
        """The file, then the resources it imports, breadth first, each once."""
        queue, seen = deque([uri]), {uri}
        while queue and len(seen) <= MAX_IMPORTED:
            index = self._load(queue.popleft())
            if index is None:
                continue
            yield index
            for target in index.imports:
                if target not in seen:
                    seen.add(target)
                    queue.append(target)

    def _lookup(self, uri: str, name: str) -> Definition | None:
        found = next((f.definitions[name] for f in self._imported(uri) if name in f.definitions), None)
        if found:
            return found
        nearest = sorted((u for u, f in self.files.items() if name in f.definitions),
                         key=lambda u: -_shared_prefix(u, uri))
        return self.files[nearest[0]].definitions[name] if nearest else None

    def _resolve(self, uri: str, line: int, character: int) -> Definition | None:
        name = self._name_at(uri, line, character)
        return self._lookup(uri, name) if name else None

    def definition(self, uri: str, line: int, character: int) -> Location | None:
        found = self._resolve(uri, line, character)
        return found.location if found else None

    def references(self, uri: str, line: int, character: int) -> list[Location]:
        """Calls whose own file resolves the name to the same definition."""
        name = self._name_at(uri, line, character)
        target = self._lookup(uri, name) if name else None
        if target is None:
            return []
        found = [loc for u, f in list(self.files.items()) if name in f.names
                 and self._lookup(u, name) is target
                 for loc, n in zip(f.calls, f.names) if n == name]
        return found[:MAX_RESULTS]

    def find(self, query: str) -> list[Found]:
        """Keywords whose name matches the query: exact, then prefix, then substring."""
        wanted = key(query)
        ranked = []
        for f in self.files.values():
            for name_key, d in f.definitions.items():
                if wanted in name_key and not name_key.startswith(VARIABLE_PREFIX):
                    rank = 0 if name_key == wanted else 1 if name_key.startswith(wanted) else 2
                    ranked.append((rank, d.name, Found(d.name, d.location)))
        return [found for _, _, found in sorted(ranked, key=lambda r: r[:2])][:MAX_RESULTS]

    def hover(self, uri: str, line: int, character: int) -> str | None:
        found = self._resolve(uri, line, character)
        if found is None:
            return None
        text = f"{found.signature}\n{found.doc}" if found.doc else found.signature
        return text[:MAX_HOVER]
