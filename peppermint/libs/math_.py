import math
import statistics
from ..bridge import wrap_lib


def log(x):
    return math.log(x)

def mean(values):
    return statistics.mean(values)

def std(values):
    return statistics.stdev(values)

def sqrt(x):
    return math.sqrt(x)

def round_(x):
    return round(x)

def floor(x):
    return math.floor(x)

def ceil(x):
    return math.ceil(x)

def abs_(x):
    return abs(x)


def build_math_env() -> dict:
    return wrap_lib({
        "log":   log,
        "mean":  mean,
        "std":   std,
        "sqrt":  sqrt,
        "round": round_,
        "floor": floor,
        "ceil":  ceil,
        "abs":   abs_,
    })
