from __future__ import annotations
import json
from typing import Any
import pandas as pd
from ..interpreter import Ok, Err, PmFunction, ColRef


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
    if isinstance(data, list):
        return data
    raise TypeError(f"expected a List, got {type(data).__name__}")


def _unwrap(v):
    return v.value if isinstance(v, Ok) else v


# --- IO — these return Ok/Err ---

@pep_signature("load(path: str) -> Ok<List<Row>> | Err")
def load(path, _interp=None, _env=None, **_) -> Ok | Err:
    """Load a CSV or JSON file as a list of rows."""
    try:
        path = _eval_arg(path, _interp, _env)
        if path.endswith(".json"):
            with open(path) as f:
                data = json.load(f)
            rows = data if isinstance(data, list) else [data]
        else:
            df = pd.read_csv(path)
            rows = df.to_dict(orient="records")
        return Ok(rows)
    except Exception as e:
        return Err(str(e))


@pep_signature("save(path: str) -> Ok<List<Row>> | Err")
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
    items = _to_list(data)
    fn = _interp.make_row_fn(pred, _env)
    return [item for item in items if _unwrap(fn(item))]


@pep_signature("map(expr: Expr) -> List<Any>")
def map_(data, transform, _interp=None, _env=None, **_) -> list:
    """Transform every element. `it` refers to the current element."""
    items = _to_list(data)
    fn = _interp.make_row_fn(transform, _env)
    return [_unwrap(fn(item)) for item in items]


@pep_signature("mapi(expr: Expr) -> List<Any>")
def mapi(data, transform, _interp=None, _env=None, **_) -> list:
    """map with index. `it` is `{ idx: Int, value: Any }`."""
    items = _to_list(data)
    fn = _interp.make_row_fn(transform, _env)
    return [_unwrap(fn({"idx": i, "value": x})) for i, x in enumerate(items)]


@pep_signature("add(field: Expr, concurrent: Int?) -> List<Row>")
def add(data, _interp=None, _env=None, **kwargs) -> list:
    """Add a new field to every row. Use `it.field` or `col.field` expressions. `concurrent: N` runs the expression in a thread pool with N workers."""
    concurrent = kwargs.pop("concurrent", None)
    if concurrent is not None:
        concurrent = int(_eval_arg(concurrent, _interp, _env))

    non_meta = {k: v for k, v in kwargs.items() if not k.startswith("_")}
    if len(non_meta) != 1:
        raise ValueError("add() requires exactly one keyword argument: the new field name")
    field, expr = next(iter(non_meta.items()))

    # Evaluate the expression to check if it's a column-level operation
    val = _unwrap(_eval_arg(expr, _interp, _env))
    if isinstance(val, (_AggFn, _RankFn, _RollingFn)):
        df = pd.DataFrame(_to_list(data))
        series = val.broadcast(df)
        rows = df.copy()
        rows[field] = series.values
        return rows.to_dict(orient="records")

    fn = _interp.make_row_fn(expr, _env)
    rows = _to_list(data)

    if concurrent:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=concurrent) as pool:
            values = list(pool.map(lambda row: _unwrap(fn(row)), rows))
        return [{**row, field: val} for row, val in zip(rows, values)]

    return [{**row, field: _unwrap(fn(row))} for row in rows]


@pep_signature("take(n: Int) -> List<Row>")
def take(data, n, _interp=None, _env=None, **_) -> list:
    """Keep the first n rows."""
    n = int(_eval_arg(n, _interp, _env))
    return _to_list(data)[:n]


@pep_signature("drop(field: str) -> List<Row>")
def drop(data, field, _interp=None, _env=None, **_) -> list:
    """Remove a field from every row."""
    field = _eval_arg(field, _interp, _env)
    return [{k: v for k, v in row.items() if k != field} for row in _to_list(data)]


@pep_signature("select(fields: str...) -> List<Row>")
def select(data, *fields, _interp=None, _env=None, **_) -> list:
    """Keep only the specified fields."""
    fields = [_eval_arg(f, _interp, _env) for f in fields]
    return [{f: row[f] for f in fields if f in row} for row in _to_list(data)]


@pep_signature('rename(old: new) -> List<Row>')
def rename(data, _interp=None, _env=None, **kwargs) -> list:
    """Rename a field. Pass as keyword: `rename(old_name: "new_name")`."""
    non_meta = {k: v for k, v in kwargs.items() if not k.startswith("_")}
    if len(non_meta) != 1:
        raise ValueError("rename() requires exactly one keyword argument: old: new")
    old, new_expr = next(iter(non_meta.items()))
    new = _eval_arg(new_expr, _interp, _env)
    return [{(new if k == old else k): v for k, v in row.items()} for row in _to_list(data)]


@pep_signature('sort(by: str, dir?: "asc" | "desc") -> List<Row>')
def sort(data, by=None, dir=None, _interp=None, _env=None, **_) -> list:
    """Sort rows by a field. `dir` defaults to `"asc"`."""
    by = _eval_arg(by, _interp, _env)
    dir = _eval_arg(dir, _interp, _env) if dir is not None else "asc"
    return sorted(_to_list(data), key=lambda r: r.get(by) if isinstance(r, dict) else r, reverse=(dir == "desc"))


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
def each(data, by=None, _block=None, _interp=None, _env=None, **_):
    """Run a sub-pipe for each group. Results are concatenated, or original table returned for side effects."""
    from ..ast_nodes import Pipe, Literal

    by = _eval_arg(by, _interp, _env)
    if by is None:
        raise ValueError("each() requires 'by' argument")
    if _block is None:
        raise ValueError("each() requires a sub-pipe: |> step or { |> step }")

    rows = _to_list(data)
    groups: dict = {}
    for row in rows:
        key = row.get(by)
        groups.setdefault(key, []).append(row)

    all_results = []
    is_side_effect = None

    for key, group_rows in groups.items():
        pipe = Pipe(steps=[Literal(group_rows)] + list(_block))
        result = _interp.eval_pipe(pipe, _env)
        if isinstance(result, Err):
            return result
        value = result.value if isinstance(result, Ok) else result
        if isinstance(value, list):
            if is_side_effect is None:
                is_side_effect = False
            all_results.extend([{by: key, **row} for row in value])
        else:
            is_side_effect = True

    if is_side_effect:
        return rows
    return all_results


@pep_signature("join(other: List<Row>, on: str) -> List<Row>")
def join(data, other, on=None, _interp=None, _env=None, **_) -> list:
    """Inner join on a shared key field. Rows with no match are dropped."""
    on = _eval_arg(on, _interp, _env)
    other_rows = _to_list(other)
    index = {row[on]: row for row in other_rows if on in row}
    return [{**row, **index[row.get(on)]} for row in _to_list(data) if row.get(on) in index]


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

    df = pd.DataFrame(_to_list(data))

    def _agg_group(sub_df):
        row = {}
        for field, expr in non_meta.items():
            val = _unwrap(_eval_arg(expr, _interp, _env))
            if isinstance(val, _AggFn):
                row[field] = val.apply(sub_df)
            else:
                row[field] = val
        return row

    if by:
        rows = []
        for key, sub in df.groupby(by):
            row = {by: key}
            row.update(_agg_group(sub))
            rows.append(row)
        return rows
    else:
        return [_agg_group(df)]


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
    }
