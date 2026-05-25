"""
Peppermint env lib — read environment variables.
"""
from __future__ import annotations
import os
from ..bridge import ok, err
from ..stdlib.core import pep_signature


@pep_signature("env.get(key: str) -> str | Err")
def get(key, **_):
    """Read an environment variable. Returns Err if the key is not set."""
    val = os.environ.get(key)
    if val is None:
        return err(f"env.get: '{key}' is not set")
    return val


def build_env_env() -> dict:
    return {
        "get": get,
    }
