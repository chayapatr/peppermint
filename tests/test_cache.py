import pytest
from peppermint.cache import Cache, cache_key_for_step, cache_key_for_load, cache_key_for_row


def test_step_cache_miss_then_hit(tmp_path):
    cache = Cache(str(tmp_path / "test.pep"))
    key = cache_key_for_step("filter(it.a > 1)", [{"a": 1}])
    assert cache.get_step(key) is None
    cache.set_step(key, [{"a": 2}])
    assert cache.get_step(key) == [{"a": 2}]


def test_step_cache_persists(tmp_path):
    pep = str(tmp_path / "test.pep")
    Cache(pep).set_step("k", [1, 2, 3])
    assert Cache(pep).get_step("k") == [1, 2, 3]


def test_step_key_differs_for_different_inputs():
    k1 = cache_key_for_step("filter(it.a > 1)", [{"a": 1}])
    k2 = cache_key_for_step("filter(it.a > 1)", [{"a": 2}])
    assert k1 != k2


def test_step_key_same_for_same_inputs():
    k1 = cache_key_for_step("filter(it.a > 1)", [{"a": 1}])
    k2 = cache_key_for_step("filter(it.a > 1)", [{"a": 1}])
    assert k1 == k2


def test_step_key_differs_for_different_steps():
    k1 = cache_key_for_step("filter(it.a > 1)", [{"a": 1}])
    k2 = cache_key_for_step("filter(it.a > 2)", [{"a": 1}])
    assert k1 != k2


def test_load_key_changes_on_file_change(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")
    k1 = cache_key_for_load(str(f))
    import time; time.sleep(0.01)
    f.write_text("a,b\n1,2\n3,4\n")
    k2 = cache_key_for_load(str(f))
    assert k1 != k2


def test_row_cache_miss_then_hit(tmp_path):
    cache = Cache(str(tmp_path / "test.pep"))
    key = cache_key_for_row({"text": "hello"}, "ml.embed(source=deepinfra,model=x)")
    assert cache.get_row(key) is None
    cache.set_row(key, [0.1, 0.2])
    assert cache.get_row(key) == [0.1, 0.2]


def test_row_key_differs_for_different_rows():
    k1 = cache_key_for_row({"text": "hello"}, "ml.embed")
    k2 = cache_key_for_row({"text": "world"}, "ml.embed")
    assert k1 != k2


def test_row_key_same_for_same_row():
    k1 = cache_key_for_row({"text": "hello"}, "ml.embed")
    k2 = cache_key_for_row({"text": "hello"}, "ml.embed")
    assert k1 == k2


def test_cache_clear(tmp_path):
    cache = Cache(str(tmp_path / "test.pep"))
    cache.set_step("k", 42)
    cache.clear()
    assert cache.get_step("k") is None


def test_cache_atomic_write(tmp_path):
    cache = Cache(str(tmp_path / "test.pep"))
    cache.set_step("k", {"result": 99})
    assert cache.get_step("k") == {"result": 99}
    # No .tmp files left behind
    import os
    for root, _, files in os.walk(tmp_path):
        assert not any(f.endswith(".tmp") for f in files)


def test_fingerprint_differs_for_different_content():
    from peppermint.cache import _fingerprint
    from peppermint.context import Context
    ctx1 = Context(data=[{"a": 1}, {"a": 2}])
    ctx2 = Context(data=[{"a": 3}, {"a": 4}])
    assert _fingerprint(ctx1) != _fingerprint(ctx2)


def test_fingerprint_same_for_same_content():
    from peppermint.cache import _fingerprint
    from peppermint.context import Context
    ctx1 = Context(data=[{"a": 1}, {"a": 2}])
    ctx2 = Context(data=[{"a": 1}, {"a": 2}])
    assert _fingerprint(ctx1) == _fingerprint(ctx2)


def test_fingerprint_differs_for_different_middle_rows():
    from peppermint.cache import _fingerprint
    from peppermint.context import Context
    ctx1 = Context(data=[{"id": 1}, {"id": 999}, {"id": 3}])
    ctx2 = Context(data=[{"id": 1}, {"id": 888}, {"id": 3}])
    assert _fingerprint(ctx1) != _fingerprint(ctx2)


def test_step_cache_skips_execution(tmp_path):
    """Verify eval_pipe hits cache and does not re-execute the step."""
    from peppermint.parser import parse
    from peppermint.interpreter import Interpreter
    from peppermint.stdlib import build_global_env

    call_count = {"n": 0}
    original_filter = None

    import peppermint.stdlib.core as core
    original_filter = core.filter_

    def counting_filter(*args, **kwargs):
        call_count["n"] += 1
        return original_filter(*args, **kwargs)
    counting_filter._accepts_deferred = True
    counting_filter._pep_signature = original_filter._pep_signature

    core.filter_ = counting_filter

    src = '[{ a: 1 }, { a: 2 }, { a: 3 }] |> filter(it.a > 1)\n    @cache'
    pep_path = str(tmp_path / "test.pep")
    cache = Cache(pep_path)

    try:
        env1 = build_global_env()
        env1.set("filter", counting_filter)
        Interpreter(env1, quiet=True, cache=cache).run(parse(src))

        env2 = build_global_env()
        env2.set("filter", counting_filter)
        Interpreter(env2, quiet=True, cache=cache).run(parse(src))
    finally:
        core.filter_ = original_filter

    assert call_count["n"] == 1  # second run was a cache hit


def test_row_cache_skips_api_call(tmp_path):
    """Verify @row_cache skips the function call when row is already cached."""
    from peppermint.parser import parse
    from peppermint.interpreter import Interpreter
    from peppermint.stdlib import build_global_env
    from peppermint.cache import Cache, cache_key_for_row
    from peppermint.context import Context

    call_count = {"n": 0}

    def expensive(data, _interp=None, _env=None, **_):
        rows = data.data if isinstance(data, Context) else data
        result = []
        for row in rows:
            call_count["n"] += 1
            result.append({**row, "out": row["x"] * 2})
        return Context(data=result)

    env = build_global_env()
    env.set("expensive", expensive)

    src = '[{ x: 1 }, { x: 2 }, { x: 3 }] |> expensive()\n    @row_cache'
    cache = Cache(str(tmp_path / "test.pep"))

    # First run — all 3 rows computed
    Interpreter(env, quiet=True, cache=cache).run(parse(src))
    assert call_count["n"] == 3

    # Second run — all 3 rows served from row cache
    call_count["n"] = 0
    Interpreter(env, quiet=True, cache=cache).run(parse(src))
    assert call_count["n"] == 0  # no calls, all cached


def _make_row_fn(call_count):
    """Helper: a per-row function that tracks how many times it's called."""
    from peppermint.context import Context

    def fn(data, _interp=None, _env=None, **_):
        rows = data.data if isinstance(data, Context) else data
        result = []
        for row in rows:
            call_count["n"] += 1
            result.append({**row, "out": row["x"] * 2})
        return Context(data=result)

    return fn


def test_row_cache_partial_failure_retries_failed_rows(tmp_path):
    """Failed rows are not cached -- they are retried on the next run."""
    from peppermint.parser import parse
    from peppermint.interpreter import Interpreter
    from peppermint.stdlib import build_global_env
    from peppermint.context import Context

    call_count = {"n": 0}

    def fn(data, _interp=None, _env=None, **_):
        rows = data.data if isinstance(data, Context) else data
        result = []
        for row in rows:
            call_count["n"] += 1
            if row["x"] == 2:
                raise RuntimeError("simulated failure")
            result.append({**row, "out": row["x"] * 10})
        return Context(data=result)

    env = build_global_env()
    env.set("fn", fn)
    src = '[{ x: 1 }, { x: 2 }, { x: 3 }] |> fn()\n    @row_cache'
    cache = Cache(str(tmp_path / "test.pep"))

    # Run 1: rows 1 and 3 succeed, row 2 fails
    Interpreter(env, quiet=True, cache=cache).run(parse(src))
    assert call_count["n"] == 3

    # Run 2: rows 1 and 3 served from cache, row 2 retried
    call_count["n"] = 0
    Interpreter(env, quiet=True, cache=cache).run(parse(src))
    assert call_count["n"] == 1  # only row 2 retried


def test_row_cache_step_cache_written_when_fully_done(tmp_path):
    """After all rows succeed, step cache is written -- next rerun skips everything."""
    from peppermint.parser import parse
    from peppermint.interpreter import Interpreter
    from peppermint.stdlib import build_global_env

    call_count = {"n": 0}
    env = build_global_env()
    env.set("fn", _make_row_fn(call_count))
    src = '[{ x: 1 }, { x: 2 }, { x: 3 }] |> fn()\n    @row_cache'
    cache = Cache(str(tmp_path / "test.pep"))

    # Run 1: all rows computed, step cache written at end
    Interpreter(env, quiet=True, cache=cache).run(parse(src))
    assert call_count["n"] == 3

    # Run 2: step cache hit -- fn never called, not even for row cache lookup
    call_count["n"] = 0
    Interpreter(env, quiet=True, cache=cache).run(parse(src))
    assert call_count["n"] == 0


def test_row_cache_no_step_cache_when_errors(tmp_path):
    """If any row fails, step cache is NOT written -- next rerun goes through row cache."""
    from peppermint.parser import parse
    from peppermint.interpreter import Interpreter
    from peppermint.stdlib import build_global_env
    from peppermint.context import Context

    attempt = {"n": 0}

    def fn(data, _interp=None, _env=None, **_):
        rows = data.data if isinstance(data, Context) else data
        result = []
        for row in rows:
            attempt["n"] += 1
            if row["x"] == 3:
                raise RuntimeError("fail")
            result.append({**row, "out": row["x"]})
        return Context(data=result)

    env = build_global_env()
    env.set("fn", fn)
    src = '[{ x: 1 }, { x: 2 }, { x: 3 }] |> fn()\n    @row_cache'
    cache = Cache(str(tmp_path / "test.pep"))

    # Run 1: row 3 fails, step cache NOT written
    Interpreter(env, quiet=True, cache=cache).run(parse(src))
    assert attempt["n"] == 3

    # Run 2: must go through row cache (not step cache), rows 1+2 cached, row 3 retried
    attempt["n"] = 0
    Interpreter(env, quiet=True, cache=cache).run(parse(src))
    assert attempt["n"] == 1  # only row 3 retried, not a full step cache hit


def test_row_cache_new_rows_run_existing_cached(tmp_path):
    """Adding new rows reruns only the new ones -- existing rows served from cache."""
    from peppermint.parser import parse
    from peppermint.interpreter import Interpreter
    from peppermint.stdlib import build_global_env

    call_count = {"n": 0}
    env = build_global_env()

    def fn(data, _interp=None, _env=None, **_):
        from peppermint.context import Context
        rows = data.data if isinstance(data, Context) else data
        result = []
        for row in rows:
            call_count["n"] += 1
            result.append({**row, "out": row["x"] * 2})
        return Context(data=result)

    env.set("fn", fn)
    cache = Cache(str(tmp_path / "test.pep"))

    # Run 1: 2 rows
    src1 = '[{ x: 1 }, { x: 2 }] |> fn()\n    @row_cache'
    Interpreter(env, quiet=True, cache=cache).run(parse(src1))
    assert call_count["n"] == 2

    # Run 2: 3 rows (1 new) — existing 2 cached, only new row runs
    call_count["n"] = 0
    src2 = '[{ x: 1 }, { x: 2 }, { x: 3 }] |> fn()\n    @row_cache'
    Interpreter(env, quiet=True, cache=cache).run(parse(src2))
    assert call_count["n"] == 1  # only x=3 is new


def test_tampered_file_returns_none(tmp_path):
    from peppermint.cache import _Store
    import secrets
    key = secrets.token_bytes(32)
    store = _Store(tmp_path / "cache", key)
    store.set("k", {"data": [1, 2, 3]})
    store._path("k").write_bytes(b"\x00" * 64)
    assert store.get("k") is None


def test_wrong_key_returns_none(tmp_path):
    from peppermint.cache import _Store
    import secrets
    key_a, key_b = secrets.token_bytes(32), secrets.token_bytes(32)
    _Store(tmp_path / "cache", key_a).set("k", {"secret": "value"})
    assert _Store(tmp_path / "cache", key_b).get("k") is None


def test_truncated_file_returns_none(tmp_path):
    from peppermint.cache import _Store
    import secrets
    key = secrets.token_bytes(32)
    store = _Store(tmp_path / "cache", key)
    store.set("k", 42)
    store._path("k").write_bytes(b"\x00" * 10)
    assert store.get("k") is None


def test_valid_entry_readable_alongside_tampered(tmp_path):
    from peppermint.cache import _Store
    import secrets
    key = secrets.token_bytes(32)
    store = _Store(tmp_path / "cache", key)
    store.set("good", [1, 2, 3])
    store.set("bad", "will be corrupted")
    store._path("bad").write_bytes(b"\xff" * 64)
    assert store.get("bad") is None
    assert store.get("good") == [1, 2, 3]


def test_cache_off_by_default(tmp_path):
    """Without cache=, interpreter has no cache and .peppermint/ is not created."""
    from peppermint.parser import parse
    from peppermint.interpreter import Interpreter
    from peppermint.stdlib import build_global_env
    import os

    src = '[{ a: 1 }] |> filter(it.a > 0)'
    env = build_global_env()
    interp = Interpreter(env, quiet=True)
    assert interp._cache is None
    interp.run(parse(src))
    assert not (tmp_path / ".peppermint").exists()
