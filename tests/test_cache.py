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

    src = '[{ a: 1 }, { a: 2 }, { a: 3 }] |> filter(it.a > 1)'
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
    """Verify ml.embed skips the API call when row is cached."""
    import unittest.mock as mock
    from peppermint.cache import Cache, cache_key_for_row
    from peppermint.libs.ml import embed

    cache = Cache(str(tmp_path / "test.pep"))
    rk = cache_key_for_row({"text": "hello"}, "ml.embed(source=local,model=test)")
    cache.set_row(rk, [0.1, 0.2, 0.3])

    with mock.patch("peppermint.libs.ml._client_cache", {}):
        with mock.patch("sentence_transformers.SentenceTransformer") as MockST:
            result = embed("hello", source="local", model="test", _row_cache=cache)

    assert result == [0.1, 0.2, 0.3]
    MockST.assert_not_called()  # API never touched


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
