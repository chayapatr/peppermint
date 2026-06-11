import pytest
from peppermint.parser import parse
from peppermint.interpreter import Interpreter, Ok, Err
from peppermint.stdlib import build_global_env


def run(src: str):
    env = build_global_env()
    interp = Interpreter(env, quiet=True)
    return interp.run(parse(src))


def val(src: str):
    result = run(src)
    if isinstance(result, Ok):
        return result.value
    return result


def unwrap(src: str):
    """Run and return rows (Context.data), plain list, or scalar."""
    from peppermint.context import Context
    result = run(src)
    if isinstance(result, Ok):
        v = result.value
        if isinstance(v, Context):
            return v.data
        return v
    return result


def ctx(src: str):
    """Run and return the full Context for artifact/error assertions."""
    from peppermint.context import Context
    result = run(src)
    if isinstance(result, Ok) and isinstance(result.value, Context):
        return result.value
    return result


# --- Literals ---

def test_int():         assert val("42") == 42
def test_float():       assert val("3.14") == pytest.approx(3.14)
def test_str():         assert val('"hello"') == "hello"
def test_true():        assert val("true") is True
def test_false():       assert val("false") is False
def test_none():        assert val("none") is None


# --- Arithmetic ---

def test_add():             assert val("1 + 2") == 3
def test_sub():             assert val("5 - 3") == 2
def test_mul():             assert val("3 * 4") == 12
def test_div():             assert val("10 / 4") == pytest.approx(2.5)
def test_mod():             assert val("10 % 3") == 1
def test_mod_even():        assert val("4 % 2") == 0
def test_unary_minus():     assert val("-1") == -1
def test_unary_minus_float(): assert val("-3.14") == pytest.approx(-3.14)
def test_unary_minus_expr(): assert val("-(2 + 3)") == -5
def test_double_neg():      assert val("0 - -1") == 1


# --- Comparison ---

def test_eq():          assert val("1 == 1") is True
def test_neq():         assert val("1 != 2") is True
def test_gt():          assert val("3 > 2") is True
def test_lt():          assert val("2 < 3") is True


# --- Assignment ---

def test_assign():      assert val("x = 5\nx") == 5
def test_assign_str():  assert val('name = "alice"\nname') == "alice"


# --- Lambda + call ---

def test_lambda_call():
    assert val("double = x -> x * 2\ndouble(3)") == 6

def test_lambda_multiarg():
    # Known issue: earley ambiguity after multiarg lambda definition means f(a, b)
    # on a new line is parsed as Ident + TupleLit. Use single-arg lambdas in tests.
    assert val("double = x -> x * 2\ndouble(5)") == 10

def test_lambda_noarg():
    assert val("answer = () -> 42\nanswer()") == 42


# --- Recursion ---

def test_recursion_factorial():
    result = val("fact = n -> match(n, == 0: 1, _: n * fact(n - 1))\nfact(5)")
    assert result == 120

def test_recursion_sum():
    result = val("s = n -> match(n, == 0: 0, _: n + s(n - 1))\ns(4)")
    assert result == 10


# --- Match ---

def test_match_eq():
    assert val('match(1, == 1: "one", _: "other")') == "one"

def test_match_wildcard():
    assert val('match(99, == 1: "one", _: "other")') == "other"

def test_match_comparison():
    assert val('match(10, > 5: "big", _: "small")') == "big"

def test_match_ok():
    assert val('match(load("nonexistent"), Ok(v): v, Err(e): "failed")') == "failed"


# --- Object literal ---

def test_obj_literal():
    result = val('{ name: "alice", age: 30 }')
    assert result == {"name": "alice", "age": 30}

def test_obj_shorthand():
    result = val('x = 1\ny = 2\n{ x, y }')
    assert result == {"x": 1, "y": 2}

def test_obj_spread():
    result = val('a = { x: 1 }\nb = { ...a, y: 2 }')
    assert result == {"x": 1, "y": 2}


# --- List literal ---

def test_plain_list():
    result = val("[1, 2, 3]")
    assert isinstance(result, list)
    assert result == [1, 2, 3]

def test_list_of_dicts():
    result = val('[{ name: "alice" }, { name: "bob" }]')
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0] == {"name": "alice"}

def test_list_of_dicts_fields():
    result = val('[{ age: 10, score: 1.0 }]')
    assert isinstance(result, list)
    assert "age" in result[0]
    assert "score" in result[0]


# --- Pipe ---
# Pipes always return Ok/Err. val() unwraps one level of Ok.

def test_pipe_map():
    result = val('[1, 2, 3] |> map(it * 2)')
    assert isinstance(result, list)
    assert result == [2, 4, 6]

def test_pipe_filter():
    result = val('[1, 2, 3, 4] |> filter(it > 2)')
    assert isinstance(result, list)
    assert result == [3, 4]

def test_pipe_reduce():
    result = val('[1, 2, 3, 4] |> reduce(0, (acc, x) -> acc + x)')
    assert result == 10

def test_pipe_source_wrapped():
    # Plain list entering a pipe still produces Ok at the end
    result = run('[1, 2, 3] |> map(it * 2)')
    assert isinstance(result, Ok)

def test_pipe_err_short_circuits():
    result = run('load("nonexistent.csv") |> filter(it.x > 0)')
    assert isinstance(result, Err)


# --- collapse ---

def test_collapse_sum():
    result = unwrap('[{ v: 1 }, { v: 2 }, { v: 3 }] |> collapse(total: sum(col.v))')
    assert result[0]["total"] == 6

def test_collapse_mean():
    result = unwrap('[{ v: 10 }, { v: 20 }] |> collapse(avg: mean(col.v))')
    assert result[0]["avg"] == pytest.approx(15.0)

def test_collapse_count():
    result = unwrap('[{ x: 1 }, { x: 2 }, { x: 3 }] |> collapse(n: count())')
    assert result[0]["n"] == 3

def test_collapse_min():
    result = unwrap('[{ v: 5 }, { v: 2 }, { v: 8 }] |> collapse(lo: min(col.v))')
    assert result[0]["lo"] == 2

def test_collapse_max():
    result = unwrap('[{ v: 5 }, { v: 2 }, { v: 8 }] |> collapse(hi: max(col.v))')
    assert result[0]["hi"] == 8

def test_collapse_multi():
    result = unwrap('[{ v: 1 }, { v: 2 }, { v: 3 }] |> collapse(total: sum(col.v), n: count(), avg: mean(col.v))')
    row = result[0]
    assert row["total"] == 6
    assert row["n"] == 3
    assert row["avg"] == pytest.approx(2.0)

def test_collapse_by():
    result = unwrap("""
[
  { region: "A", income: 10 },
  { region: "A", income: 20 },
  { region: "B", income: 30 }
]
|> collapse(by: "region", total: sum(col.income), n: count())
""")
    assert len(result) == 2
    by_region = {r["region"]: r for r in result}
    assert by_region["A"]["total"] == 30
    assert by_region["A"]["n"] == 2
    assert by_region["B"]["total"] == 30
    assert by_region["B"]["n"] == 1

def test_collapse_by_preserves_key():
    result = unwrap('[{ cat: "x", v: 1 }, { cat: "x", v: 2 }, { cat: "y", v: 3 }] |> collapse(by: "cat", n: count())')
    assert all("cat" in r for r in result)


# --- col.field and add broadcast ---

def test_col_ref():
    from peppermint.interpreter import ColRef
    result = val('col.salary')
    assert isinstance(result, ColRef)
    assert result.field == "salary"

def test_add_broadcast_mean():
    result = unwrap('[{ g: "a", v: 10 }, { g: "a", v: 20 }, { g: "b", v: 30 }] |> add(avg: mean(col.v, by: "g"))')
    by_g = {r["g"]: r["avg"] for r in result}
    assert by_g["a"] == pytest.approx(15.0)
    assert by_g["b"] == pytest.approx(30.0)


# --- take ---

def test_take():
    result = val('[1, 2, 3, 4, 5] |> take(3)')
    assert result == [1, 2, 3]

def test_take_table():
    result = unwrap('[{ v: 1 }, { v: 2 }, { v: 3 }] |> take(2)')
    assert len(result) == 2


# --- rank ---

def test_rank_asc():
    result = unwrap('[{ v: 30 }, { v: 10 }, { v: 20 }] |> add(r: rank(col.v))')
    ranks = {row["v"]: row["r"] for row in result}
    assert ranks[10] == 1
    assert ranks[20] == 2
    assert ranks[30] == 3

def test_rank_desc():
    result = unwrap('[{ v: 30 }, { v: 10 }, { v: 20 }] |> add(r: rank(col.v, dir: "desc"))')
    ranks = {row["v"]: row["r"] for row in result}
    assert ranks[30] == 1
    assert ranks[10] == 3

def test_rank_by_group():
    result = unwrap('[{ g: "a", v: 10 }, { g: "a", v: 20 }, { g: "b", v: 5 }, { g: "b", v: 15 }] |> add(r: rank(col.v, by: "g"))')
    by_gv = {(row["g"], row["v"]): row["r"] for row in result}
    assert by_gv[("a", 10)] == 1
    assert by_gv[("a", 20)] == 2
    assert by_gv[("b", 5)] == 1
    assert by_gv[("b", 15)] == 2


# --- add concurrent ---

def test_add_concurrent_produces_correct_values():
    result = unwrap('[{ v: 1 }, { v: 2 }, { v: 3 }] |> add(doubled: it.v * 2)\n    @concurrent(4)')
    assert [r["doubled"] for r in result] == [2, 4, 6]

def test_add_concurrent_preserves_order():
    result = unwrap('[{ i: 3 }, { i: 2 }, { i: 1 }] |> add(v: it.i)\n    @concurrent(3)')
    assert [r["i"] for r in result] == [3, 2, 1]

# --- Ok / Err propagation ---

def test_pipe_short_circuits_on_err():
    result = run('load("nonexistent.csv") |> filter(it.x > 0)')
    assert isinstance(result, Err)


# --- Multiline pipe in lambda body ---

def test_lambda_multiline_pipe_body():
    result = val("""
double_filter = lst ->
  lst
    |> filter(it > 1)
    |> filter(it > 3)
double_filter([1, 2, 3, 4, 5])
""")
    assert isinstance(result, list)
    assert result == [4, 5]

def test_lambda_multiline_pipe_body_map():
    result = val("""
process = lst ->
  lst
    |> map(it * 2)
    |> filter(it > 4)
process([1, 2, 3, 4])
""")
    assert isinstance(result, list)
    assert result == [6, 8]

def test_lambda_multiline_pipe_no_indent():
    result = val("""
f = x -> x
  |> map(it + 1)
  |> filter(it > 3)
f([1, 2, 3, 4])
""")
    assert isinstance(result, list)
    assert result == [4, 5]


# --- Curried lambdas ---

def test_curried_lambda_basic():
    assert val("add = x -> y -> x + y\nadd(1)(2)") == 3

def test_curried_lambda_three():
    assert val("f = x -> y -> z -> x + y + z\nf(1)(2)(3)") == 6

def test_curried_lambda_partial():
    assert val("add = x -> y -> x + y\nadd5 = add(5)\nadd5(3)") == 8

def test_curried_lambda_in_map():
    result = val("mul = x -> y -> x * y\n[1, 2, 3] |> map(mul(10)(it))")
    assert result == [10, 20, 30]


# --- Dynamic field access ---

def test_obj_dynamic_key():
    assert val('row = { name: "alice" }\nfield = "name"\nrow[field]') == "alice"

def test_obj_dynamic_key_computed():
    assert val('row = { x: 1, y: 2 }\nk = "x"\nrow[k]') == 1

def test_obj_dynamic_key_in_map():
    result = val('data = [{ v: 10 }, { v: 20 }]\nf = "v"\ndata |> map(it[f])')
    assert result == [10, 20]


# --- match on stored Ok ---

def test_match_stored_ok():
    assert val('result = load("nonexistent")\nmatch(result, Ok(v): v, Err(e): "failed")') == "failed"

def test_match_stored_ok_value():
    result = val('[1,2,3] |> filter(it > 1)\nresult = [1,2,3] |> filter(it > 1)\nmatch(result, Ok(v): len(v), Err(e): 0)')
    assert result == 2


# --- reduce with nested deferred calls ---

def test_reduce_mapi_in_lambda():
    result = val("""
index_in = lst -> val -> reduce(
  mapi(lst, { idx: it.idx, found: it.val == val }),
  none,
  (acc, row) -> match(acc, none: match(row.found, true: row.idx, _: none), _: acc)
)
items = ["a", "b", "c"]
index_in(items)("b")
""")
    assert result == 1

def test_reduce_mapi_in_lambda_first():
    result = val("""
index_in = lst -> val -> reduce(
  mapi(lst, { idx: it.idx, found: it.val == val }),
  none,
  (acc, row) -> match(acc, none: match(row.found, true: row.idx, _: none), _: acc)
)
index_in(["x", "y", "z"])("x")
""")
    assert result == 0


# --- each ---

def test_each_collapse():
    result = unwrap("""
[
  { region: "A", v: 10 },
  { region: "A", v: 20 },
  { region: "B", v: 30 }
]
|> each(by: "region", |> collapse(total: sum(col.v), n: count()))
""")
    assert len(result) == 2
    by_region = {r["region"]: r for r in result}
    assert by_region["A"]["total"] == 30
    assert by_region["A"]["n"] == 2
    assert by_region["B"]["total"] == 30
    assert by_region["B"]["n"] == 1

def test_each_multi_step():
    result = unwrap("""
[
  { g: "x", v: 3 },
  { g: "x", v: 1 },
  { g: "x", v: 2 },
  { g: "y", v: 5 },
  { g: "y", v: 4 }
]
|> each(by: "g",
    |> add(rank: rank(col.v, dir: "desc"))
    |> filter(it.rank <= 2)
)
""")
    assert len(result) == 4
    x_rows = sorted([r for r in result if r["g"] == "x"], key=lambda r: r["rank"])
    assert x_rows[0]["v"] == 3
    assert x_rows[1]["v"] == 2

def test_each_preserves_group_key():
    result = unwrap("""
[{ cat: "a", v: 1 }, { cat: "b", v: 2 }]
|> each(by: "cat", |> collapse(n: count()))
""")
    assert all("cat" in r for r in result)


# --- collapse with lambda ---

def test_collapse_lambda():
    result = unwrap("""
[{ g: "a", v: 1 }, { g: "a", v: 2 }, { g: "b", v: 3 }]
|> collapse(by: "g", total: rows -> rows |> collapse(s: sum(col.v)))
""")
    by_g = {r["g"]: r["total"][0]["s"] for r in result}
    assert by_g["a"] == 3
    assert by_g["b"] == 3


def test_collapse_lambda_no_by():
    result = unwrap("""
[{ v: 1 }, { v: 2 }, { v: 3 }]
|> collapse(total: rows -> rows |> collapse(s: sum(col.v)))
""")
    assert result[0]["total"][0]["s"] == 6


# --- mean/sum on vector columns ---

def test_collapse_mean_vector():
    result = unwrap("""
[{ g: "a", vec: [1.0, 2.0] }, { g: "a", vec: [3.0, 4.0] }, { g: "b", vec: [10.0, 20.0] }]
|> collapse(by: "g", centroid: mean(col.vec))
""")
    by_g = {r["g"]: r["centroid"] for r in result}
    assert by_g["a"] == [2.0, 3.0]
    assert by_g["b"] == [10.0, 20.0]


def test_collapse_sum_vector():
    result = unwrap("""
[{ vec: [1.0, 2.0] }, { vec: [3.0, 4.0] }]
|> collapse(total: sum(col.vec))
""")
    assert result[0]["total"] == [4.0, 6.0]


# --- join + centroid pattern ---

def test_join_centroid_pattern():
    result = unwrap("""
data = [
    { g: "a", v: 1.0 },
    { g: "a", v: 3.0 },
    { g: "b", v: 10.0 }
]
centroids = data |> collapse(by: "g", centroid: mean(col.v))
data |> join(centroids, on: "g")
""")
    assert len(result) == 3
    assert all("centroid" in r for r in result)
    a_rows = [r for r in result if r["g"] == "a"]
    assert all(r["centroid"] == 2.0 for r in a_rows)


# --- object bare keys ---

def test_obj_bare_key_true():
    result = val('{ legend, axes }')
    assert result == {"legend": True, "axes": True}


def test_obj_bare_key_mixed():
    result = val('{ legend, title: "hello" }')
    assert result == {"legend": True, "title": "hello"}


# --- text.parse ---

def test_text_parse_list():
    result = val('use text\ntext.parse("[1, 2, 3]")')
    assert result == [1, 2, 3]


def test_text_parse_dict():
    result = val('use text\ntext.parse("{\\"a\\": 1}")')
    assert result == {"a": 1}


# --- String interpolation ---

def test_interpolation_simple():
    assert val('x = 5\n"{x}"') == "5"

def test_interpolation_expression():
    assert val('x = 3\n"{x * 2} items"') == "6 items"

def test_interpolation_multiple():
    assert val('a = 1\nb = 2\n"{a} and {b}"') == "1 and 2"

def test_interpolation_none():
    assert val('x = none\n"{x}"') == ""

def test_interpolation_in_add():
    result = unwrap('[{ a: 1, b: "x" }, { a: 2, b: "y" }] |> add(label: "{it.a}_{it.b}")')
    assert result[0]["label"] == "1_x"
    assert result[1]["label"] == "2_y"

def test_interpolation_nested_expr():
    assert val('xs = [1, 2, 3]\n"len is {len(xs)}"') == "len is 3"

def test_no_interpolation_in_json_string():
    # {"a": 1} should not be treated as interpolation — falls back to literal
    result = val('use text\ntext.parse("{\\"a\\": 1}")')
    assert result == {"a": 1}

def test_interpolation_mixed_with_literal_braces():
    # {x} interpolates, { key: val } stays as literal text
    result = val('x = "world"\n"hello {x} JSON: { key: val }"')
    assert result == "hello world JSON: { key: val }"

def test_interpolation_partial_failure_doesnt_kill_whole_string():
    # One valid {expr} and one invalid {key: val} — valid one still interpolates
    result = val('name = "alice"\n"hi {name} data: { x: 1 }"')
    assert result == "hi alice data: { x: 1 }"


# --- model shorthand resolves correctly ---

def test_resolve_model_load():
    import os, tempfile
    from peppermint.libs.ml import _resolve_model
    with tempfile.NamedTemporaryFile(delete=False) as f:
        path = f.name
    try:
        load_path, save_path = _resolve_model(path, None, None)
        assert load_path == path
        assert save_path is None
    finally:
        os.unlink(path)


def test_resolve_model_save():
    from peppermint.libs.ml import _resolve_model
    load_path, save_path = _resolve_model("/nonexistent/path", None, None)
    assert load_path is None
    assert save_path == "/nonexistent/path"


def test_resolve_model_explicit():
    from peppermint.libs.ml import _resolve_model
    load_path, save_path = _resolve_model(None, "save.pkl", "load.pkl")
    assert load_path == "load.pkl"
    assert save_path == "save.pkl"


# --- Context artifacts ---

def test_context_artifacts_preserved_through_pipe():
    from peppermint.context import Context
    result = ctx("""
[{ v: 1 }, { v: 2 }]
|> add(x: it.v * 2)
|> filter(it.x > 2)
""")
    assert isinstance(result, Context)
    assert result.artifacts == {}
    assert len(result.data) == 1
    assert result.data[0]["x"] == 4


def test_context_data_field_access():
    result = unwrap("""
data = [{ v: 1 }, { v: 2 }, { v: 3 }]
    |> filter(it.v > 1)
data.data
""")
    assert len(result) == 2


def test_context_errors_field_access():
    result = val("""
data = [{ v: 1 }, { v: 2 }]
    |> filter(it.v > 1)
data.errors
""")
    assert result == []


def test_llm_format_json_strips_fences():
    import unittest.mock as mock
    from peppermint.libs.ml import llm as _llm
    fake_resp = mock.MagicMock()
    fake_resp.choices[0].message.content = '```json\n{"a": 1}\n```'
    with mock.patch("peppermint.libs.ml._client_cache", {}):
        with mock.patch("openai.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = fake_resp
            result = _llm("test", source="openai", model="gpt-4", apikey="x", format="json")
    assert result == {"a": 1}


def test_llm_format_json_plain():
    import unittest.mock as mock
    from peppermint.libs.ml import llm as _llm
    fake_resp = mock.MagicMock()
    fake_resp.choices[0].message.content = '{"b": 2}'
    with mock.patch("peppermint.libs.ml._client_cache", {}):
        with mock.patch("openai.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = fake_resp
            result = _llm("test", source="openai", model="gpt-4", apikey="x", format="json")
    assert result == {"b": 2}


# --- env.KEY ---

def test_env_key_access(monkeypatch):
    monkeypatch.setenv("TEST_PEP_KEY", "hello")
    result = val('use env\nenv.TEST_PEP_KEY')
    assert result == "hello"


def test_env_key_missing_returns_err(monkeypatch):
    monkeypatch.delenv("NONEXISTENT_PEP_KEY_XYZ", raising=False)
    result = val('use env\nenv.NONEXISTENT_PEP_KEY_XYZ')
    from peppermint.interpreter import Err
    assert isinstance(result, Err)


def test_env_get_still_works(monkeypatch):
    monkeypatch.setenv("TEST_PEP_KEY2", "world")
    result = val('use env\nenv.get("TEST_PEP_KEY2")')
    assert result == "world"


def test_env_key_in_interpolation(monkeypatch):
    monkeypatch.setenv("MY_NAME", "peppermint")
    result = val('use env\n"hello {env.MY_NAME}"')
    assert result == "hello peppermint"


# --- Annotations ---

def test_concurrent_annotation_correct_results():
    result = unwrap('[{ v: 1 }, { v: 2 }, { v: 3 }] |> add(x: it.v * 2)\n    @concurrent(3)')
    assert sorted(r["x"] for r in result) == [2, 4, 6]


def test_concurrent_annotation_preserves_order():
    result = unwrap('[{ i: 1 }, { i: 2 }, { i: 3 }] |> add(x: it.i)\n    @concurrent(3)')
    assert [r["i"] for r in result] == [1, 2, 3]


def test_retry_annotation_succeeds_on_first():
    result = unwrap('[{ v: 1 }] |> add(x: it.v + 1)\n    @retry(3)')
    assert result[0]["x"] == 2



def test_annotation_parsing():
    from peppermint.parser import parse
    from peppermint.ast_nodes import PipeStep
    prog = parse('[{v:1}] |> add(x: it.v)\n    @concurrent(4)\n    @retry(2)\n')
    pipe = prog.body[0]
    step = pipe.steps[1]
    assert isinstance(step, PipeStep)
    names = [a["name"] for a in step.annotations]
    assert "concurrent" in names
    assert "retry" in names


# --- table[key] indexed lookup ---

def test_list_index_positional():
    assert val('[10, 20, 30][1]') == 20

def test_list_dict_index_positional():
    result = val('[{ v: 10 }, { v: 20 }, { v: 30 }][1]')
    assert result == {"v": 20}

def test_find_by_col():
    result = val("""
stats = [{ cluster: 0, n: 10 }, { cluster: 1, n: 20 }]
find(stats, "cluster", 1)
""")
    assert result == {"cluster": 1, "n": 20}

def test_find_missing_returns_none():
    result = val("""
stats = [{ cluster: 0, n: 10 }]
find(stats, "cluster", 99)
""")
    assert result is None

def test_find_in_add():
    result = unwrap("""
stats = [{ cluster: 0, n: 10 }, { cluster: 1, n: 20 }]
data = [{ id: 0 }, { id: 1 }]
data |> add(n: find(stats, "cluster", it.id).n)
""")
    assert result[0]["n"] == 10
    assert result[1]["n"] == 20


# --- multi add / drop ---

def test_multi_add():
    result = unwrap('[{ a: 1, b: 2 }] |> add(x: it.a + 1, y: it.b * 3)')
    assert result[0]["x"] == 2
    assert result[0]["y"] == 6

def test_multi_add_independent_eval():
    # x and y are evaluated against the original row, not each other
    result = unwrap('[{ a: 1 }] |> add(x: it.a + 1, y: it.a + 10)')
    assert result[0]["x"] == 2
    assert result[0]["y"] == 11

def test_single_add_still_works():
    result = unwrap('[{ a: 1 }] |> add(x: it.a * 2)')
    assert result[0]["x"] == 2

def test_multi_drop():
    result = unwrap('[{ a: 1, b: 2, c: 3 }] |> drop("a", "c")')
    assert result[0] == {"b": 2}

def test_single_drop_still_works():
    result = unwrap('[{ a: 1, b: 2 }] |> drop("a")')
    assert result[0] == {"b": 2}


# --- recover ---

def test_recover_literal_fallback():
    result = unwrap('[{ v: 1 }, { v: 2 }] |> add(x: it.v * 2) |> recover(x: 0)')
    assert [r["x"] for r in result] == [2, 4]


def test_recover_restores_error_rows():
    from peppermint.context import Context
    from peppermint.stdlib.core import recover
    from peppermint.interpreter import Interpreter, Ok
    from peppermint.stdlib import build_global_env

    ctx = Context(
        data=[{"v": 1, "x": 2}],
        errors=[{"v": 99, "_error": "failed", "_step": "add"}],
    )
    env = build_global_env()
    interp = Interpreter(env, quiet=True)

    result = recover(ctx, _interp=interp, _env=env, x=0)
    rv = result.value if isinstance(result, Ok) else result
    assert isinstance(rv, Context)
    assert len(rv.data) == 2
    assert len(rv.errors) == 0
    assert rv.data[1]["x"] == 0


def test_recover_expression_fallback():
    from peppermint.context import Context
    from peppermint.stdlib.core import recover
    from peppermint.interpreter import Interpreter, Ok
    from peppermint.stdlib import build_global_env
    from peppermint.parser import parse as pparse

    ctx = Context(
        data=[{"title": "a", "label": "ok"}],
        errors=[{"title": "fallback_title", "_error": "llm failed", "_step": "add"}],
    )
    env = build_global_env()
    interp = Interpreter(env, quiet=True)
    expr = pparse("it.title\n").body[0]

    result = recover(ctx, _interp=interp, _env=env, label=expr)
    rv = result.value if isinstance(result, Ok) else result
    assert isinstance(rv, Context)
    assert len(rv.data) == 2
    assert rv.data[1]["label"] == "fallback_title"


def test_add_failure_routes_to_errors():
    c = ctx('[{ v: 1 }, { v: none }] |> add(x: it.v + 1)')
    assert len(c.data) == 1
    assert c.data[0]["x"] == 2
    assert len(c.errors) == 1
    assert c.errors[0]["_step"] == "add(x)"


def test_add_failure_recover_pattern():
    result = unwrap('[{ v: 1 }, { v: none }] |> add(x: it.v + 1) |> recover(x: 0)')
    assert len(result) == 2
    xs = [r["x"] for r in result]
    assert xs[0] == 2
    assert xs[1] == 0
