from __future__ import annotations
import json
from typing import Any
import pandas as pd
from ..interpreter import Ok, Err, PmFunction, ColRef

builtins_str = str
builtins_int = int
builtins_float = float


def pep_signature(sig: str):
    """Decorator that attaches a Peppermint-facing signature string to a stdlib function."""
    def decorator(fn):
        fn._pep_signature = sig
        return fn
    return decorator


def _eval_arg(arg, interp, env):
    if interp and hasattr(arg, '__class__') and hasattr(interp, 'eval'):
        try:
            return interp.eval(arg, env)
        except Exception:
            return arg
    return arg


def _to_list(data) -> list:
    if isinstance(data, Ok):
        return _to_list(data.value)
    from ..context import Context
    if isinstance(data, Context):
        return data.data
    if isinstance(data, list):
        return data
    raise TypeError(f"expected a List, got {type(data).__name__}")


def _as_ctx(data):
    """Coerce a table (list of dicts or Context) to Context. Returns None for non-table data."""
    from ..context import Context
    if isinstance(data, Context):
        return data
    if isinstance(data, Ok):
        return _as_ctx(data.value)
    if isinstance(data, list):
        if not data or isinstance(data[0], dict):
            return Context(data=data)
    return None


def _is_table(data) -> bool:
    from ..context import Context
    if isinstance(data, Context):
        return True
    v = data.value if isinstance(data, Ok) else data
    return isinstance(v, list) and (not v or isinstance(v[0], dict))


def _unwrap(v):
    return v.value if isinstance(v, Ok) else v


# --- IO — these return Ok/Err ---

@pep_signature("load(path: str) -> Ok<List<Row>> | Err")
def load(path, _interp=None, _env=None, **_) -> Ok | Err:
    """Load a CSV, JSON, YAML, or TXT file.

JSON/YAML: if top-level is a list, returns a table; if a dict, returns a single-row table.
TXT: returns a table with one row per non-empty line: `{ line, index }`.
CSV: standard tabular load."""
    try:
        from ..context import Context
        path = _eval_arg(path, _interp, _env)
        if path.endswith(".json"):
            with open(path) as f:
                data = json.load(f)
            rows = data if isinstance(data, list) else [data]
        elif path.endswith(".yaml") or path.endswith(".yml"):
            import yaml
            with open(path) as f:
                data = yaml.safe_load(f)
            rows = data if isinstance(data, list) else [data]
        elif path.endswith(".txt"):
            with open(path) as f:
                lines = [l.rstrip("\n") for l in f if l.strip()]
            rows = [{"line": line, "index": i} for i, line in enumerate(lines)]
        else:
            df = pd.read_csv(path)
            rows = df.to_dict(orient="records")
        return Ok(Context(data=rows))
    except Exception as e:
        return Err(str(e))


@pep_signature("save(path: str) -> Ok<Context> | Err")
def save(data, path, _interp=None, _env=None, **_) -> Ok | Err:
    """Write rows to a CSV, JSON, YAML, or TXT file. Creates directories if needed.

TXT: writes one `line` field per row, ignoring other fields."""
    try:
        import os
        path = _eval_arg(path, _interp, _env)
        os.makedirs(os.path.dirname(path), exist_ok=True) if os.path.dirname(path) else None
        rows = _to_list(data)
        if path.endswith(".json"):
            import json as _json
            with open(path, "w") as f:
                _json.dump(rows, f, indent=2, default=str)
        elif path.endswith(".yaml") or path.endswith(".yml"):
            import yaml
            with open(path, "w") as f:
                yaml.dump(rows, f, allow_unicode=True, sort_keys=False)
        elif path.endswith(".txt"):
            with open(path, "w") as f:
                for row in rows:
                    f.write(str(row.get("line", row)) + "\n")
        else:
            df = pd.DataFrame(rows)
            df.to_csv(path, index=False)
        return Ok(data)
    except Exception as e:
        return Err(str(e))


# --- Pure functions — return plain values ---

@pep_signature("filter(pred: Expr) -> List<Row>")
def filter_(data, pred, _interp=None, _env=None, **_) -> list:
    """Keep rows where pred is true. `it` refers to the current row."""
    fn = _interp.make_row_fn(pred, _env)
    ctx = _as_ctx(data)
    if ctx is not None:
        return ctx.with_data([item for item in ctx.data if _unwrap(fn(item))])
    return [item for item in _to_list(data) if _unwrap(fn(item))]


@pep_signature("map(expr: Expr) -> List<Any>")
def map_(data, transform, _interp=None, _env=None, _row_cache=None, **_) -> list:
    """Transform every element. `it` refers to the current element. Use `@concurrent(N)` for parallel execution."""
    items = _to_list(data)
    fn = _interp.make_row_fn(transform, _env, row_cache=_row_cache)
    return [_unwrap(fn(item)) for item in items]


@pep_signature("mapi(expr: Expr) -> List<Any>")
def mapi(data, transform, _interp=None, _env=None, _row_cache=None, **_) -> list:
    """Map with index. `it` is `{ idx: Int, val: Any }`. Use `@concurrent(N)` for parallel execution."""
    items = _to_list(data)
    fn = _interp.make_row_fn(transform, _env, row_cache=_row_cache)
    indexed = [{"idx": i, "val": x} for i, x in enumerate(items)]
    return [_unwrap(fn(item)) for item in indexed]


@pep_signature("add(field: Expr, ...) -> List<Row>")
def add(data, _interp=None, _env=None, _row_cache=None, **kwargs) -> list:
    """Add one or more fields to every row. Use `it.field` or `col.field` expressions.
Multiple fields are evaluated independently against the original row — field B cannot reference field A from the same `add` call.
Use `@concurrent(N)` and `@retry(N)` annotations for parallel/retry execution.
If the expression fails for a row, that row moves to `.errors` (with `_error` and `_step`). Use `recover()` to handle failures."""
    from ..context import Context

    non_meta = {k: v for k, v in kwargs.items() if k not in ("_interp", "_env", "_block", "_depth", "_row_cache")}
    if not non_meta:
        raise ValueError("add() requires at least one keyword argument: the new field name(s)")

    ctx = _as_ctx(data)
    rows = ctx.data if ctx is not None else _to_list(data)
    existing_errors = list(ctx.errors) if ctx is not None else []

    for field, expr in non_meta.items():
        val = _unwrap(_eval_arg(expr, _interp, _env))
        if hasattr(val, "broadcast"):
            df = pd.DataFrame(rows)
            series = val.broadcast(df)
            out = df.copy()
            out[field] = series.values
            rows = out.to_dict(orient="records")
            continue

        fn = _interp.make_row_fn(expr, _env, row_cache=_row_cache)
        good = []
        bad = []

        for row in rows:
            try:
                result = _unwrap(fn(row))
                if isinstance(result, Err):
                    bad.append({**row, "_error": result.msg, "_step": f"add({field})"})
                else:
                    good.append({**row, field: result})
            except Exception as e:
                bad.append({**row, "_error": str(e), "_step": f"add({field})"})

        rows = good
        existing_errors = existing_errors + bad

    if ctx is not None:
        return Context(data=rows, artifacts=ctx.artifacts, errors=existing_errors)
    return rows


@pep_signature("take(n: Int) -> List<Row>")
def take(data, n, _interp=None, _env=None, **_) -> list:
    """Keep the first n rows."""
    n = int(_eval_arg(n, _interp, _env))
    ctx = _as_ctx(data)
    if ctx is not None:
        return ctx.with_data(ctx.data[:n])
    return _to_list(data)[:n]


@pep_signature("drop(field: str, ...) -> List<Row>")
def drop(data, *fields, _interp=None, _env=None, **_) -> list:
    """Remove one or more fields from every row."""
    fields = {_eval_arg(f, _interp, _env) for f in fields}
    ctx = _as_ctx(data)
    rows = ctx.data if ctx is not None else _to_list(data)
    result = [{k: v for k, v in row.items() if k not in fields} for row in rows]
    return ctx.with_data(result) if ctx is not None else result


@pep_signature("select(fields: str..., renamed?: Expr) -> List<Row>")
def select(data, *fields, _interp=None, _env=None, _row_cache=None, **kwargs) -> list:
    """Keep only the specified fields. Keyword args compute or rename: `select("a", b: it.x + 1)`."""
    fields = [_eval_arg(f, _interp, _env) for f in fields]
    non_meta = {k: v for k, v in kwargs.items() if k not in ("_interp", "_env", "_block", "_depth", "_row_cache")}
    ctx = _as_ctx(data)
    rows = ctx.data if ctx is not None else _to_list(data)

    from ..context import Context
    good = []
    bad = []
    existing_errors = list(ctx.errors) if ctx is not None else []

    for row in rows:
        new_row = {f: row[f] for f in fields if f in row}
        failed = None
        for field, expr in non_meta.items():
            fn = _interp.make_row_fn(expr, _env, row_cache=_row_cache)
            try:
                result = _unwrap(fn(row))
                if isinstance(result, Err):
                    failed = (field, result.msg)
                    break
                new_row[field] = result
            except Exception as e:
                failed = (field, str(e))
                break
        if failed:
            bad.append({**row, "_error": failed[1], "_step": f"select({failed[0]})"})
        else:
            good.append(new_row)

    if ctx is not None:
        return Context(data=good, artifacts=ctx.artifacts, errors=existing_errors + bad)
    return good


@pep_signature('rename(old: new) -> List<Row>')
def rename(data, _interp=None, _env=None, **kwargs) -> list:
    """Rename a field. Pass as keyword: `rename(old_name: "new_name")`."""
    non_meta = {k: v for k, v in kwargs.items() if not k.startswith("_")}
    if len(non_meta) != 1:
        raise ValueError("rename() requires exactly one keyword argument: old: new")
    old, new_expr = next(iter(non_meta.items()))
    new = _eval_arg(new_expr, _interp, _env)
    ctx = _as_ctx(data)
    rows = ctx.data if ctx is not None else _to_list(data)
    result = [{(new if k == old else k): v for k, v in row.items()} for row in rows]
    return ctx.with_data(result) if ctx is not None else result


@pep_signature('sort(by: str, dir?: "asc" | "desc") -> List<Row>')
def sort(data, by=None, dir=None, _interp=None, _env=None, **_) -> list:
    """Sort rows by a field. `dir` defaults to `"asc"`."""
    by = _eval_arg(by, _interp, _env)
    dir = _eval_arg(dir, _interp, _env) if dir is not None else "asc"
    ctx = _as_ctx(data)
    rows = ctx.data if ctx is not None else _to_list(data)
    result = sorted(rows, key=lambda r: r.get(by) if isinstance(r, dict) else r, reverse=(dir == "desc"))
    return ctx.with_data(result) if ctx is not None else result


@pep_signature("reduce(init: Any, fn: (Any, Any) -> Any) -> Any")
def reduce(data, init, fn, _interp=None, _env=None, **_) -> Any:
    """Fold the list into a single value, starting from `init`."""
    import functools
    data = _eval_arg(data, _interp, _env)
    items = _to_list(data)
    init = _eval_arg(init, _interp, _env)
    pm_fn = _interp.eval(fn, _env) if _interp else fn

    def apply(acc, item):
        if isinstance(pm_fn, PmFunction):
            return _unwrap(_interp._call_pm_function(pm_fn, [acc, item], {}, None, _env))
        return pm_fn(acc, item)

    return functools.reduce(apply, items, init)



@pep_signature("each(by: str, |> ...) -> List<Row>")
def each(data, *args, by=None, fn=None, _block=None, _interp=None, _env=None, _depth=0, **kwargs):
    """Run a sub-pipe for each group. Results are concatenated, or original table returned for side effects.
Accepts a block `{ |> ... }` or a lambda `x -> x |> ...` as the sub-pipe."""
    from ..ast_nodes import Pipe, Literal
    from ..context import Context

    # Lambda form: each(by: "col", grp -> grp |> ...)
    # The lambda arrives as a positional arg alongside by: kwarg
    fn_arg = fn
    for a in args:
        if isinstance(a, PmFunction):
            fn_arg = a
            break
    if isinstance(fn_arg, PmFunction):
        _block = None  # use lambda path

    by = _eval_arg(by, _interp, _env)
    if by is None:
        raise ValueError("each() requires 'by' argument")
    if _block is None and fn_arg is None:
        raise ValueError("each() requires a sub-pipe block or lambda")

    ctx = _as_ctx(data)
    groups: dict = {}
    for row in ctx.data:
        key = row.get(by)
        groups.setdefault(key, []).append(row)

    all_results = []
    all_errors = list(ctx.errors)
    all_artifacts = dict(ctx.artifacts)
    is_side_effect = None

    for key, group_rows in groups.items():
        group_ctx = Context(data=group_rows)

        if fn_arg is not None and isinstance(fn_arg, PmFunction):
            result = _interp._call_pm_function(fn_arg, [group_ctx], {}, None, _env)
        else:
            pipe = Pipe(steps=[Literal(group_ctx)] + list(_block))
            result = _interp.eval_pipe(pipe, _env, depth=_depth + 1)

        if isinstance(result, Err):
            return result
        value = result.value if isinstance(result, Ok) else result

        if isinstance(value, Context):
            if is_side_effect is None:
                is_side_effect = False
            # Re-inject group key for rows that lost it (e.g. after collapse)
            rows_out = [r if r.get(by) is not None else {by: key, **r} for r in value.data]
            all_results.extend(rows_out)
            all_errors.extend(value.errors)
            for name, artifact in value.artifacts.items():
                all_artifacts.setdefault(name, {})[key] = artifact
        elif isinstance(value, list):
            if is_side_effect is None:
                is_side_effect = False
            rows_out = [r if (isinstance(r, dict) and r.get(by) is not None) else ({by: key, **r} if isinstance(r, dict) else r) for r in value]
            all_results.extend(rows_out)
        else:
            is_side_effect = True

    if is_side_effect:
        return ctx
    return Context(data=all_results, artifacts=all_artifacts, errors=all_errors)


@pep_signature("join(other: List<Row>, on: str) -> List<Row>")
@pep_signature("cross(field: str, values: List) -> List<Row>")
def cross(data, field=None, values=None, _interp=None, _env=None, **_):
    """Duplicate every row once per value in `values`, adding `field` as a new column.

Use to fan out a table across multiple models, conditions, or parameters:
`|> cross("target_model", ["gpt-4o", "claude-sonnet-4-6"])`"""
    field = _eval_arg(field, _interp, _env)
    values = _eval_arg(values, _interp, _env)
    ctx = _as_ctx(data)
    rows = ctx.data if ctx is not None else _to_list(data)
    result = [{**row, field: v} for row in rows for v in values]
    return ctx.with_data(result) if ctx is not None else result


def join(data, other, on=None, _interp=None, _env=None, **_) -> list:
    """Inner join on a shared key field. Rows with no match are dropped."""
    on = _eval_arg(on, _interp, _env)
    other_rows = _to_list(other)
    index = {row[on]: row for row in other_rows if on in row}
    ctx = _as_ctx(data)
    rows = ctx.data if ctx is not None else _to_list(data)
    result = [{**row, **index[row.get(on)]} for row in rows if row.get(on) in index]
    return ctx.with_data(result) if ctx is not None else result


@pep_signature("print(value: Any) -> Any")
def print_(data, _interp=None, _env=None, **_):
    """Print a value and pass it through unchanged."""
    val = _eval_arg(data, _interp, _env)
    from ..context import Context
    if isinstance(val, Context):
        print(val.data)
    else:
        print(val)
    return val


@pep_signature("halt(message?: str) -> never")
def halt(message=None, _interp=None, _env=None, **_):
    """Stop execution immediately with an optional message."""
    import sys
    msg = _eval_arg(message, _interp, _env) if message is not None else "halted"
    print(f"halt: {msg}", file=sys.stderr)
    sys.exit(1)


@pep_signature("recover(field: Expr) -> List<Row>")
def recover(data, _interp=None, _env=None, _row_cache=None, **kwargs):
    """Move error rows back into data using a fallback expression.

Applies to all rows currently in `.errors`. For each error row, evaluates
the fallback expression with `it` bound to the row, sets the field, and
moves the row back into `.data`. Clears `.errors` after recovery.

Example: `|> add(label: ml.llm(...)) |> recover(label: "unknown")`
Example: `|> add(label: ml.llm(...)) |> recover(label: it.title)`"""
    from ..context import Context
    ctx = _as_ctx(data)
    if ctx is None or not ctx.errors:
        return data

    non_meta = {k: v for k, v in kwargs.items() if k not in ("_interp", "_env", "_block", "_depth", "_row_cache")}
    if not non_meta:
        raise ValueError("recover() requires exactly one keyword argument: the field name")

    field, expr = next(iter(non_meta.items()))
    fn = _interp.make_row_fn(expr, _env, row_cache=_row_cache)

    recovered = []
    still_failing = []
    for row in ctx.errors:
        try:
            fallback = _unwrap(fn(row))
            recovered.append({**row, field: fallback,
                               **{k: v for k, v in row.items() if k.startswith("_") and k != field}})
        except Exception:
            still_failing.append(row)

    from ..context import Context
    return Context(
        data=ctx.data + recovered,
        artifacts=ctx.artifacts,
        errors=still_failing,
    )


# --- Aggregation ---

class _AggFn:
    """Produced by mean(col.field), sum(col.field), etc.
    col_ref: ColRef — the column to aggregate.
    by: optional str — group key for broadcasting back onto rows (used in add).
    """
    def __init__(self, op: str, col_ref, by=None):
        self.op = op
        self.col_ref = col_ref  # ColRef or None (for count)
        self.by = by

    def apply(self, df: pd.DataFrame) -> Any:
        if self.op == "count":
            return len(df)
        series = df[self.col_ref.field]
        if isinstance(series.iloc[0], list):
            import numpy as np
            stacked = np.stack(series.tolist())
            if self.op == "mean": return np.mean(stacked, axis=0).tolist()
            if self.op == "sum":  return np.sum(stacked, axis=0).tolist()
            if self.op == "min":  return np.min(stacked, axis=0).tolist()
            if self.op == "max":  return np.max(stacked, axis=0).tolist()
        if self.op == "sum":  return series.sum()
        if self.op == "mean": return series.mean()
        if self.op == "min":  return series.min()
        if self.op == "max":  return series.max()

    def broadcast(self, df: pd.DataFrame) -> pd.Series:
        """For use inside add() with by: — returns a Series aligned to df."""
        if self.by:
            return df.groupby(self.by)[self.col_ref.field].transform(self.op)
        return pd.Series([self.apply(df)] * len(df), index=df.index)


def _make_agg(op):
    def fn(col_ref=None, by=None, **_):
        if col_ref is None and op != "count":
            raise ValueError(f"{op}() requires a col.field argument")
        return _AggFn(op, col_ref, by=by)
    fn.__name__ = op
    fn._accepts_deferred = True
    return fn

sum_   = _make_agg("sum")
mean_  = _make_agg("mean")
count_ = _make_agg("count")
min_   = _make_agg("min")
max_   = _make_agg("max")

sum_._pep_signature   = "sum(col.field) -> AggFn"
sum_.__doc__          = "Sum of a column. Use inside `collapse` or `add`."
mean_._pep_signature  = "mean(col.field) -> AggFn"
mean_.__doc__         = "Mean of a column. Use inside `collapse` or `add`."
count_._pep_signature = "count() -> AggFn"
count_.__doc__        = "Row count. Use inside `collapse`."
min_._pep_signature   = "min(col.field) -> AggFn"
min_.__doc__          = "Minimum of a column. Use inside `collapse` or `add`."
max_._pep_signature   = "max(col.field) -> AggFn"
max_.__doc__          = "Maximum of a column. Use inside `collapse` or `add`."


@pep_signature("collapse(by?: str, ...agg) -> List<Row>")
def collapse(data, _interp=None, _env=None, **kwargs) -> list:
    """Aggregate rows, optionally grouped by a field."""
    by = _eval_arg(kwargs.pop("by", None), _interp, _env)
    non_meta = {k: v for k, v in kwargs.items() if not k.startswith("_")}

    ctx = _as_ctx(data)
    rows = ctx.data if ctx is not None else _to_list(data)
    df = pd.DataFrame(rows)

    def _agg_group(sub_df):
        from ..interpreter import PmFunction
        row = {}
        for field, expr in non_meta.items():
            val = _unwrap(_eval_arg(expr, _interp, _env))
            if isinstance(val, _AggFn):
                row[field] = val.apply(sub_df)
            elif isinstance(val, PmFunction):
                from ..context import Context
                group_list = sub_df.to_dict(orient="records")
                result = _interp._call_pm_function(val, [group_list], {}, None, _env)
                rv = _unwrap(result)
                row[field] = rv.data if isinstance(rv, Context) else rv
            else:
                row[field] = val
        return row

    if by:
        out = []
        for key, sub in df.groupby(by):
            row = {by: key}
            row.update(_agg_group(sub))
            out.append(row)
        return ctx.with_data(out) if ctx is not None else out
    else:
        result = [_agg_group(df)]
        return ctx.with_data(result) if ctx is not None else result


def agg(data, _interp=None, _env=None, **kwargs) -> list:
    return collapse(data, _interp=_interp, _env=_env, **kwargs)


class _RankFn:
    def __init__(self, col_ref: ColRef, by=None, dir="asc"):
        self.col_ref = col_ref
        self.by = by
        self.dir = dir

    def broadcast(self, df: pd.DataFrame) -> pd.Series:
        ascending = self.dir != "desc"
        if self.by:
            return df.groupby(self.by)[self.col_ref.field].rank(ascending=ascending, method="min").astype(int)
        return df[self.col_ref.field].rank(ascending=ascending, method="min").astype(int)


class _RollingFn:
    def __init__(self, col_ref: ColRef, window: int, fn, by=None):
        self.col_ref = col_ref
        self.window = window
        self.fn = fn
        self.by = by

    def broadcast(self, df: pd.DataFrame) -> pd.Series:
        op = self.fn.__name__ if hasattr(self.fn, "__name__") else str(self.fn)
        if self.by:
            return df.groupby(self.by)[self.col_ref.field].transform(
                lambda s: s.rolling(self.window).agg(op)
            )
        return df[self.col_ref.field].rolling(self.window).agg(op)



@pep_signature('rank(col.field, by?: str, dir?: "asc" | "desc") -> RankFn')
def rank(col_ref, by=None, dir="asc", **_):
    """Rank rows by a column. Use inside `add`."""
    return _RankFn(col_ref, by=by, dir=dir)

rank._accepts_deferred = True


@pep_signature("rolling(col.field, window: Int, fn: AggFn, by?: str) -> RollingFn")
def rolling(col_ref, window, fn, by=None, **_):
    """Rolling window aggregation. Use inside `add`."""
    return _RollingFn(col_ref, int(window), fn, by=by)

rolling._accepts_deferred = True


@pep_signature("get(list: List<Any>, i: Int) -> Any")
def get(data, i, _interp=None, _env=None, **_):
    """Get element at index. Prefer `list[i]` syntax."""
    if isinstance(data, Ok): data = data.value
    i = _eval_arg(i, _interp, _env)
    if isinstance(i, Ok): i = i.value
    if isinstance(data, dict):
        if i not in data:
            raise KeyError(f"key '{i}' not found in object")
        return data[i]
    return _to_list(data)[int(i)]


@pep_signature("find(table: List<Row>, col: str, value: Any) -> Row | none")
def find(data, col, value, _interp=None, _env=None, **_):
    """Find the first row where `col` equals `value`. Returns `none` if not found.

Example: `find(cluster_stats, "cluster", it.cluster).n`"""
    col = _eval_arg(col, _interp, _env)
    value = _eval_arg(value, _interp, _env)
    if isinstance(value, Ok): value = value.value
    from ..context import Context
    rows = data.data if isinstance(data, Context) else _to_list(data)
    for row in rows:
        if row.get(col) == value:
            return row
    return None


def set_(data, i, v, _interp=None, _env=None, **_):
    items = list(_to_list(data))
    i = _eval_arg(i, _interp, _env)
    if isinstance(i, Ok): i = i.value
    v = _eval_arg(v, _interp, _env)
    if isinstance(v, Ok): v = v.value
    items[int(i)] = v
    return items


@pep_signature("first(list: List<Any>) -> Any")
def first(data, _interp=None, _env=None, **_):
    """Return the first element of a list, or none if empty."""
    rows = _to_list(data)
    return rows[0] if rows else None


@pep_signature("last(list: List<Any>) -> Any")
def last(data, _interp=None, _env=None, **_):
    """Return the last element of a list, or none if empty."""
    rows = _to_list(data)
    return rows[-1] if rows else None


@pep_signature("len(list: List<Any>) -> Int")
def length(data, _interp=None, _env=None, **_):
    """Number of elements in a list."""
    return len(_to_list(data))


@pep_signature("slice(list: List<Any>, start: Int, end: Int) -> List<Any>")
def slice_(data, start, end, _interp=None, _env=None, **_):
    """Slice a list from start to end (inclusive)."""
    items = _to_list(data)
    start, end = int(start), int(end)
    if start < 0 or end < 0:
        raise ValueError("slice indices must be non-negative")
    return items[start:end + 1]  # inclusive end


@pep_signature("concat(a: List<Any>, b: List<Any>, ...) -> List<Any>")
def concat(*args, _interp=None, _env=None, **_):
    """Concatenate two or more lists."""
    result = []
    for arg in args:
        result.extend(_unwrap(x) for x in _to_list(arg))
    return result


@pep_signature("unique(by: str) -> List<Row>")
def unique(data, by=None, _interp=None, _env=None, **_):
    """Remove duplicate rows, keeping the first occurrence. `by` specifies the field to deduplicate on."""
    by = _eval_arg(by, _interp, _env)
    ctx = _as_ctx(data)
    rows = ctx.data if ctx is not None else _to_list(data)
    if by is None:
        seen = set()
        result = []
        for row in rows:
            key = tuple(sorted(row.items())) if isinstance(row, dict) else row
            if key not in seen:
                seen.add(key)
                result.append(row)
        return ctx.with_data(result) if ctx is not None else result
    seen = set()
    result = []
    for row in rows:
        key = row.get(by)
        if key not in seen:
            seen.add(key)
            result.append(row)
    return ctx.with_data(result) if ctx is not None else result


@pep_signature("str(value: Any) -> str")
def to_str(value, _interp=None, _env=None, **_):
    """Convert a value to a string."""
    v = _unwrap(_eval_arg(value, _interp, _env))
    return builtins_str(v)


@pep_signature("float(value: Any) -> Num")
def to_float(value, _interp=None, _env=None, **_):
    """Convert a value to a float."""
    v = _unwrap(_eval_arg(value, _interp, _env))
    return builtins_float(v)


@pep_signature("int(value: Any) -> Int")
def to_int(value, _interp=None, _env=None, **_):
    """Convert a value to an integer. Returns none for NaN or NA values."""
    v = _unwrap(_eval_arg(value, _interp, _env))
    if v is None:
        return None
    try:
        import math
        if isinstance(v, float) and math.isnan(v):
            return None
    except Exception:
        pass
    try:
        # Handle pandas NA
        import pandas as pd
        if v is pd.NA:
            return None
    except Exception:
        pass
    return builtins_int(v)


for _fn in (filter_, map_, mapi, add, select, sort, reduce, each, collapse, recover, sum_, mean_, count_, min_, max_):
    _fn._accepts_deferred = True


def build_core_env() -> dict:
    return {
        "load":   load,
        "save":   save,
        "filter": filter_,
        "map":    map_,
        "mapi":   mapi,
        "add":    add,
        "drop":   drop,
        "select": select,
        "rename": rename,
        "sort":   sort,
        "reduce": reduce,
        "each":     each,
        "join":     join,
        "cross":    cross,
        "collapse": collapse,
        "sum":      sum_,
        "mean":     mean_,
        "count":    count_,
        "min":      min_,
        "max":      max_,
        "print":   print_,
        "halt":    halt,
        "recover": recover,
        "get":    get,
        "first":  first,
        "last":   last,
        "find":   find,
        "set":    set_,
        "len":    length,
        "take":    take,
        "rank":    rank,
        "rolling": rolling,
        "concat":  concat,
        "slice":   slice_,
        "unique":  unique,
        "str":     to_str,
        "float":   to_float,
        "int":     to_int,
    }
