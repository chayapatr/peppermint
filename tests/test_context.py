from peppermint.context import Context


def test_context_defaults():
    ctx = Context(data=[{"a": 1}])
    assert ctx.data == [{"a": 1}]
    assert ctx.artifacts == {}
    assert ctx.errors == []


def test_context_rows_property():
    ctx = Context(data=[{"a": 1}, {"a": 2}])
    assert ctx.rows == [{"a": 1}, {"a": 2}]


def test_with_data_immutable():
    ctx = Context(data=[{"a": 1}])
    ctx2 = ctx.with_data([{"a": 2}])
    assert ctx2.data == [{"a": 2}]
    assert ctx2.artifacts == {}
    assert ctx.data == [{"a": 1}]


def test_with_artifact_immutable():
    ctx = Context(data=[])
    ctx2 = ctx.with_artifact("kmeans", {"k": 3})
    assert ctx2.artifacts == {"kmeans": {"k": 3}}
    assert ctx.artifacts == {}


def test_with_error_immutable():
    ctx = Context(data=[{"a": 1}])
    row = {"a": 1, "_error": "oops", "_step": "add"}
    ctx2 = ctx.with_error(row)
    assert ctx2.errors == [row]
    assert ctx.errors == []


def test_merge_errors():
    ctx = Context(data=[], errors=[{"_error": "a"}])
    ctx2 = ctx.merge_errors([{"_error": "b"}])
    assert len(ctx2.errors) == 2
    assert ctx.errors == [{"_error": "a"}]


def test_artifacts_preserved_through_with_data():
    ctx = Context(data=[{"a": 1}], artifacts={"kmeans": {"k": 3}})
    ctx2 = ctx.with_data([{"a": 2}])
    assert ctx2.artifacts == {"kmeans": {"k": 3}}
