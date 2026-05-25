"""Peppermint LSP server. Start with: pep lsp"""
from __future__ import annotations
import re
from pygls.lsp.server import LanguageServer
from lsprotocol.types import (
    TEXT_DOCUMENT_DID_OPEN, TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_HOVER, TEXT_DOCUMENT_COMPLETION,
    TEXT_DOCUMENT_DEFINITION,
    DidOpenTextDocumentParams, DidChangeTextDocumentParams,
    HoverParams, CompletionParams, DefinitionParams,
    Hover, MarkupContent, MarkupKind,
    CompletionList, CompletionItem, CompletionItemKind,
    Diagnostic, DiagnosticSeverity, Position, Range, Location,
    PublishDiagnosticsParams,
    TextDocumentSyncKind,
)
from peppermint.parser import parse, ParseError
from .analyzer import analyze, AnalysisResult
from .catalog import init as init_catalog, CATALOG

server = LanguageServer(
    "peppermint-lsp", "v0.1",
    text_document_sync_kind=TextDocumentSyncKind.Full,
)

# Per-document state: uri -> AnalysisResult
_docs: dict[str, AnalysisResult] = {}


def _parse_and_analyze(uri: str, text: str):
    diagnostics = []
    try:
        program = parse(text)
        result = analyze(program)
        _docs[uri] = result

        for name, loc in result.undefined_refs:
            start = Position(line=loc.line - 1, character=loc.col - 1)
            end = Position(line=loc.line - 1, character=loc.col - 1 + len(name))
            diagnostics.append(Diagnostic(
                range=Range(start=start, end=end),
                message=f"Undefined name: {name}",
                severity=DiagnosticSeverity.Warning,
            ))

    except ParseError as e:
        line = max(0, e.line - 1)
        col = max(0, e.col - 1)
        start = Position(line=line, character=col)
        end = Position(line=line, character=col + 1)
        diagnostics.append(Diagnostic(
            range=Range(start=start, end=end),
            message=str(e.args[0]).split(": ", 1)[-1],
            severity=DiagnosticSeverity.Error,
        ))

    server.text_document_publish_diagnostics(
        PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics)
    )


@server.feature(TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: LanguageServer, params: DidOpenTextDocumentParams):
    _parse_and_analyze(params.text_document.uri, params.text_document.text)


@server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: LanguageServer, params: DidChangeTextDocumentParams):
    text = params.content_changes[-1].text
    _parse_and_analyze(params.text_document.uri, text)


_OPERATORS = ["|>", "->"]

def _word_at(text: str, line: int, col: int) -> str:
    lines = text.splitlines()
    if line >= len(lines):
        return ""
    src_line = lines[line]
    # Check if cursor is on a known operator (check col and col-1 to catch both chars)
    for op in _OPERATORS:
        for start in (col - 1, col):
            if start >= 0 and src_line[start:start + len(op)] == op:
                return op
    left = col
    while left > 0 and (src_line[left - 1].isalnum() or src_line[left - 1] in "_."):
        left -= 1
    right = col
    while right < len(src_line) and (src_line[right].isalnum() or src_line[right] in "_."):
        right += 1
    return src_line[left:right].strip(".")


def _hover_content(name: str, result: AnalysisResult | None) -> str | None:
    entry = CATALOG.get(name)
    if entry:
        sig = entry.get("signature") or name
        doc = entry.get("doc") or ""
        return f"```peppermint\n{sig}\n```\n\n{doc}"

    if result and name in result.scope:
        scope_entry = result.scope[name]
        return f"```peppermint\n(variable) {name}: {scope_entry.type_hint}\n```"

    return None


@server.feature(TEXT_DOCUMENT_HOVER)
def hover(ls: LanguageServer, params: HoverParams) -> Hover | None:
    uri = params.text_document.uri
    doc = ls.workspace.get_text_document(uri)
    word = _word_at(doc.source, params.position.line, params.position.character)
    if not word:
        return None
    result = _docs.get(uri)
    content = _hover_content(word, result)
    if not content:
        return None
    return Hover(contents=MarkupContent(kind=MarkupKind.Markdown, value=content))


@server.feature(TEXT_DOCUMENT_COMPLETION)
def completion(ls: LanguageServer, params: CompletionParams) -> CompletionList:
    uri = params.text_document.uri
    doc = ls.workspace.get_text_document(uri)
    pos = params.position
    src_lines = doc.source.splitlines()
    line_text = src_lines[pos.line] if pos.line < len(src_lines) else ""
    prefix = line_text[:pos.character]

    items = []

    # After "ml.", "math.", etc. — namespace completions
    ns_match = re.search(r'(\w+)\.$', prefix)
    if ns_match:
        ns = ns_match.group(1)
        # Suppress after "it." and "col." — dynamic fields
        if ns in ("it", "col"):
            return CompletionList(is_incomplete=False, items=[])
        for name, entry in CATALOG.items():
            if name.startswith(f"{ns}."):
                fn_name = name[len(ns) + 1:]
                items.append(CompletionItem(
                    label=fn_name,
                    kind=CompletionItemKind.Function,
                    detail=entry.get("signature"),
                    documentation=entry.get("doc"),
                ))
        return CompletionList(is_incomplete=False, items=items)

    # General: top-level catalog names + user-defined names
    for name, entry in CATALOG.items():
        if "." not in name:
            items.append(CompletionItem(
                label=name,
                kind=CompletionItemKind.Function,
                detail=entry.get("signature"),
                documentation=entry.get("doc"),
            ))

    result = _docs.get(uri)
    if result:
        for name, scope_entry in result.scope.items():
            kind = CompletionItemKind.Function if scope_entry.type_hint == "fn" else CompletionItemKind.Variable
            items.append(CompletionItem(label=name, kind=kind))

    return CompletionList(is_incomplete=False, items=items)


@server.feature(TEXT_DOCUMENT_DEFINITION)
def definition(ls: LanguageServer, params: DefinitionParams) -> Location | None:
    uri = params.text_document.uri
    doc = ls.workspace.get_text_document(uri)
    word = _word_at(doc.source, params.position.line, params.position.character)
    result = _docs.get(uri)
    if not result or word not in result.scope:
        return None
    entry = result.scope[word]
    if entry.is_stdlib:
        return None
    loc = entry.loc
    pos = Position(line=loc.line - 1, character=loc.col - 1)
    return Location(uri=uri, range=Range(start=pos, end=pos))


def start():
    init_catalog()
    server.start_io()
