import math
import statistics
from ..bridge import pep_fn
from ..stdlib.core import pep_signature


@pep_fn
@pep_signature("math.log(x: Num) -> Num")
def log(x):
    """Natural logarithm."""
    return math.log(x)

@pep_fn
@pep_signature("math.mean(list: List<Num>) -> Num")
def mean(values):
    """Mean of a list of numbers."""
    return statistics.mean(values)

@pep_fn
@pep_signature("math.std(list: List<Num>) -> Num")
def std(values):
    """Standard deviation of a list of numbers."""
    return statistics.stdev(values)

@pep_fn
@pep_signature("math.sqrt(x: Num) -> Num")
def sqrt(x):
    """Square root."""
    return math.sqrt(x)

@pep_fn
@pep_signature("math.round(x: Num) -> Int")
def round_(x):
    """Round to nearest integer."""
    return round(x)

@pep_fn
@pep_signature("math.floor(x: Num) -> Int")
def floor(x):
    """Floor of x."""
    return math.floor(x)

@pep_fn
@pep_signature("math.ceil(x: Num) -> Int")
def ceil(x):
    """Ceiling of x."""
    return math.ceil(x)

@pep_fn
@pep_signature("math.abs(x: Num) -> Num")
def abs_(x):
    """Absolute value."""
    return abs(x)

@pep_fn
@pep_signature("math.min(list: List<Num>) -> Num")
def min_(values):
    """Minimum value in a list."""
    return min(values)

@pep_fn
@pep_signature("math.max(list: List<Num>) -> Num")
def max_(values):
    """Maximum value in a list."""
    return max(values)

@pep_fn
@pep_signature("math.sum(list: List<Num>) -> Num")
def sum_(values):
    """Sum of a list of numbers."""
    return sum(values)

@pep_fn
@pep_signature("math.median(list: List<Num>) -> Num")
def median(values):
    """Median of a list of numbers."""
    return statistics.median(values)

@pep_fn
@pep_signature("math.clamp(x: Num, lo: Num, hi: Num) -> Num")
def clamp(x, lo, hi):
    """Clamp x to the range [lo, hi]."""
    return max(lo, min(hi, x))

@pep_fn
@pep_signature("math.pow(x: Num, exp: Num) -> Num")
def pow_(x, exp):
    """Raise x to the power exp."""
    return math.pow(x, exp)


def build_math_env() -> dict:
    return {
        "log":    log,
        "mean":   mean,
        "std":    std,
        "sqrt":   sqrt,
        "round":  round_,
        "floor":  floor,
        "ceil":   ceil,
        "abs":    abs_,
        "min":    min_,
        "max":    max_,
        "sum":    sum_,
        "median": median,
        "clamp":  clamp,
        "pow":    pow_,
    }
