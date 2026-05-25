import math
import statistics
from ..bridge import wrap_lib
from ..stdlib.core import pep_signature


@pep_signature("math.log(x: Num) -> Num")
def log(x):
    """Natural logarithm."""
    return math.log(x)

@pep_signature("math.mean(list: List<Num>) -> Num")
def mean(values):
    """Mean of a list of numbers."""
    return statistics.mean(values)

@pep_signature("math.std(list: List<Num>) -> Num")
def std(values):
    """Standard deviation of a list of numbers."""
    return statistics.stdev(values)

@pep_signature("math.sqrt(x: Num) -> Num")
def sqrt(x):
    """Square root."""
    return math.sqrt(x)

@pep_signature("math.round(x: Num) -> Int")
def round_(x):
    """Round to nearest integer."""
    return round(x)

@pep_signature("math.floor(x: Num) -> Int")
def floor(x):
    """Floor of x."""
    return math.floor(x)

@pep_signature("math.ceil(x: Num) -> Int")
def ceil(x):
    """Ceiling of x."""
    return math.ceil(x)

@pep_signature("math.abs(x: Num) -> Num")
def abs_(x):
    """Absolute value."""
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
