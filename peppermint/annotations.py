"""Annotation execution engine for pipe steps.

Each annotation is a wrapper: it takes a `run_row` function and returns a new
`run_row` function with additional behavior. Wrappers compose by stacking.

    run_row: (row: dict, artifacts: dict) -> (out_row, was_cached, err_row)

Dispatch (serial or concurrent) iterates rows using the final wrapped run_row.
@until operates on the full result after dispatch, so it lives outside the stack.
"""
from __future__ import annotations
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from .ast_nodes import Call, Ident, FieldAccess, IntLit, FloatLit, StrLit, BoolLit
from .runtime import Ok, Err
from .context import Context


# --- Stable repr (cache key generation) ---

def stable_repr(node) -> str:
    """AST node → location-free string, stable across different source positions."""
    if isinstance(node, (IntLit, FloatLit, StrLit, BoolLit)):
        return repr(node.value)
    if isinstance(node, Ident):
        return node.name
    if isinstance(node, FieldAccess):
        return f"{stable_repr(node.obj)}.{node.field}"
    if isinstance(node, Call):
        name = stable_repr(node.func)
        kw = ",".join(f"{k}={stable_repr(v)}" for k, v in sorted(node.kwargs.items()))
        return f"{name}({kw})"
    return repr(type(node).__name__)


def step_cache_key(expr, annotations: list) -> str:
    ann_key = str([{"name": a["name"]} for a in annotations])
    return stable_repr(expr) + ann_key


# --- Annotation config ---

def parse_annotations(annotations: list, eval_fn, env) -> dict:
    """Extract annotation values into a plain config dict."""
    cfg = {
        "concurrent_n": None,
        "retry_n": 0,
        "row_cache": False,
        "progress": False,
    }
    for ann in annotations:
        name = ann["name"]
        args = ann["args"]
        if name == "concurrent" and args:
            cfg["concurrent_n"] = int(_resolve_arg(args[0], eval_fn, env))
        elif name == "retry" and args:
            cfg["retry_n"] = int(_resolve_arg(args[0], eval_fn, env))
        elif name == "row_cache":
            cfg["row_cache"] = True
        elif name == "progress":
            cfg["progress"] = True
    return cfg


def _resolve_arg(arg, eval_fn, env):
    if isinstance(arg, (int, float, str, bool)):
        return arg
    return eval_fn(arg, env)


# --- Wrappers ---

def wrap_retry(run_row: Callable, n: int, step_name: str) -> Callable:
    """Retry run_row up to n times on exception or Err result."""
    def wrapped(row, artifacts):
        last = None
        for _ in range(n + 1):
            try:
                out_row, was_cached, err_row = run_row(row, artifacts)
                if err_row is None:
                    return out_row, was_cached, err_row
                last = (out_row, was_cached, err_row)
            except Exception as e:
                last = (None, False, {**row, "_error": str(e), "_step": step_name})
        return last
    return wrapped


def wrap_row_cache(run_row: Callable, cache, step_src: str) -> Callable:
    """Check row cache before running; write cache on success."""
    from .cache import cache_key_for_row
    def wrapped(row, artifacts):
        rk = cache_key_for_row(row, step_src)
        cached = cache.get_row(rk)
        if cached is not None:
            return cached, True, None
        out_row, was_cached, err_row = run_row(row, artifacts)
        if err_row is None and out_row is not None and "_error" not in out_row:
            cache.set_row(rk, out_row)
        return out_row, False, err_row
    return wrapped


def wrap_progress(run_row: Callable, total: int) -> Callable:
    """Print a live progress bar to stderr after each row completes."""
    lock = threading.Lock()
    count = [0]

    def tick():
        with lock:
            count[0] += 1
            done = count[0]
        pct = int(done / total * 20)
        bar = "█" * pct + "░" * (20 - pct)
        print(f"\r  [{bar}] {done}/{total}", end="", flush=True, file=sys.stderr)
        if done == total:
            print(file=sys.stderr)

    def wrapped(row, artifacts):
        result = run_row(row, artifacts)
        tick()
        return result
    return wrapped


# --- Dispatch ---

def _collect_row_result(result_tuple, row, step_name, rc_stats):
    out_row, was_cached, err_row = result_tuple
    rc_stats["total"] += 1
    if err_row is not None:
        return None, err_row
    if was_cached:
        rc_stats["hits"] += 1
    return out_row, None


def run_rows_serial(rows, artifacts, errors, run_row, step_name, rc_stats):
    out_rows = []
    for row in rows:
        try:
            out_row, err_row = _collect_row_result(
                run_row(row, artifacts), row, step_name, rc_stats
            )
            if err_row is not None:
                errors.append(err_row)
            elif out_row is not None:
                out_rows.append(out_row)
        except Exception as e:
            errors.append({**row, "_error": str(e), "_step": step_name})
            rc_stats["total"] += 1
    return out_rows


def run_rows_parallel(rows, artifacts, run_row, step_name, n_workers):
    def _run_one(row):
        try:
            out_row, was_cached, err_row = run_row(row, artifacts)
            if err_row is not None:
                return [], [err_row]
            return ([out_row] if out_row is not None else []), []
        except Exception as e:
            return [], [{**row, "_error": str(e), "_step": step_name}]

    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        parts = list(pool.map(_run_one, rows))

    out_rows, errors = [], []
    for data_part, err_part in parts:
        out_rows.extend(data_part)
        errors.extend(err_part)
    return out_rows, errors


# --- Main entry point ---

def eval_with_annotations(expr, value, annotations, cfg, cache, call_name, eval_call, env, depth, step_cache):
    """Apply all annotations and execute expr on value.

    Execution order:
      1. Build run_row leaf (eval_call on single row)
      2. Stack wrappers: retry → row_cache → progress
      3. Dispatch: parallel (@concurrent) or serial (row_cache/progress/default)
    """
    use_row_cache = cfg["row_cache"] and cache is not None
    use_progress = cfg["progress"]
    concurrent_n = cfg["concurrent_n"]
    retry_n = cfg["retry_n"]

    rc_stats = {"hits": 0, "total": 0}
    needs_row_iter = use_row_cache or use_progress or bool(concurrent_n)

    if needs_row_iter:
        src = step_cache_key(expr, annotations)

        # 1. Leaf: eval expr on a single-row Context
        def run_row(row, artifacts):
            row_ctx = Context(data=[row], artifacts=artifacts, errors=[])
            result = eval_call(expr, row_ctx, env, depth=depth)
            rv = result.value if isinstance(result, Ok) else None
            if isinstance(rv, Context) and rv.errors:
                return None, False, rv.errors[0]
            out_rows = rv.data if isinstance(rv, Context) else (rv if isinstance(rv, list) else None)
            return (out_rows[0] if out_rows else None), False, None

        # 2. Stack wrappers (innermost first — retry wraps the raw call)
        wrapped = run_row
        if retry_n:
            wrapped = wrap_retry(wrapped, retry_n, call_name)
        if use_row_cache:
            wrapped = wrap_row_cache(wrapped, cache, src)

        # Extract rows from input
        if isinstance(value, Context):
            rows, artifacts, errors = value.data, value.artifacts, list(value.errors)
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            rows, artifacts, errors = value, {}, []
        else:
            rows = None

        if rows is not None:
            total = len(rows)
            if use_progress:
                wrapped = wrap_progress(wrapped, total)

            if concurrent_n:
                out_rows, new_errors = run_rows_parallel(rows, artifacts, wrapped, call_name, concurrent_n)
                errors.extend(new_errors)
            else:
                out_rows = run_rows_serial(rows, artifacts, errors, wrapped, call_name, rc_stats)

            result = Ok(Context(
                data=out_rows,
                artifacts=artifacts if isinstance(value, Context) else {},
                errors=errors,
            ))
        else:
            result = eval_call(expr, value, env, depth=depth)
    else:
        result = eval_call(expr, value, env, depth=depth, row_cache=step_cache)

    return result, rc_stats if use_row_cache else None
