"""Walk a parsed Peppermint AST and extract scope information.

Reuses peppermint.ast_nodes directly — no duplicate parsing logic.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from peppermint.ast_nodes import (
    Program, Assign, UseDecl, NsDecl, Ident, FieldAccess,
    Call, Pipe, PipeStep, Lambda, Match, Block, Loc,
    PatOk, PatErr, InterpolatedStr,
)


@dataclass
class ScopeEntry:
    name: str
    type_hint: str        # "List<Row>", "fn", "untyped", etc.
    loc: Loc
    is_stdlib: bool = False


@dataclass
class AnalysisResult:
    scope: dict[str, ScopeEntry] = field(default_factory=dict)
    undefined_refs: list[tuple[str, Loc]] = field(default_factory=list)


_ANNOTATION_NAMES = frozenset({"concurrent", "retry", "until", "stable"})


def _build_always_in_scope() -> frozenset[str]:
    """Build the set of always-in-scope names from core env + discovered libs + builtins."""
    from peppermint.stdlib.core import build_core_env
    from peppermint.stdlib import load_stdlib

    names = set(build_core_env().keys())
    names.update({"col", "it", "true", "false", "none"})
    names.update(_ANNOTATION_NAMES)

    libs_path = Path(__file__).parent.parent / "libs"
    for p in sorted(libs_path.glob("*.py")):
        stem = p.stem
        if stem.startswith("_"):
            continue
        lib_name = stem.rstrip("_")
        names.add(lib_name)  # "ml", "math", "str", etc. as namespace names

    return frozenset(names)


_ALWAYS_IN_SCOPE = _build_always_in_scope()


def _build_list_row_fns() -> frozenset[str]:
    """Scan _pep_signature attributes to find functions returning List<Row>."""
    from peppermint.stdlib.core import build_core_env
    fns: set[str] = set()
    for name, fn in build_core_env().items():
        sig = getattr(fn, "_pep_signature", None)
        if sig and "->" in sig and "List<Row>" in sig.split("->", 1)[1]:
            fns.add(name)
    return frozenset(fns)


_LIST_ROW_FNS = _build_list_row_fns()


def _infer_type(node) -> str:
    if isinstance(node, Call):
        fn = node.func
        name = fn.name if isinstance(fn, Ident) else None
        if name in _LIST_ROW_FNS:
            return "List<Row>"
    if isinstance(node, Lambda):
        return "fn"
    if isinstance(node, Pipe):
        if node.steps:
            last = node.steps[-1]
            expr = getattr(last, "expr", last)
            if isinstance(expr, Call):
                name = expr.func.name if isinstance(expr.func, Ident) else None
                if name in _LIST_ROW_FNS:
                    return "List<Row>"
    return "untyped"


def analyze(program: Program) -> AnalysisResult:
    result = AnalysisResult()

    # Pass 1: collect all top-level assigned names
    for stmt in program.body:
        if isinstance(stmt, Assign):
            result.scope[stmt.name] = ScopeEntry(
                name=stmt.name,
                type_hint=_infer_type(stmt.value),
                loc=stmt.loc,
            )
        elif isinstance(stmt, NsDecl):
            result.scope[stmt.name] = ScopeEntry(
                name=stmt.name,
                type_hint="namespace",
                loc=stmt.loc,
            )
        elif isinstance(stmt, UseDecl):
            alias = stmt.alias or stmt.path
            result.scope[alias] = ScopeEntry(
                name=alias,
                type_hint="namespace",
                loc=stmt.loc,
                is_stdlib=True,
            )

    # Pass 2: walk for undefined Ident references
    all_known = set(result.scope.keys()) | _ALWAYS_IN_SCOPE
    _walk_refs(program, all_known, result.undefined_refs)

    return result


def _walk_refs(node, known: set, undefined: list):
    if node is None:
        return
    if isinstance(node, Ident):
        if node.name not in known:
            undefined.append((node.name, node.loc))
        return
    if isinstance(node, Program):
        for child in node.body:
            _walk_refs(child, known, undefined)
    elif isinstance(node, Assign):
        _walk_refs(node.value, known, undefined)
    elif isinstance(node, Call):
        _walk_refs(node.func, known, undefined)
        for a in node.args:
            _walk_refs(a, known, undefined)
        for v in node.kwargs.values():
            _walk_refs(v, known, undefined)
    elif isinstance(node, PipeStep):
        _walk_refs(node.expr, known, undefined)
        # Walk annotation args (expressions like max: 5) but not the annotation names themselves
        for ann in getattr(node, 'annotations', []):
            for arg in ann.get("args", []):
                if isinstance(arg, dict) and "value" in arg:
                    _walk_refs(arg["value"], known, undefined)
                elif not isinstance(arg, (int, float, str, bool)):
                    _walk_refs(arg, known, undefined)
    elif isinstance(node, Pipe):
        pipe_known = set(known)
        for step in node.steps:
            if isinstance(step, Assign):
                _walk_refs(step.value, pipe_known, undefined)
                pipe_known.add(step.name)
            else:
                _walk_refs(step, pipe_known, undefined)
    elif isinstance(node, Lambda):
        inner = known | set(node.params) | {"it"}
        _walk_refs(node.body, inner, undefined)
    elif isinstance(node, Match):
        _walk_refs(node.subject, known, undefined)
        for arm in node.arms:
            arm_known = known
            if isinstance(arm.pattern, (PatOk, PatErr)) and arm.pattern.name:
                arm_known = known | {arm.pattern.name}
            _walk_refs(arm.body, arm_known, undefined)
    elif isinstance(node, Block):
        block_known = set(known)
        for s in node.stmts:
            if isinstance(s, Assign):
                block_known.add(s.name)
            elif isinstance(s, Pipe):
                for step in s.steps:
                    if isinstance(step, Assign):
                        block_known.add(step.name)
            _walk_refs(s, block_known, undefined)
    elif isinstance(node, FieldAccess):
        _walk_refs(node.obj, known, undefined)
    elif isinstance(node, InterpolatedStr):
        for part in node.parts:
            _walk_refs(part, known, undefined)
    elif hasattr(node, '__dataclass_fields__'):
        for fname in node.__dataclass_fields__:
            _walk_refs(getattr(node, fname), known, undefined)
