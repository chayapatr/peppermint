import math
import statistics
from ..interpreter import Ok, Err


def log(x, **_):
    try:
        return Ok(math.log(x))
    except Exception as e:
        return Err(str(e))


def mean(values, **_):
    try:
        if hasattr(values, "__iter__"):
            return Ok(statistics.mean(values))
        return Err("mean() requires a list")
    except Exception as e:
        return Err(str(e))


def std(values, **_):
    try:
        if hasattr(values, "__iter__"):
            return Ok(statistics.stdev(values))
        return Err("std() requires a list")
    except Exception as e:
        return Err(str(e))


def sqrt(x, **_):
    try:
        return Ok(math.sqrt(x))
    except Exception as e:
        return Err(str(e))


def round_(x, **_):
    try:
        return Ok(round(x))
    except Exception as e:
        return Err(str(e))


def build_math_env() -> dict:
    return {
        "log":   log,
        "mean":  mean,
        "std":   std,
        "sqrt":  sqrt,
        "round": round_,
    }
