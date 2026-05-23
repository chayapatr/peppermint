"""
Peppermint str stdlib — string operations.
"""
import re as _re
from ..bridge import ok, err, to_python


def _ev(arg, interp, env):
    if interp and arg is not None and not isinstance(arg, (int, float, str, bool)):
        try:
            return interp.eval(arg, env)
        except Exception:
            return arg
    return arg


def trim(s, _interp=None, _env=None, **_):
    try:
        return ok(str(to_python(_ev(s, _interp, _env))).strip())
    except Exception as e:
        return err(str(e))


def lower(s, _interp=None, _env=None, **_):
    try:
        return ok(str(to_python(_ev(s, _interp, _env))).lower())
    except Exception as e:
        return err(str(e))


def upper(s, _interp=None, _env=None, **_):
    try:
        return ok(str(to_python(_ev(s, _interp, _env))).upper())
    except Exception as e:
        return err(str(e))


def replace(s, old, new, _interp=None, _env=None, **_):
    try:
        s   = str(to_python(_ev(s,   _interp, _env)))
        old = str(to_python(_ev(old, _interp, _env)))
        new = str(to_python(_ev(new, _interp, _env)))
        return ok(s.replace(old, new))
    except Exception as e:
        return err(str(e))


def split(s, sep=None, _interp=None, _env=None, **_):
    try:
        s   = str(to_python(_ev(s,   _interp, _env)))
        sep = str(to_python(_ev(sep, _interp, _env))) if sep is not None else None
        return ok(s.split(sep))
    except Exception as e:
        return err(str(e))


def join(parts, sep="", _interp=None, _env=None, **_):
    try:
        parts = to_python(_ev(parts, _interp, _env))
        sep   = str(to_python(_ev(sep, _interp, _env)))
        return ok(sep.join(str(p) for p in parts))
    except Exception as e:
        return err(str(e))


def contains(s, sub, _interp=None, _env=None, **_):
    try:
        s   = str(to_python(_ev(s,   _interp, _env)))
        sub = str(to_python(_ev(sub, _interp, _env)))
        return ok(sub in s)
    except Exception as e:
        return err(str(e))


def starts_with(s, prefix, _interp=None, _env=None, **_):
    try:
        s      = str(to_python(_ev(s,      _interp, _env)))
        prefix = str(to_python(_ev(prefix, _interp, _env)))
        return ok(s.startswith(prefix))
    except Exception as e:
        return err(str(e))


def ends_with(s, suffix, _interp=None, _env=None, **_):
    try:
        s      = str(to_python(_ev(s,      _interp, _env)))
        suffix = str(to_python(_ev(suffix, _interp, _env)))
        return ok(s.endswith(suffix))
    except Exception as e:
        return err(str(e))


def length(s, _interp=None, _env=None, **_):
    try:
        return ok(len(to_python(_ev(s, _interp, _env))))
    except Exception as e:
        return err(str(e))


def match(s, pattern, _interp=None, _env=None, **_):
    try:
        s       = str(to_python(_ev(s,       _interp, _env)))
        pattern = str(to_python(_ev(pattern, _interp, _env)))
        return ok(_re.search(pattern, s) is not None)
    except Exception as e:
        return err(str(e))


def slice_(s, start=0, end=None, _interp=None, _env=None, **_):
    try:
        s     = str(to_python(_ev(s,     _interp, _env)))
        start = int(to_python(_ev(start, _interp, _env)))
        end   = int(to_python(_ev(end,   _interp, _env))) if end is not None else None
        return ok(s[start:end])
    except Exception as e:
        return err(str(e))


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
    }
