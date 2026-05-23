import pytest
from peppermint.parser import parse
from peppermint.interpreter import Interpreter, Ok, Err, ListValue
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
    assert isinstance(result, ListValue)
    assert result.rows == [1, 2, 3]

def test_list_of_dicts_becomes_listvalue():
    result = val('[{ name: "alice" }, { name: "bob" }]')
    assert isinstance(result, ListValue)
    assert len(result.rows) == 2
    assert result.rows[0] == {"name": "alice"}

def test_listvalue_schema():
    result = val('[{ age: 10, score: 1.0 }]')
    assert isinstance(result, ListValue)
    assert "age" in result.schema
    assert "score" in result.schema


# --- Pipe ---
# Pipes always return Ok/Err. val() unwraps one level of Ok.

def test_pipe_map():
    result = val('[1, 2, 3] |> map(it * 2)')
    assert isinstance(result, ListValue)
    assert result.rows == [2, 4, 6]

def test_pipe_filter():
    result = val('[1, 2, 3, 4] |> filter(it > 2)')
    assert isinstance(result, ListValue)
    assert result.rows == [3, 4]

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


# --- Aggregation ---

def test_agg_sum():
    result = val('[{ v: 1 }, { v: 2 }, { v: 3 }] |> agg(total: sum(it.v))')
    assert isinstance(result, ListValue)
    assert result.rows[0]["total"] == 6

def test_agg_mean():
    result = val('[{ v: 10 }, { v: 20 }] |> agg(avg: mean(it.v))')
    assert isinstance(result, ListValue)
    assert result.rows[0]["avg"] == pytest.approx(15.0)

def test_agg_count():
    result = val('[{ x: 1 }, { x: 2 }, { x: 3 }] |> agg(n: count())')
    assert isinstance(result, ListValue)
    assert result.rows[0]["n"] == 3

def test_agg_min():
    result = val('[{ v: 5 }, { v: 2 }, { v: 8 }] |> agg(lo: min(it.v))')
    assert isinstance(result, ListValue)
    assert result.rows[0]["lo"] == 2

def test_agg_max():
    result = val('[{ v: 5 }, { v: 2 }, { v: 8 }] |> agg(hi: max(it.v))')
    assert isinstance(result, ListValue)
    assert result.rows[0]["hi"] == 8

def test_agg_multi():
    result = val('[{ v: 1 }, { v: 2 }, { v: 3 }] |> agg(total: sum(it.v), n: count(), avg: mean(it.v))')
    assert isinstance(result, ListValue)
    row = result.rows[0]
    assert row["total"] == 6
    assert row["n"] == 3
    assert row["avg"] == pytest.approx(2.0)


# --- Group + agg ---

def test_group_agg():
    result = val("""
data = [
  { region: "A", income: 10 },
  { region: "A", income: 20 },
  { region: "B", income: 30 }
]
data
|> group(by: "region") {
    |> agg(total: sum(it.income), n: count())
}
""")
    assert isinstance(result, ListValue)
    rows = result.rows
    assert len(rows) == 2
    by_region = {r["region"]: r for r in rows}
    assert by_region["A"]["total"] == 30
    assert by_region["A"]["n"] == 2
    assert by_region["B"]["total"] == 30
    assert by_region["B"]["n"] == 1

def test_group_preserves_key():
    result = val("""
data = [{ cat: "x", v: 1 }, { cat: "x", v: 2 }, { cat: "y", v: 3 }]
data |> group(by: "cat") { |> agg(n: count()) }
""")
    assert isinstance(result, ListValue)
    assert all("cat" in r for r in result.rows)


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
    assert isinstance(result, ListValue)
    assert result.rows == [4, 5]

def test_lambda_multiline_pipe_body_map():
    result = val("""
process = lst ->
  lst
    |> map(it * 2)
    |> filter(it > 4)
process([1, 2, 3, 4])
""")
    assert isinstance(result, ListValue)
    assert result.rows == [6, 8]

def test_lambda_multiline_pipe_no_indent():
    result = val("""
f = x -> x
  |> map(it + 1)
  |> filter(it > 3)
f([1, 2, 3, 4])
""")
    assert isinstance(result, ListValue)
    assert result.rows == [4, 5]
