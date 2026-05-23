"""
Peppermint math stdlib — pure Python, uses bridge for type conversion.
"""
import math
import statistics
from ..bridge import ok, err, to_python, from_python


def log(x, **_):
    try:
        return ok(math.log(to_python(x)))
    except Exception as e:
        return err(str(e))


def mean(values, **_):
    try:
        vals = to_python(values)
        if not hasattr(vals, "__iter__"):
            return err("mean() requires a list")
        return ok(statistics.mean(vals))
    except Exception as e:
        return err(str(e))


def std(values, **_):
    try:
        vals = to_python(values)
        if not hasattr(vals, "__iter__"):
            return err("std() requires a list")
        return ok(statistics.stdev(vals))
    except Exception as e:
        return err(str(e))


def sqrt(x, **_):
    try:
        return ok(math.sqrt(to_python(x)))
    except Exception as e:
        return err(str(e))


def round_(x, **_):
    try:
        return ok(round(to_python(x)))
    except Exception as e:
        return err(str(e))


def build_math_env() -> dict:
    return {
        "log":   log,
        "mean":  mean,
        "std":   std,
        "sqrt":  sqrt,
        "round": round_,
    }
