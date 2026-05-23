"""
Peppermint ↔ Python bridge.

Python libraries loaded via `use` should import from here rather than
touching interpreter internals directly. The bridge is the single place
that knows about both worlds.
"""
from __future__ import annotations
from typing import Any, Callable


# --- Lazy imports to avoid circular deps ---

def _interp_types():
    from .interpreter import Ok, Err, ListValue
    return Ok, Err, ListValue


# --- Type predicates ---

def is_ok(val) -> bool:
    Ok, Err, ListValue = _interp_types()
    return isinstance(val, Ok)

def is_err(val) -> bool:
    Ok, Err, ListValue = _interp_types()
    return isinstance(val, Err)

def is_list(val) -> bool:
    Ok, Err, ListValue = _interp_types()
    return isinstance(val, (ListValue, list))

def is_object_list(val) -> bool:
    Ok, Err, ListValue = _interp_types()
    if isinstance(val, ListValue):
        return True
    if isinstance(val, list):
        return bool(val) and isinstance(val[0], dict)
    return False


# --- Conversion: Peppermint → Python ---

def to_python(val) -> Any:
    """Unwrap Peppermint runtime values to plain Python."""
    Ok, Err, ListValue = _interp_types()
    if isinstance(val, Ok):
        return to_python(val.value)
    if isinstance(val, Err):
        raise RuntimeError(val.msg)
    if isinstance(val, ListValue):
        return val.rows          # list[dict]
    return val


# --- Conversion: Python → Peppermint ---

def _infer_schema(rows: list[dict]) -> dict:
    if not rows:
        return {}
    return {k: type(v) for k, v in rows[0].items()}


def make_list(rows: list[dict]):
    """Wrap a list of dicts into a Peppermint ListValue."""
    Ok, Err, ListValue = _interp_types()
    return ListValue(rows=rows, schema=_infer_schema(rows))


def from_python(val) -> Any:
    """Wrap a plain Python value back into a Peppermint Ok result."""
    Ok, Err, ListValue = _interp_types()
    if isinstance(val, (Ok, Err)):
        return val
    if isinstance(val, list) and val and isinstance(val[0], dict):
        return Ok(make_list(val))
    return Ok(val)


def err(msg: str):
    """Return a Peppermint Err."""
    Ok, Err, ListValue = _interp_types()
    return Err(msg)


def ok(val):
    """Return a Peppermint Ok."""
    Ok, Err, ListValue = _interp_types()
    return Ok(val)


# --- Row utilities ---

def get_rows(val) -> list[dict]:
    """Extract rows from a ListValue or plain list[dict]."""
    Ok, Err, ListValue = _interp_types()
    if isinstance(val, ListValue):
        return val.rows
    if isinstance(val, list):
        return val
    raise TypeError(f"expected a list, got {type(val).__name__}")


def map_rows(val, fn: Callable[[dict], dict]):
    """Apply fn to each row, return a new ListValue wrapped in Ok."""
    rows = get_rows(val)
    return from_python([fn(row) for row in rows])


def add_column(val, name: str, fn: Callable[[dict], Any]):
    """Add a new field to every row using fn(row) -> value."""
    rows = get_rows(val)
    return from_python([{**row, name: fn(row)} for row in rows])


def filter_rows(val, fn: Callable[[dict], bool]):
    """Keep rows where fn(row) is truthy."""
    rows = get_rows(val)
    return from_python([row for row in rows if fn(row)])


# --- Library loader ---

def load_python_file(path: str, alias: str | None = None) -> dict:
    """
    Import a .py file and return its public functions as a dict.
    Functions are wrapped so their return values are auto-converted
    from Python to Peppermint types.
    """
    import importlib.util, inspect

    spec = importlib.util.spec_from_file_location("_pep_user_lib", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    fns = {}
    for name, obj in inspect.getmembers(mod, inspect.isfunction):
        if name.startswith("_"):
            continue
        fns[name] = _wrap(obj)
    return fns


def _wrap(fn: Callable) -> Callable:
    """
    Wrap a plain Python function so that:
    - Its first arg (the piped value) is converted from Peppermint to Python
    - Its return value is converted from Python to Peppermint
    - Exceptions become Err
    """
    import functools

    @functools.wraps(fn)
    def wrapper(*args, _interp=None, _env=None, _block=None, **kwargs):
        try:
            # Convert first positional arg (piped value) if present
            converted = []
            for i, arg in enumerate(args):
                converted.append(to_python(arg) if i == 0 else arg)
            result = fn(*converted, **kwargs)
            return from_python(result)
        except Exception as e:
            Ok, Err, ListValue = _interp_types()
            return Err(str(e))

    return wrapper
