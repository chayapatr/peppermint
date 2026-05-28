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
    """Load a CSV or JSON file as a list of rows."""
    try:
        from ..context import Context
        path = _eval_arg(path, _interp, _env)
        if path.endswith(".json"):
            with open(path) as f:
                data = json.load(f)
            rows = data if isinstance(data, list) else [data]
        else:
            df = pd.read_csv(path)
            rows = df.to_dict(orient="records")
        return Ok(Context(data=rows))
    except Exception as e:
        return Err(str(e))


@pep_signature("save(path: str) -> Ok<Context> | Err")
def save(data, path, _interp=None, _env=None, **_) -> Ok | Err:
    """Write a list of rows to a CSV or JSON file."""
    try:
        path = _eval_arg(path, _interp, _env)
        rows = _to_list(data)
        df = pd.DataFrame(rows)
        if path.endswith(".json"):
            df.to_json(path, orient="records", indent=2)
        else:
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


@pep_signature("map(expr: Expr, concurrent: Int?) -> List<Any>")
def map_(data, transform, concurrent=None, _interp=None, _env=None, **_) -> list:
    """Transform every element. `it` refers to the current element. `concurrent: N` runs in a thread pool with N workers."""
    concurrent = int(_eval_arg(concurrent, _interp, _env)) if concurrent is not None else None
    items = _to_list(data)
    fn = _interp.make_row_fn(transform, _env)
    if concurrent:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=concurrent) as pool:
            return list(pool.map(lambda item: _unwrap(fn(item)), items))
    return [_unwrap(fn(item)) for item in items]


@pep_signature("mapi(expr: Expr, concurrent: Int?) -> List<Any>")

def mapi(data, transform, concurrent=None, _interp=None, _env=None, **_) -> list:
    """map with index. `it` is `{ idx: Int, val: Any }`. `concurrent: N` runs in a thread pool with N workers."""
    concurrent = int(_eval_arg(concurrent, _interp, _env)) if concurrent is not None else None
    items = _to_list(data)
    fn = _interp.make_row_fn(transform, _env)
    indexed = [{"idx": i, "val": x} for i, x in enumerate(items)]
    if concurrent:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=concurrent) as pool:
            return list(pool.map(lambda item: _unwrap(fn(item)), indexed))
    return [_unwrap(fn(item)) for item in indexed]


@pep_signature("add(field: Expr, concurrent: Int?, retry: Int?) -> List<Row>")
def add(data, _interp=None, _env=None, **kwargs) -> list:
    """Add a new field to every row. Use `it.field` or `col.field` expressions. `concurrent: N` runs in a thread pool. `retry: N` retries on failure before writing `none`."""
    import sys
    concurrent = kwargs.pop("concurrent", None)
    retry      = kwargs.pop("retry", None)
    if concurrent is not None:
        concurrent = int(_eval_arg(concurrent, _interp, _env))
    if retry is not None:
        retry = int(_eval_arg(retry, _interp, _env))

    non_meta = {k: v for k, v in kwargs.items() if k not in ("_interp", "_env", "_block", "_depth")}
    if len(non_meta) != 1:
        raise ValueError("add() requires exactly one keyword argument: the new field name")
    field, expr = next(iter(non_meta.items()))

    ctx = _as_ctx(data)
    rows = ctx.data if ctx is not None else _to_list(data)

    # Evaluate the expression to check if it's a column-level operation
    val = _unwrap(_eval_arg(expr, _interp, _env))
    if hasattr(val, "broadcast"):
        df = pd.DataFrame(rows)
        series = val.broadcast(df)
        out = df.copy()
        out[field] = series.values
        result = out.to_dict(orient="records")
        return ctx.with_data(result) if ctx is not None else result

    fn = _interp.make_row_fn(expr, _env)
    failures = [0]

    def _run(row):
        attempts = retry + 1 if retry else 1
        last_exc = None
        for _ in range(attempts):
            try:
                return _unwrap(fn(row))
            except Exception as e:
                last_exc = e
        failures[0] += 1
        print(f"add({field}): failed after {attempts} attempt(s): {last_exc}", file=sys.stderr)
        return None

    if concurrent:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=concurrent) as pool:
            values = list(pool.map(_run, rows))
    else:
        values = [_run(row) for row in rows]

    if failures[0]:
        print(f"add({field}): {failures[0]}/{len(rows)} rows failed, written as none", file=sys.stderr)

    result = [{**row, field: v} for row, v in zip(rows, values)]
    return ctx.with_data(result) if ctx is not None else result


@pep_signature("take(n: Int) -> List<Row>")
def take(data, n, _interp=None, _env=None, **_) -> list:
    """Keep the first n rows."""
    n = int(_eval_arg(n, _interp, _env))
    ctx = _as_ctx(data)
    if ctx is not None:
        return ctx.with_data(ctx.data[:n])
    return _to_list(data)[:n]


@pep_signature("drop(field: str) -> List<Row>")
def drop(data, field, _interp=None, _env=None, **_) -> list:
    """Remove a field from every row."""
    field = _eval_arg(field, _interp, _env)
    ctx = _as_ctx(data)
    rows = ctx.data if ctx is not None else _to_list(data)
    result = [{k: v for k, v in row.items() if k != field} for row in rows]
    return ctx.with_data(result) if ctx is not None else result


@pep_signature("select(fields: str...) -> List<Row>")
def select(data, *fields, _interp=None, _env=None, **_) -> list:
    """Keep only the specified fields."""
    fields = [_eval_arg(f, _interp, _env) for f in fields]
    ctx = _as_ctx(data)
    rows = ctx.data if ctx is not None else _to_list(data)
    result = [{f: row[f] for f in fields if f in row} for row in rows]
    return ctx.with_data(result) if ctx is not None else result


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
def each(data, by=None, _block=None, _interp=None, _env=None, _depth=0, **kwargs):
    """Run a sub-pipe for each group. Results are concatenated, or original table returned for side effects.
Accepts a block `{ |> ... }` or a lambda `x -> x |> ...` as the sub-pipe."""
    from ..ast_nodes import Pipe, Literal
    from ..context import Context

    # Lambda form: each(by: "col", x -> x |> ...)
    fn_arg = kwargs.get("fn") or (list(kwargs.values())[0] if kwargs else None)
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
    print(val)
    return val


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
                group_list = sub_df.to_dict(orient="records")
                result = _interp._call_pm_function(val, [group_list], {}, None, _env)
                row[field] = _unwrap(result)
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


def set_(data, i, v, _interp=None, _env=None, **_):
    items = list(_to_list(data))
    i = _eval_arg(i, _interp, _env)
    if isinstance(i, Ok): i = i.value
    v = _eval_arg(v, _interp, _env)
    if isinstance(v, Ok): v = v.value
    items[int(i)] = v
    return items


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
    """Convert a value to an integer."""
    v = _unwrap(_eval_arg(value, _interp, _env))
    return builtins_int(v)


for _fn in (filter_, map_, mapi, add, sort, reduce, each, collapse, sum_, mean_, count_, min_, max_):
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
        "collapse": collapse,
        "sum":      sum_,
        "mean":     mean_,
        "count":    count_,
        "min":      min_,
        "max":      max_,
        "print":  print_,
        "get":    get,
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
