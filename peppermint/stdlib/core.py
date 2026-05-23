from __future__ import annotations
import json
from typing import Any
import pandas as pd
from ..interpreter import Ok, Err, ListValue, PmFunction


def _infer_schema(rows: list) -> dict[str, type]:
    if not rows or not isinstance(rows[0], dict):
        return {}
    return {k: type(v) for k, v in rows[0].items()}


def _list_value(rows: list[dict]) -> ListValue:
    return ListValue(rows=rows, schema=_infer_schema(rows))


def _eval_arg(arg, interp, env):
    if interp and hasattr(arg, '__class__') and hasattr(interp, 'eval'):
        try:
            return interp.eval(arg, env)
        except Exception:
            return arg
    return arg


def _to_list(data) -> tuple[list, bool]:
    if isinstance(data, Ok):
        return _to_list(data.value)
    if isinstance(data, ListValue):
        return data.rows, True
    if isinstance(data, list):
        return data, False
    raise TypeError(f"expected a List, got {type(data).__name__}")


def _from_list(items: list, is_object_list: bool):
    return _list_value(items)


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
        return Ok(_list_value(rows))
    except Exception as e:
        return Err(str(e))


def save(data: ListValue, path, _interp=None, _env=None, **_) -> Ok | Err:
    try:
        path = _eval_arg(path, _interp, _env)
        df = pd.DataFrame(data.rows)
        if path.endswith(".json"):
            df.to_json(path, orient="records", indent=2)
        else:
            df.to_csv(path, index=False)
        return Ok(data)
    except Exception as e:
        return Err(str(e))


# --- Pure functions — return plain values ---

def filter_(data, pred, _interp=None, _env=None, **_) -> ListValue | list:
    items, is_obj = _to_list(data)
    fn = _interp.make_row_fn(pred, _env)
    out = [item for item in items if _unwrap(fn(item))]
    return _from_list(out, is_obj)


def map_(data, transform, _interp=None, _env=None, **_) -> ListValue:
    items, _ = _to_list(data)
    fn = _interp.make_row_fn(transform, _env)
    out = [_unwrap(fn(item)) for item in items]
    return _from_list(out, False)


def mapi(data, transform, _interp=None, _env=None, **_) -> ListValue:
    """map with index — it is {idx: i, value: x}"""
    items, _ = _to_list(data)
    fn = _interp.make_row_fn(transform, _env)
    out = [_unwrap(fn({"idx": i, "value": x})) for i, x in enumerate(items)]
    return _from_list(out, False)


def add(data: ListValue, _interp=None, _env=None, **kwargs) -> ListValue:
    non_meta = {k: v for k, v in kwargs.items() if not k.startswith("_")}
    if len(non_meta) != 1:
        raise ValueError("add() requires exactly one keyword argument: the new field name")
    field, expr = next(iter(non_meta.items()))
    fn = _interp.make_row_fn(expr, _env)
    rows = [{**row, field: _unwrap(fn(row))} for row in data.rows]
    return _list_value(rows)


def drop(data: ListValue, field, _interp=None, _env=None, **_) -> ListValue:
    field = _eval_arg(field, _interp, _env)
    rows = [{k: v for k, v in row.items() if k != field} for row in data.rows]
    return _list_value(rows)


def select(data: ListValue, *fields, _interp=None, _env=None, **_) -> ListValue:
    fields = [_eval_arg(f, _interp, _env) for f in fields]
    rows = [{f: row[f] for f in fields if f in row} for row in data.rows]
    return _list_value(rows)


def rename(data: ListValue, _interp=None, _env=None, **kwargs) -> ListValue:
    non_meta = {k: v for k, v in kwargs.items() if not k.startswith("_")}
    if len(non_meta) != 1:
        raise ValueError("rename() requires exactly one keyword argument: old: new")
    old, new_expr = next(iter(non_meta.items()))
    new = _eval_arg(new_expr, _interp, _env)
    rows = [{(new if k == old else k): v for k, v in row.items()} for row in data.rows]
    return _list_value(rows)


def sort(data: ListValue, by=None, dir=None, _interp=None, _env=None, **_) -> ListValue:
    by = _eval_arg(by, _interp, _env)
    dir = _eval_arg(dir, _interp, _env) if dir is not None else "asc"
    rows = sorted(data.rows, key=lambda r: r.get(by), reverse=(dir == "desc"))
    return _list_value(rows)


def reduce(data, init, fn, _interp=None, _env=None, **_) -> Any:
    import functools
    items, _ = _to_list(data)
    init = _eval_arg(init, _interp, _env)
    pm_fn = _interp.eval(fn, _env) if _interp else fn

    def apply(acc, item):
        if isinstance(pm_fn, PmFunction):
            return _unwrap(_interp._call_pm_function(pm_fn, [acc, item], {}, None, _env))
        return pm_fn(acc, item)

    return functools.reduce(apply, items, init)


def group(data: ListValue, by=None, _block=None, _interp=None, _env=None, **_) -> ListValue:
    if by is None:
        raise ValueError("group() requires 'by' argument")
    by = _eval_arg(by, _interp, _env)
    if _block is None:
        raise ValueError("group() requires a block { |> ... }")

    from ..ast_nodes import Pipe, Literal

    groups: dict[str, list[dict]] = {}
    for row in data.rows:
        key = str(row.get(by, ""))
        groups.setdefault(key, []).append(row)

    all_rows = []
    for key, rows in groups.items():
        group_data = ListValue(rows=rows, schema=_infer_schema(rows))
        pipe = Pipe(steps=[Literal(group_data)] + list(_block))
        result = _interp.eval_pipe(pipe, _env)
        if isinstance(result, Err):
            return result  # propagate sub-pipe error up
        value = result.value
        if not isinstance(value, ListValue):
            raise TypeError(f"group sub-pipe must produce a List, got {type(value).__name__}")
        all_rows.extend([{by: key, **row} for row in value.rows])

    return _list_value(all_rows)


def join(data: ListValue, other: ListValue, on=None, _interp=None, _env=None, **_) -> ListValue:
    on = _eval_arg(on, _interp, _env)
    index = {row[on]: row for row in other.rows if on in row}
    rows = [{**row, **index[row.get(on)]} for row in data.rows if row.get(on) in index]
    return _list_value(rows)


def print_(data, _interp=None, _env=None, **_):
    val = _eval_arg(data, _interp, _env) if not isinstance(data, ListValue) else data
    print(val)
    return val


# --- Aggregation ---

class _AggFn:
    def __init__(self, name, expr):
        self.name = name
        self.expr = expr


def sum_(expr=None, **_):  return _AggFn("sum", expr)
def mean_(expr=None, **_): return _AggFn("mean", expr)
def count_(**_):            return _AggFn("count", None)
def min_(expr=None, **_):  return _AggFn("min", expr)
def max_(expr=None, **_):  return _AggFn("max", expr)


def _apply_agg(fn: _AggFn, items: list, interp, env) -> Any:
    if fn.name == "count":
        return len(items)
    row_fn = interp.make_row_fn(fn.expr, env)
    vals = [_unwrap(row_fn(item)) for item in items]
    if fn.name == "sum":  return sum(vals)
    if fn.name == "mean": return sum(vals) / len(vals) if vals else 0
    if fn.name == "min":  return min(vals)
    if fn.name == "max":  return max(vals)


def agg(data, _interp=None, _env=None, **kwargs) -> ListValue | dict:
    items, _ = _to_list(data)
    non_meta = {k: v for k, v in kwargs.items() if not k.startswith("_")}
    result = {}
    for field, expr in non_meta.items():
        fn = _eval_arg(expr, _interp, _env)
        fn = _unwrap(fn)
        if isinstance(fn, _AggFn):
            result[field] = _apply_agg(fn, items, _interp, _env)
        else:
            result[field] = fn
    if isinstance(data, ListValue):
        return _list_value([result])
    return result


def get(data, i, _interp=None, _env=None, **_):
    items, _ = _to_list(data)
    i = _eval_arg(i, _interp, _env)
    if isinstance(i, Ok): i = i.value
    return items[int(i)]


def set_(data, i, v, _interp=None, _env=None, **_):
    items, _ = _to_list(data)
    i = _eval_arg(i, _interp, _env)
    if isinstance(i, Ok): i = i.value
    v = _eval_arg(v, _interp, _env)
    if isinstance(v, Ok): v = v.value
    new = list(items)
    new[int(i)] = v
    return _from_list(new, False)


def length(data, _interp=None, _env=None, **_):
    items, _ = _to_list(data)
    return len(items)


def concat(*args, _interp=None, _env=None, **_):
    result = []
    for arg in args:
        items, _ = _to_list(arg)
        result.extend(items)
    return result


for _fn in (filter_, map_, mapi, add, sort, reduce, group, agg, sum_, mean_, count_, min_, max_):
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
        "group":  group,
        "join":   join,
        "agg":    agg,
        "sum":    sum_,
        "mean":   mean_,
        "count":  count_,
        "min":    min_,
        "max":    max_,
        "print":  print_,
        "get":    get,
        "set":    set_,
        "length": length,
        "concat": concat,
    }
