import re as _re
from ..bridge import pep_fn
from ..stdlib.core import pep_signature


@pep_fn
@pep_signature("str.trim(s: str) -> str")
def trim(s):
    """Strip leading and trailing whitespace."""
    return str(s).strip()

@pep_fn
@pep_signature("str.lower(s: str) -> str")
def lower(s):
    """Convert to lowercase."""
    return str(s).lower()

@pep_fn
@pep_signature("str.upper(s: str) -> str")
def upper(s):
    """Convert to uppercase."""
    return str(s).upper()

@pep_fn
@pep_signature("str.replace(s: str, old: str, new: str) -> str")
def replace(s, old, new):
    """Replace all occurrences of `old` with `new`."""
    return str(s).replace(str(old), str(new))

@pep_fn
@pep_signature("str.split(s: str, sep: str) -> List<str>")
def split(s, sep=None):
    """Split a string into a list by separator."""
    return str(s).split(str(sep) if sep is not None else None)

@pep_fn
@pep_signature("str.join(parts: List<str>, sep: str) -> str")
def join(parts, sep=""):
    """Join a list of strings with a separator."""
    return str(sep).join(str(p) for p in parts)

@pep_fn
@pep_signature("str.contains(s: str, sub: str) -> bool")
def contains(s, sub):
    """True if `sub` is found in `s`."""
    return str(sub) in str(s)

@pep_fn
@pep_signature("str.starts_with(s: str, prefix: str) -> bool")
def starts_with(s, prefix):
    """True if `s` starts with `prefix`."""
    return str(s).startswith(str(prefix))

@pep_fn
@pep_signature("str.ends_with(s: str, suffix: str) -> bool")
def ends_with(s, suffix):
    """True if `s` ends with `suffix`."""
    return str(s).endswith(str(suffix))

@pep_fn
@pep_signature("str.length(s: str) -> Int")
def length(s):
    """Length of a string in characters."""
    return len(s)

@pep_fn
@pep_signature("str.match(s: str, pattern: str) -> bool")
def match(s, pattern):
    """True if the regex pattern matches anywhere in `s`."""
    return _re.search(str(pattern), str(s)) is not None

@pep_fn
@pep_signature("str.slice(s: str, start: Int, end?: Int) -> str")
def slice_(s, start=0, end=None):
    """Substring by character index."""
    return str(s)[int(start):int(end) if end is not None else None]

@pep_fn
def at(s, i):
    return str(s)[int(i)]

@pep_fn
def ord_(c):
    return ord(str(c)[0])

@pep_fn
def char(n):
    return chr(int(n))

@pep_fn
def chars(s):
    return list(str(s))


def build_str_env() -> dict:
    return {
        "trim":        trim,
        "lower":       lower,
        "upper":       upper,
        "replace":     replace,
        "split":       split,
        "join":        join,
        "contains":    contains,
        "starts_with": starts_with,
        "ends_with":   ends_with,
        "length":      length,
        "match":       match,
        "slice":       slice_,
        "at":          at,
        "ord":         ord_,
        "char":        char,
        "chars":       chars,
    }
