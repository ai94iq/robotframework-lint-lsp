"""Workspace index for document symbols, definition, references and hover.

Pure functions over buffer text so the LSP layer stays thin. Positions are
0-based lines and columns, as LSP sends them.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from robot.api import Token, get_model, get_resource_model
from robot.parsing.model.blocks import Keyword, TestCase
from robot.parsing.model.statements import Arguments, Documentation, Variable
from robot.utils import normalize

MAX_HOVER = 200
MAX_RESULTS = 50
# Fixture settings name a keyword in a NAME token instead of a KEYWORD token.
FIXTURES = {Token.SETUP, Token.TEARDOWN, Token.SUITE_SETUP, Token.SUITE_TEARDOWN,
            Token.TEST_SETUP, Token.TEST_TEARDOWN}


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    line: int
    end_line: int


@dataclass(frozen=True)
class Location:
    uri: str
    line: int
    start: int
    end: int


@dataclass(frozen=True)
class Found:
    name: str
    location: Location


@dataclass
class _Definition:
    name: str
    location: Location
    signature: str
    doc: str


def _key(name: str) -> str:
    return normalize(name, ignore="_")


def _parse(text: str, suffix: str):
    parser = get_resource_model if suffix == ".resource" else get_model
    return parser(io.StringIO(text))


def _walk(node):
    yield node
    for child in getattr(node, "body", []) + getattr(node, "sections", []):
        yield from _walk(child)


def document_symbols(text: str, suffix: str) -> list[Symbol]:
    """Tests, keywords and variables in file order."""
    symbols = []
    for node in _walk(_parse(text, suffix)):
        if isinstance(node, (TestCase, Keyword)):
            kind = "test" if isinstance(node, TestCase) else "keyword"
            symbols.append(Symbol(node.name, kind, node.lineno - 1, node.end_lineno - 1))
        elif isinstance(node, Variable) and node.name:
            symbols.append(Symbol(node.name, "variable", node.lineno - 1, node.lineno - 1))
    return symbols[:MAX_RESULTS]


def _calls(model) -> list[Token]:
    """Every token that names a called keyword."""
    calls = []
    for node in _walk(model):
        if getattr(node, "type", None) in FIXTURES:
            calls.extend(t for t in node.tokens if t.type == Token.NAME and t.value.upper() != "NONE")
        elif hasattr(node, "tokens"):
            calls.extend(t for t in node.tokens if t.type == Token.KEYWORD)
    return calls


def _definitions(uri: str, model) -> dict[str, _Definition]:
    found = {}
    for node in _walk(model):
        if isinstance(node, Keyword):
            name = node.header.get_token(Token.KEYWORD_NAME)
            loc = Location(uri, name.lineno - 1, name.col_offset, name.end_col_offset)
            found[_key(node.name)] = _Definition(node.name, loc, _signature(node), _first_doc_line(node))
    return found


def _signature(node: Keyword) -> str:
    args = next((s.values for s in node.body if isinstance(s, Arguments)), ())
    return f"{node.name}({', '.join(args)})"


def _first_doc_line(node: Keyword) -> str:
    doc = next((s.value for s in node.body if isinstance(s, Documentation)), "")
    return doc.split("\n", 1)[0]


@dataclass
class _FileIndex:
    calls: list[Location] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    definitions: dict[str, _Definition] = field(default_factory=dict)


class WorkspaceIndex:
    """Keyword definitions and calls across every indexed file."""

    def __init__(self) -> None:
        self.files: dict[str, _FileIndex] = {}

    def update(self, uri: str, text: str) -> None:
        model = _parse(text, ".resource" if uri.endswith(".resource") else ".robot")
        tokens = _calls(model)
        self.files[uri] = _FileIndex(
            [Location(uri, t.lineno - 1, t.col_offset, t.end_col_offset) for t in tokens],
            [_key(t.value) for t in tokens],
            _definitions(uri, model),
        )

    def _name_at(self, uri: str, line: int, character: int) -> str | None:
        index = self.files.get(uri)
        if index is None:
            return None
        for loc, name in zip(index.calls, index.names):
            if loc.line == line and loc.start <= character <= loc.end:
                return name
        return next((k for k, d in index.definitions.items()
                     if d.location.line == line and d.location.start <= character <= d.location.end), None)

    def _lookup(self, uri: str, name: str) -> _Definition | None:
        local = self.files[uri].definitions.get(name)
        if local:
            return local
        return next((f.definitions[name] for f in self.files.values() if name in f.definitions), None)

    def _resolve(self, uri: str, line: int, character: int) -> _Definition | None:
        name = self._name_at(uri, line, character)
        return self._lookup(uri, name) if name else None

    def definition(self, uri: str, line: int, character: int) -> Location | None:
        found = self._resolve(uri, line, character)
        return found.location if found else None

    def references(self, uri: str, line: int, character: int) -> list[Location]:
        name = self._name_at(uri, line, character)
        if name is None:
            return []
        found = [loc for f in self.files.values() for loc, n in zip(f.calls, f.names) if n == name]
        return found[:MAX_RESULTS]

    def find(self, query: str) -> list[Found]:
        """Keywords whose name matches the query: exact, then prefix, then substring."""
        wanted = _key(query)
        ranked = []
        for f in self.files.values():
            for key, d in f.definitions.items():
                if wanted in key:
                    rank = 0 if key == wanted else 1 if key.startswith(wanted) else 2
                    ranked.append((rank, d.name, Found(d.name, d.location)))
        return [found for _, _, found in sorted(ranked, key=lambda r: r[:2])][:MAX_RESULTS]

    def hover(self, uri: str, line: int, character: int) -> str | None:
        found = self._resolve(uri, line, character)
        if found is None:
            return None
        text = f"{found.signature}\n{found.doc}" if found.doc else found.signature
        return text[:MAX_HOVER]
