from __future__ import annotations
import inspect
from dataclasses import dataclass
from typing import Any
from .ast_nodes import Loc


_fn_accepts_interp: dict = {}

def _check_accepts_interp(fn) -> bool:
    """Return True if fn accepts **kwargs or explicit _interp parameter."""
    cached = _fn_accepts_interp.get(id(fn))
    if cached is not None:
        return cached
    try:
        sig = inspect.signature(fn)
        result = any(
            p.kind == inspect.Parameter.VAR_KEYWORD or p.name == '_interp'
            for p in sig.parameters.values()
        )
    except (ValueError, TypeError):
        result = False
    _fn_accepts_interp[id(fn)] = result
    return result


@dataclass
class _TailCall:
    fn: "PmFunction"
    args: list
    env: "Env"


@dataclass
class Ok:
    value: Any
    def __repr__(self): return f"Ok({self.value!r})"


@dataclass
class Err:
    msg: str
    cause: "PepError | None" = None
    def __repr__(self): return f"Err({self.msg!r})"


@dataclass
class PmFunction:
    params: list[str]
    body: Any
    closure: "Env"
    def __repr__(self): return f"<fn({', '.join(self.params)})>"


@dataclass
class PmRange:
    start: int
    end: int


@dataclass
class ColRef:
    """Reference to a column across all rows — produced by col.field."""
    field: str
    def __repr__(self): return f"col.{self.field}"


class _ColProxy:
    """Sentinel object bound to 'col' in the global env."""
    def __getattr__(self, field: str) -> ColRef:
        return ColRef(field)
    def __repr__(self): return "col"


class Env:
    def __init__(self, parent: "Env | None" = None):
        self._vars: dict[str, Any] = {}
        self.parent = parent

    def get(self, name: str, loc=None) -> Any:
        if name in self._vars:
            return self._vars[name]
        if self.parent:
            return self.parent.get(name, loc)
        raise PepError(f"undefined variable '{name}'", loc=loc, span=len(name))

    def set(self, name: str, value: Any):
        self._vars[name] = value

    def extend(self, bindings: dict[str, Any]) -> "Env":
        child = Env(parent=self)
        for k, v in bindings.items():
            child.set(k, v)
        return child


class PepError(Exception):
    def __init__(self, msg: str, loc: "Loc | None" = None, span: int = 0):
        super().__init__(msg)
        self.loc = loc
        self.span = span
