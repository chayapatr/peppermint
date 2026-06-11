"""Tests for @progress annotation."""
import io
import sys
from peppermint.parser import parse
from peppermint.interpreter import Interpreter, Ok
from peppermint.stdlib import build_global_env
from peppermint.context import Context


def _make_fn(call_count: dict | None = None):
    def fn(data, **_):
        rows = data.data if isinstance(data, Context) else data
        result = []
        for row in rows:
            if call_count is not None:
                call_count["n"] += 1
            result.append({**row, "out": row["x"] * 2})
        return Context(data=result)
    return fn


def _run_capture(src: str, cache=None):
    """Run src, capture stderr progress output."""
    env = build_global_env()
    env.set("fn", _make_fn())

    buf = io.StringIO()
    old = sys.stderr
    sys.stderr = buf
    try:
        result = Interpreter(env, quiet=True, cache=cache).run(parse(src))
    finally:
        sys.stderr = old

    val = result.value if isinstance(result, Ok) else result
    return val, buf.getvalue()


def test_progress_outputs_bar_to_stderr():
    _, stderr = _run_capture("[{x:1},{x:2},{x:3}] |> fn()\n    @progress")
    assert "█" in stderr or "/" in stderr


def test_progress_shows_correct_count():
    _, stderr = _run_capture("[{x:1},{x:2},{x:3},{x:4},{x:5}] |> fn()\n    @progress")
    assert "5/5" in stderr


def test_progress_with_concurrent():
    _, stderr = _run_capture(
        "[{x:1},{x:2},{x:3},{x:4},{x:5}] |> fn()\n    @concurrent(3)\n    @progress"
    )
    assert "5/5" in stderr


def test_progress_does_not_affect_result():
    result_with, _ = _run_capture("[{x:1},{x:2},{x:3}] |> fn()\n    @progress")
    result_without, _ = _run_capture("[{x:1},{x:2},{x:3}] |> fn()")
    assert result_with.data == result_without.data


def test_no_progress_without_annotation():
    _, stderr = _run_capture("[{x:1},{x:2},{x:3}] |> fn()")
    assert "█" not in stderr and "░" not in stderr


def test_progress_with_row_cache(tmp_path):
    from peppermint.cache import Cache
    cache = Cache(str(tmp_path / "test.pep"))
    _, stderr = _run_capture(
        "[{x:1},{x:2},{x:3}] |> fn()\n    @row_cache\n    @progress",
        cache=cache,
    )
    assert "3/3" in stderr
