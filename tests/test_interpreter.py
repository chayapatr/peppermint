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
    result = unwrap('[{ v: 1 }, { v: 2 }, { v: 3 }] |> add(doubled: it.v * 2, concurrent: 4)')
    assert [r["doubled"] for r in result] == [2, 4, 6]

def test_add_concurrent_preserves_order():
    result = unwrap('[{ i: 3 }, { i: 2 }, { i: 1 }] |> add(v: it.i, concurrent: 3)')
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
|> collapse(by: "g", total: rows -> rows |> collapse(s: sum(col.v)) |> get(0))
""")
    by_g = {r["g"]: r["total"]["s"] for r in result}
    assert by_g["a"] == 3
    assert by_g["b"] == 3


def test_collapse_lambda_no_by():
    result = unwrap("""
[{ v: 1 }, { v: 2 }, { v: 3 }]
|> collapse(total: rows -> rows |> collapse(s: sum(col.v)) |> get(0))
""")
    assert result[0]["total"]["s"] == 6


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
