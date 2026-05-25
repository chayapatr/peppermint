"""Scans stdlib at startup and builds a lookup table for hover/completion."""
from __future__ import annotations
import inspect
from pathlib import Path
from peppermint.stdlib.core import build_core_env
from peppermint.stdlib import load_stdlib


def _discover_libs() -> list[str]:
    """Return all lib names autodiscovered from peppermint/libs/."""
    libs_path = Path(__file__).parent.parent / "libs"
    names = []
    for p in sorted(libs_path.glob("*.py")):
        stem = p.stem
        if stem.startswith("_"):
            continue
        # strip trailing underscore used to avoid shadowing builtins (e.g. math_)
        names.append(stem.rstrip("_"))
    return names


_KEYWORDS: dict[str, dict] = {
    "match": {
        "signature": "match(value, pat: result, ..., _: fallback)",
        "doc": "Pattern match on a value. Arms are `pattern: expr`. Use `_` for the wildcard/default arm.",
    },
    "use": {
        "signature": "use <lib>",
        "doc": "Import a standard library namespace (e.g. `use math`, `use ml`). Makes `lib.fn` calls available.",
    },
    "true": {"signature": "true", "doc": "Boolean true."},
    "false": {"signature": "false", "doc": "Boolean false."},
    "none": {"signature": "none", "doc": "Null / no value."},
    "it": {"signature": "it", "doc": "Current element in `filter`, `map`, or `each` expressions."},
    "col": {"signature": "col.field", "doc": "Column reference. Use inside `collapse`, `add`, `rank`, or `rolling` to refer to a column by name."},
    "|>": {
        "signature": "expr |> fn(...)",
        "doc": "Pipe operator. Passes the left-hand value as the first argument to the right-hand function call.",
    },
    "->": {
        "signature": "params -> body",
        "doc": "Lambda. Single param: `x -> x + 1`. Multiple params: `(x, y) -> x + y`. Curried: `x -> y -> x + y`.",
    },
}


def build_catalog() -> dict[str, dict]:
    """Return {name: {signature, doc}} for all stdlib + lib functions.

    Core names use their bare name (e.g. "filter").
    Lib names are prefixed with the lib name (e.g. "ml.embed").
    """
    catalog: dict[str, dict] = dict(_KEYWORDS)

    for name, fn in build_core_env().items():
        sig = getattr(fn, "_pep_signature", None)
        doc = inspect.getdoc(fn)
        if sig or doc:
            catalog[name] = {"signature": sig, "doc": doc}

    for lib in _discover_libs():
        try:
            env = load_stdlib(lib)
        except KeyError:
            continue
        for fn_name, fn in env.items():
            sig = getattr(fn, "_pep_signature", None)
            doc = inspect.getdoc(fn)
            if sig or doc:
                catalog[f"{lib}.{fn_name}"] = {"signature": sig, "doc": doc}

    return catalog


# Singleton — built once at server startup
CATALOG: dict[str, dict] = {}


def init():
    CATALOG.update(build_catalog())
