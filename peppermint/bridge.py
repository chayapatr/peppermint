"""
Peppermint ↔ Python bridge.

Python libraries loaded via `use` should import from here rather than
touching interpreter internals directly. The bridge is the single place
that knows about both worlds.
"""
from __future__ import annotations
from typing import Any, Callable
import functools

_types: tuple | None = None

def _interp_types():
    global _types
    if _types is None:
        from .interpreter import Ok, Err
        _types = (Ok, Err)
    return _types


# --- Type predicates ---

def is_ok(val) -> bool:
    Ok, Err = _interp_types()
    return isinstance(val, Ok)

def is_err(val) -> bool:
    Ok, Err = _interp_types()
    return isinstance(val, Err)

def is_list(val) -> bool:
    return isinstance(val, list)


# --- Conversion: Peppermint → Python ---

def to_python(val) -> Any:
    """Unwrap Peppermint runtime values to plain Python."""
    Ok, Err = _interp_types()
    if isinstance(val, Ok):
        return to_python(val.value)
    if isinstance(val, Err):
        return val.msg
    if isinstance(val, list):
        return [to_python(r) for r in val]
    try:
        import numpy as np
        if isinstance(val, np.integer):  return int(val)
        if isinstance(val, np.floating): return float(val)
        if isinstance(val, np.ndarray):  return val.tolist()
    except ImportError:
        pass
    try:
        import pandas as pd
        if isinstance(val, pd.DataFrame): return val.to_dict(orient="records")
        if isinstance(val, pd.Series):    return val.tolist()
    except ImportError:
        pass
    return val


# --- Conversion: Python → Peppermint ---

def from_python(val) -> Any:
    """Wrap a plain Python value into a Peppermint Ok result."""
    Ok, Err = _interp_types()
    try:
        import numpy as np
        if isinstance(val, np.integer):  val = int(val)
        elif isinstance(val, np.floating): val = float(val)
        elif isinstance(val, np.ndarray): val = val.tolist()
    except ImportError:
        pass
    try:
        import pandas as pd
        if isinstance(val, pd.DataFrame): val = val.to_dict(orient="records")
        elif isinstance(val, pd.Series):  val = val.tolist()
    except ImportError:
        pass
    if isinstance(val, Ok) or isinstance(val, Err):
        return val
    return Ok(val)


def err(msg: str):
    """Return a Peppermint Err."""
    Ok, Err = _interp_types()
    return Err(msg)


def ok(val):
    """Return a Peppermint Ok."""
    Ok, Err = _interp_types()
    return Ok(val)


# --- Row utilities ---

def get_rows(val) -> list:
    """Extract rows from a list."""
    if isinstance(val, list):
        return val
    raise TypeError(f"expected a list, got {type(val).__name__}")


def map_rows(val, fn: Callable[[dict], dict]):
    """Apply fn to each row, return a new list wrapped in Ok."""
    return from_python([fn(row) for row in get_rows(val)])


def add_column(val, name: str, fn: Callable[[dict], Any]):
    """Add a new field to every row using fn(row) -> value."""
    return from_python([{**row, name: fn(row)} for row in get_rows(val)])


def filter_rows(val, fn: Callable[[dict], bool]):
    """Keep rows where fn(row) is truthy."""
    return from_python([row for row in get_rows(val) if fn(row)])


# --- Library loader ---

def load_python_file(path: str, alias: str | None = None) -> dict:
    """Import a .py file and return its public functions wrapped for Peppermint."""
    import importlib.util, inspect

    spec = importlib.util.spec_from_file_location("_pep_user_lib", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    return {
        name: wrap(obj)
        for name, obj in inspect.getmembers(mod, inspect.isfunction)
        if not name.startswith("_")
    }


def wrap(fn: Callable) -> Callable:
    """Wrap a plain Python function for use in Peppermint.

    - Args converted from Peppermint values to plain Python
    - Return value wrapped in Ok
    - Exceptions become Err
    """
    @functools.wraps(fn)
    def wrapper(*args, _interp=None, _env=None, _block=None, **kwargs):
        try:
            converted = [to_python(a) for a in args]
            converted_kwargs = {k: to_python(v) for k, v in kwargs.items()}
            return from_python(fn(*converted, **converted_kwargs))
        except Exception as e:
            Ok, Err = _interp_types()
            return Err(str(e))
    return wrapper


def wrap_lib(fns: dict) -> dict:
    """Wrap a dict of plain Python functions for use in Peppermint."""
    return {name: wrap(fn) for name, fn in fns.items()}


def pep_fn(fn: Callable) -> Callable:
    """Decorator for lib functions. The default choice for most lib functions.

    Automatically evaluates any unevaluated AST node kwargs via _interp before
    the function body runs. Plain values (str, int, float, bool, list) pass through
    unchanged. Exceptions are caught and returned as Err.

    Use @pep_fn_static if you know all args will always be plain Python values
    and want to skip the evaluation step.

    Usage::

        @pep_fn
        @pep_signature("ml.kmeans(k: Int | Range, on: str, out: str) -> List<Row>")
        def kmeans(data, k=None, on=None, out=None):
            ...
    """
    @functools.wraps(fn)
    def wrapper(*args, _interp=None, _env=None, **kwargs):
        def _ev(val):
            if _interp is None or val is None:
                return val
            if isinstance(val, (int, float, str, bool, list)):
                return val
            try:
                from .interpreter import PmRange
                if isinstance(val, PmRange):
                    return val
            except ImportError:
                pass
            try:
                return _interp.eval(val, _env)
            except Exception:
                return val

        evaluated_kwargs = {k: _ev(v) for k, v in kwargs.items()}
        try:
            return fn(*args, **evaluated_kwargs)
        except Exception as e:
            _, Err = _interp_types()
            return Err(str(e))

    wrapper._pep_fn = True
    return wrapper


pep_fn_lazy = pep_fn  # alias — same behavior, explicit about intent


def pep_fn_static(fn: Callable) -> Callable:
    """Decorator for lib functions whose args are guaranteed plain Python values.

    No evaluation step — args are passed directly to the function body.
    Use when every argument is a literal that the interpreter has already resolved.
    Exceptions are caught and returned as Err.

    Usage::

        @pep_fn_static
        @pep_signature("math.clamp(x: Num, lo: Num, hi: Num) -> Num")
        def clamp(x, lo, hi):
            ...
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        kwargs.pop("_interp", None)
        kwargs.pop("_env", None)
        kwargs.pop("_block", None)
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            _, Err = _interp_types()
            return Err(str(e))
    wrapper._pep_fn_static = True
    return wrapper
