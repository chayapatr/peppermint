from __future__ import annotations
import json
from typing import Any
import pandas as pd
from ..interpreter import Ok, Err, ListValue
from ..ast_nodes import StrLit, IntLit, FloatLit, BoolLit, NoneLit, Ident


def _infer_schema(rows: list[dict]) -> dict[str, type]:
    if not rows:
        return {}
    return {k: type(v) for k, v in rows[0].items()}


def _list_value(rows: list[dict]) -> ListValue:
    return ListValue(rows=rows, schema=_infer_schema(rows))


def _eval_arg(arg, interp, env):
    """Evaluate a plain (non-row-dependent) AST argument."""
    if interp and hasattr(arg, '__class__') and hasattr(interp, 'eval'):
        try:
            return interp.eval(arg, env)
        except Exception:
            return arg
    return arg


def load(path, _interp=None, _env=None, **_) -> Ok | Err:
    try:
        path = _eval_arg(path, _interp, _env)
        if path.endswith(".json"):
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, list):
                rows = data
            else:
                rows = [data]
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


def filter_(data: ListValue, pred, _interp=None, _env=None, **_) -> Ok | Err:
    try:
        fn = _interp.make_row_fn(pred, _env)
        rows = []
        for row in data.rows:
            result = fn(row)
            result = result.value if hasattr(result, "value") else result
            if result:
                rows.append(row)
        return Ok(_list_value(rows))
    except Exception as e:
        return Err(str(e))


def map_(data: ListValue, transform, _interp=None, _env=None, **_) -> Ok | Err:
    try:
        fn = _interp.make_row_fn(transform, _env)
        rows = []
        for row in data.rows:
            result = fn(row)
            result = result.value if hasattr(result, "value") else result
            if not isinstance(result, dict):
                raise ValueError(f"map transform must return an object, got {type(result).__name__}")
            rows.append(result)
        return Ok(_list_value(rows))
    except Exception as e:
        return Err(str(e))


def add(data: ListValue, _interp=None, _env=None, **kwargs) -> Ok | Err:
    try:
        non_meta = {k: v for k, v in kwargs.items() if not k.startswith("_")}
        if len(non_meta) != 1:
            return Err("add() requires exactly one keyword argument: the new field name")
        field, expr = next(iter(non_meta.items()))
        fn = _interp.make_row_fn(expr, _env)
        rows = []
        for row in data.rows:
            val = fn(row)
            val = val.value if hasattr(val, "value") else val
            rows.append({**row, field: val})
        return Ok(_list_value(rows))
    except Exception as e:
        return Err(str(e))


def drop(data: ListValue, field, _interp=None, _env=None, **_) -> Ok | Err:
    try:
        field = _eval_arg(field, _interp, _env)
        rows = [{k: v for k, v in row.items() if k != field} for row in data.rows]
        return Ok(_list_value(rows))
    except Exception as e:
        return Err(str(e))


def select(data: ListValue, *fields, _interp=None, _env=None, **_) -> Ok | Err:
    try:
        fields = [_eval_arg(f, _interp, _env) for f in fields]
        rows = [{f: row[f] for f in fields if f in row} for row in data.rows]
        return Ok(_list_value(rows))
    except Exception as e:
        return Err(str(e))


def rename(data: ListValue, _interp=None, _env=None, **kwargs) -> Ok | Err:
    try:
        non_meta = {k: v for k, v in kwargs.items() if not k.startswith("_")}
        if len(non_meta) != 1:
            return Err("rename() requires exactly one keyword argument: old: new")
        old, new_expr = next(iter(non_meta.items()))
        new = _eval_arg(new_expr, _interp, _env)
        rows = [{(new if k == old else k): v for k, v in row.items()} for row in data.rows]
        return Ok(_list_value(rows))
    except Exception as e:
        return Err(str(e))


def sort(data: ListValue, by=None, dir=None, _interp=None, _env=None, **_) -> Ok | Err:
    try:
        by = _eval_arg(by, _interp, _env)
        dir = _eval_arg(dir, _interp, _env) if dir is not None else "asc"
        rows = sorted(data.rows, key=lambda r: r.get(by), reverse=(dir == "desc"))
        return Ok(_list_value(rows))
    except Exception as e:
        return Err(str(e))


def reduce(data: ListValue, init, fn, _interp=None, _env=None, **_) -> Ok | Err:
    try:
        import functools
        init = _eval_arg(init, _interp, _env)
        from ..interpreter import PmFunction
        pm_fn = _interp.eval(fn, _env) if _interp else fn

        def apply(acc, row):
            if isinstance(pm_fn, PmFunction):
                result = _interp._call_pm_function(pm_fn, [acc, row], {}, None, _env)
                return result.value if hasattr(result, "value") else result
            return pm_fn(acc, row)

        result = functools.reduce(apply, data.rows, init)
        return Ok(result)
    except Exception as e:
        return Err(str(e))


def group(data: ListValue, by=None, _block=None, _interp=None, _env=None, **_) -> Ok | Err:
    try:
        if by is None:
            return Err("group() requires 'by' argument")
        by = _eval_arg(by, _interp, _env)
        if _block is None:
            return Err("group() requires a block { |> ... }")

        groups: dict[str, list[dict]] = {}
        for row in data.rows:
            key = str(row.get(by, ""))
            groups.setdefault(key, []).append(row)

        from ..ast_nodes import Pipe
        all_rows = []
        result_schema = None
        for key, rows in groups.items():
            group_data = ListValue(rows=rows, schema=_infer_schema(rows))
            # Run block as a sub-pipe
            pipe_node = Pipe(steps=[group_data] + list(_block))
            result = _interp.eval(pipe_node, _env)
            result = result.value if hasattr(result, "value") else result
            if not isinstance(result, ListValue):
                return Err(f"group sub-pipe must produce a List, got {type(result).__name__}")
            if result_schema is None:
                result_schema = set(result.schema.keys())
            elif set(result.schema.keys()) != result_schema:
                return Err("group: all groups must produce the same schema")
            all_rows.extend(result.rows)

        return Ok(_list_value(all_rows))
    except Exception as e:
        return Err(str(e))


def join(data: ListValue, other: ListValue, on=None, _interp=None, _env=None, **_) -> Ok | Err:
    try:
        on = _eval_arg(on, _interp, _env)
        index = {row[on]: row for row in other.rows if on in row}
        rows = []
        for row in data.rows:
            key = row.get(on)
            if key in index:
                rows.append({**row, **index[key]})
        return Ok(_list_value(rows))
    except Exception as e:
        return Err(str(e))


def print_(data, _interp=None, _env=None, **_) -> Ok:
    val = _eval_arg(data, _interp, _env) if not isinstance(data, ListValue) else data
    print(val)
    return Ok(val)


def build_core_env() -> dict:
    return {
        "load":   load,
        "save":   save,
        "filter": filter_,
        "map":    map_,
        "add":    add,
        "drop":   drop,
        "select": select,
        "rename": rename,
        "sort":   sort,
        "reduce": reduce,
        "group":  group,
        "join":   join,
        "print":  print_,
    }
