"""
Peppermint env lib — read environment variables.
"""
from __future__ import annotations
import os
from ..bridge import ok, err


def get(key, **_):
    val = os.environ.get(key)
    if val is None:
        return err(f"env.get: '{key}' is not set")
    return val


def build_env_env() -> dict:
    return {
        "get": get,
    }
