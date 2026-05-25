from __future__ import annotations
import json
from typing import Any
import pandas as pd
from ..interpreter import Ok, Err, PmFunction, ColRef


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

def load(path, _interp=None, _env=None, **_) -> Ok | Err:
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


def save(data, path, _interp=None, _env=None, **_) -> Ok | Err:
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

def filter_(data, pred, _interp=None, _env=None, **_) -> list:
    items = _to_list(data)
    fn = _interp.make_row_fn(pred, _env)
    return [item for item in items if _unwrap(fn(item))]


def map_(data, transform, _interp=None, _env=None, **_) -> list:
    items = _to_list(data)
    fn = _interp.make_row_fn(transform, _env)
    return [_unwrap(fn(item)) for item in items]


def mapi(data, transform, _interp=None, _env=None, **_) -> list:
    """map with index — it is {idx: i, value: x}"""
    items = _to_list(data)
    fn = _interp.make_row_fn(transform, _env)
    return [_unwrap(fn({"idx": i, "value": x})) for i, x in enumerate(items)]


def add(data, _interp=None, _env=None, **kwargs) -> list:
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
    return [{**row, field: _unwrap(fn(row))} for row in _to_list(data)]


def take(data, n, _interp=None, _env=None, **_) -> list:
    n = int(_eval_arg(n, _interp, _env))
    return _to_list(data)[:n]


def drop(data, field, _interp=None, _env=None, **_) -> list:
    field = _eval_arg(field, _interp, _env)
    return [{k: v for k, v in row.items() if k != field} for row in _to_list(data)]


def select(data, *fields, _interp=None, _env=None, **_) -> list:
    fields = [_eval_arg(f, _interp, _env) for f in fields]
    return [{f: row[f] for f in fields if f in row} for row in _to_list(data)]


def rename(data, _interp=None, _env=None, **kwargs) -> list:
    non_meta = {k: v for k, v in kwargs.items() if not k.startswith("_")}
    if len(non_meta) != 1:
        raise ValueError("rename() requires exactly one keyword argument: old: new")
    old, new_expr = next(iter(non_meta.items()))
    new = _eval_arg(new_expr, _interp, _env)
    return [{(new if k == old else k): v for k, v in row.items()} for row in _to_list(data)]


def sort(data, by=None, dir=None, _interp=None, _env=None, **_) -> list:
    by = _eval_arg(by, _interp, _env)
    dir = _eval_arg(dir, _interp, _env) if dir is not None else "asc"
    return sorted(_to_list(data), key=lambda r: r.get(by) if isinstance(r, dict) else r, reverse=(dir == "desc"))


def reduce(data, init, fn, _interp=None, _env=None, **_) -> Any:
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



def each(data, by=None, _block=None, _interp=None, _env=None, **_):
    """Apply a sub-pipe to each group independently.

    If the sub-pipe produces a table, results are concatenated and returned.
    If the sub-pipe is a pure side effect (viz, save, print), the original table is returned.
    """
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


def join(data, other, on=None, _interp=None, _env=None, **_) -> list:
    on = _eval_arg(on, _interp, _env)
    other_rows = _to_list(other)
    index = {row[on]: row for row in other_rows if on in row}
    return [{**row, **index[row.get(on)]} for row in _to_list(data) if row.get(on) in index]


def print_(data, _interp=None, _env=None, **_):
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


def collapse(data, _interp=None, _env=None, **kwargs) -> list:
    """Aggregate rows, optionally grouped by a field.

    collapse(by: "dept", avg: mean(col.salary), n: count())
    collapse(avg: mean(col.salary))  -- one row total
    """
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


def rank(col_ref, by=None, dir="asc", **_):
    return _RankFn(col_ref, by=by, dir=dir)

rank._accepts_deferred = True


def rolling(col_ref, window, fn, by=None, **_):
    return _RollingFn(col_ref, int(window), fn, by=by)

rolling._accepts_deferred = True


def get(data, i, _interp=None, _env=None, **_):
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


def length(data, _interp=None, _env=None, **_):
    return len(_to_list(data))


def slice_(data, start, end, _interp=None, _env=None, **_):
    items = _to_list(data)
    start, end = int(start), int(end)
    if start < 0 or end < 0:
        raise ValueError("slice indices must be non-negative")
    return items[start:end + 1]  # inclusive end


def concat(*args, _interp=None, _env=None, **_):
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
