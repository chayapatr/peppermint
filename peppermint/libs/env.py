"""
Peppermint env lib — read environment variables.
"""
from __future__ import annotations
import os
from ..bridge import err
from ..stdlib.core import pep_signature


@pep_signature("env.get(key: str) -> str | Err")
def get(key, **_):
    """Read an environment variable. Returns Err if not set. Prefer `env.KEY` for static keys."""
    val = os.environ.get(key)
    if val is None:
        return err(f"env.get: '{key}' is not set")
    return val


class _EnvNamespace(dict):
    """Dict subclass for the env namespace. Missing key lookups read os.environ."""

    def __missing__(self, key: str):
        val = os.environ.get(key)
        if val is None:
            from ..interpreter import Err
            return Err(f"env.{key} is not set")
        return val


def build_env_env() -> "_EnvNamespace":
    ns = _EnvNamespace()
    ns["get"] = get
    return ns
