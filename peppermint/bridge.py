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
