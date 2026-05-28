from __future__ import annotations
import hashlib
import json
import os
import pickle
from pathlib import Path
from typing import Any


def _sha256(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode())
    return h.hexdigest()


def _fingerprint(value: Any) -> str:
    """Fast fingerprint of a value for cache keying. Not cryptographically exact."""
    try:
        from .context import Context
        if isinstance(value, Context):
            rows = value.data
            n = len(rows)
            cols = sorted(rows[0].keys()) if rows else []
            sample = json.dumps(rows[0], sort_keys=True, default=str) if rows else ""
            tail = json.dumps(rows[-1], sort_keys=True, default=str) if n > 1 else ""
            return _sha256(str(n), str(cols), sample, tail)
    except Exception:
        pass
    try:
        return _sha256(json.dumps(value, sort_keys=True, default=str))
    except Exception:
        return _sha256(repr(value))


def cache_key_for_step(step_src: str, input_value: Any) -> str:
    return _sha256(step_src, _fingerprint(input_value))


def cache_key_for_load(path: str) -> str:
    stat = os.stat(path)
    return _sha256(os.path.abspath(path), str(stat.st_mtime), str(stat.st_size))


def cache_key_for_row(row: dict, step_src: str) -> str:
    try:
        row_str = json.dumps(row, sort_keys=True, default=str)
    except Exception:
        row_str = repr(row)
    return _sha256(row_str, step_src)


class _Store:
    def __init__(self, cache_dir: Path):
        self._dir = cache_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._dir / key[:2] / key[2:]

    def get(self, key: str) -> Any | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            with open(p, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None

    def set(self, key: str, value: Any) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(p) + ".tmp"
        with open(tmp, "wb") as f:
            pickle.dump(value, f)
        os.replace(tmp, p)

    def clear(self) -> None:
        import shutil
        shutil.rmtree(self._dir)
        self._dir.mkdir(parents=True, exist_ok=True)


class Cache:
    """Value cache + row-level cache, rooted at a .peppermint/ directory."""

    def __init__(self, pep_file_path: str, cache_dir: str | None = None):
        if cache_dir:
            root = Path(cache_dir)
        else:
            root = Path(pep_file_path).parent / ".peppermint"
        self._steps = _Store(root / "cache")
        self._rows  = _Store(root / "row_cache")

    # --- Step-level cache ---

    def get_step(self, key: str) -> Any | None:
        return self._steps.get(key)

    def set_step(self, key: str, value: Any) -> None:
        self._steps.set(key, value)

    # --- Row-level cache ---

    def get_row(self, key: str) -> Any | None:
        return self._rows.get(key)

    def set_row(self, key: str, value: Any) -> None:
        self._rows.set(key, value)

    def clear(self) -> None:
        self._steps.clear()
        self._rows.clear()
