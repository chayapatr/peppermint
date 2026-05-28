from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Loc:
    line: int
    col: int

    def __repr__(self):
        return f"{self.line}:{self.col}"


NO_LOC = Loc(0, 0)

# --- Patterns (used in match arms) ---

@dataclass
class PatComparison:
    op: str        # >, <, >=, <=, ==, !=
    value: Any     # int | float | str | Expr (variable)
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class PatOk:
    name: str
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class PatErr:
    name: str
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class PatTuple:
    patterns: list
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class PatWildcard:
    loc: Loc = field(default_factory=lambda: NO_LOC)

Pattern = PatComparison | PatOk | PatErr | PatTuple | PatWildcard

# --- Expressions ---

@dataclass
class IntLit:
    value: int
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class FloatLit:
    value: float
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class StrLit:
    value: str
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class BoolLit:
    value: bool
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class NoneLit:
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class Ident:
    name: str
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class FieldAccess:
    obj: Any       # Expr
    field: str
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class Neg:
    operand: Any   # Expr
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class BinOp:
    op: str        # +, -, *, /, >, <, >=, <=, ==, !=
    left: Any      # Expr
    right: Any     # Expr
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class Call:
    func: Any      # Expr — already resolved to FieldAccess or Ident by postfix rule
    args: list     # list[Expr]
    kwargs: dict   # str -> Expr
    block: list | None  # list[PipeStep] | None
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class Lambda:
    params: list[str]
    body: Any      # Expr
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class Pipe:
    steps: list    # list[Expr] — first is the source, rest are calls
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class PipeStep:
    expr: Any      # Call
    quiet: bool
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class Match:
    subject: Any   # Expr
    arms: list     # list[MatchArm]
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class MatchArm:
    pattern: Pattern
    body: Any      # Expr
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class ListLit:
    items: list    # list[Expr]
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class ObjField:
    key: str
    value: Any     # Expr
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class ObjSpread:
    obj: Any       # Expr
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class ObjShorthand:
    key: str       # { x } = { x: x }
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class ObjLit:
    entries: list  # list[ObjField | ObjSpread]
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class TupleLit:
    items: list    # list[Expr]
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class Spread:
    obj: Any       # Expr
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class Range:
    start: Any   # Expr (IntLit or arbitrary expression)
    end: Any     # Expr
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class Block:
    stmts: list   # list[Expr] — evaluates each, returns last
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class Literal:
    value: Any    # already-evaluated runtime value, passes through eval unchanged
    loc: Loc = field(default_factory=lambda: NO_LOC)

# --- Statements ---

@dataclass
class Assign:
    name: str
    value: Any     # Expr
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class UseDecl:
    path: str      # module name or file path string
    alias: str | None
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class NsDecl:
    name: str
    body: list     # list[Assign]
    loc: Loc = field(default_factory=lambda: NO_LOC)

@dataclass
class InterpolatedStr:
    parts: list    # alternating StrLit and Expr nodes
    loc: Loc = field(default_factory=lambda: NO_LOC)


@dataclass
class Program:
    body: list     # list[Assign | UseDecl | NsDecl | Expr]
    loc: Loc = field(default_factory=lambda: NO_LOC)
