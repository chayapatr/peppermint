from __future__ import annotations
import hashlib
import hmac as _hmac
import json
import os
import pickle
import secrets
from pathlib import Path
from typing import Any


def _sha256(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode())
    return h.hexdigest()


def _fingerprint(value: Any) -> str:
    """Content fingerprint of a value for cache keying."""
    try:
        from .context import Context
        if isinstance(value, Context):
            rows = value.data
            cols = sorted(rows[0].keys()) if rows else []
            h = hashlib.sha256()
            h.update(str(len(rows)).encode())
            h.update(str(cols).encode())
            for row in rows:
                h.update(json.dumps(row, sort_keys=True, default=str).encode())
            return h.hexdigest()
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


def _load_or_create_key(root: Path) -> bytes:
    """Load the per-machine HMAC key from root/.key, creating it on first use."""
    key_path = root / ".key"
    if key_path.exists():
        try:
            return key_path.read_bytes()
        except Exception:
            pass
    key = secrets.token_bytes(32)
    try:
        key_path.write_bytes(key)
    except Exception:
        pass
    return key


class _Store:
    """Pickle cache with HMAC-signed entries.

    Every entry is stored as: 32-byte HMAC-SHA256 || pickle payload.
    On read, the HMAC is verified before calling pickle.loads — a tampered
    or externally-injected file fails the check and is treated as a cache
    miss, so pickle.loads is never called on unverified data.
    """

    def __init__(self, cache_dir: Path, key: bytes):
        self._dir = cache_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._key = key

    def _path(self, key: str) -> Path:
        return self._dir / key[:2] / (key[2:] + ".pkl")

    def get(self, key: str) -> Any | None:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            raw = p.read_bytes()
            if len(raw) < 32:
                return None
            mac, payload = raw[:32], raw[32:]
            expected = _hmac.new(self._key, payload, "sha256").digest()
            if not _hmac.compare_digest(mac, expected):
                return None  # tampered; treat as miss rather than deserializing
            return pickle.loads(payload)
        except Exception:
            return None

    def set(self, key: str, value: Any) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(p) + ".tmp"
        try:
            payload = pickle.dumps(value)
            mac = _hmac.new(self._key, payload, "sha256").digest()
            with open(tmp, "wb") as f:
                f.write(mac + payload)
            os.replace(tmp, p)
        except Exception:
            pass  # not serializable; skip caching silently

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
        root.mkdir(parents=True, exist_ok=True)
        key = _load_or_create_key(root)
        self._steps = _Store(root / "cache", key)
        self._rows  = _Store(root / "row_cache", key)

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
