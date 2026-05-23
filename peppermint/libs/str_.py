import re as _re
from ..bridge import wrap_lib


def trim(s):
    return str(s).strip()

def lower(s):
    return str(s).lower()

def upper(s):
    return str(s).upper()

def replace(s, old, new):
    return str(s).replace(str(old), str(new))

def split(s, sep=None):
    return str(s).split(str(sep) if sep is not None else None)

def join(parts, sep=""):
    return str(sep).join(str(p) for p in parts)

def contains(s, sub):
    return str(sub) in str(s)

def starts_with(s, prefix):
    return str(s).startswith(str(prefix))

def ends_with(s, suffix):
    return str(s).endswith(str(suffix))

def length(s):
    return len(s)

def match(s, pattern):
    return _re.search(str(pattern), str(s)) is not None

def slice_(s, start=0, end=None):
    return str(s)[int(start):int(end) if end is not None else None]

def at(s, i):
    return str(s)[int(i)]

def ord_(c):
    return ord(str(c)[0])

def char(n):
    return chr(int(n))

def chars(s):
    return list(str(s))


def build_str_env() -> dict:
    return wrap_lib({
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
    })
