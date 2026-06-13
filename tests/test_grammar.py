import pytest
from peppermint.parser import parse as _parse, _normalize


def parse(src: str):
    _parse(_normalize(src.strip() + "\n"))


def ok(src: str):
    parse(src)


def err(src: str):
    with pytest.raises(Exception):
        parse(src)


# --- Literals ---

def test_int():         ok("42")
def test_float():       ok("3.14")
def test_string():      ok('"hello"')
def test_true():        ok("true")
def test_false():       ok("false")
def test_none():        ok("none")


# --- Assignment ---

def test_assign_int():      ok("x = 42")
def test_assign_str():      ok('x = "hello"')
def test_assign_bool():     ok("x = true")
def test_assign_expr():     ok("x = 1 + 2")


# --- Field access ---

def test_field_simple():    ok("it.age")
def test_field_chain():     ok("it.a.b.c")
def test_field_on_call():   ok("fn().field")


# --- Binary ops ---

def test_add():             ok("x + y")
def test_sub():             ok("x - y")
def test_mul():             ok("x * y")
def test_div():             ok("x / y")
def test_gt():              ok("x > 18")
def test_lt():              ok("x < 18")
def test_gte():             ok("x >= 18")
def test_lte():             ok("x <= 18")
def test_eq():              ok("x == 18")
def test_neq():             ok("x != 18")
def test_precedence():      ok("x + y * z")
def test_field_in_binop():  ok("it.age > 18")
def test_complex_binop():   ok("it.income / it.age")


# --- Calls ---

def test_call_no_args():    ok("load()")
def test_call_posarg():     ok('load("data.csv")')
def test_call_kwarg():      ok("kmeans(k: 5)")
def test_call_mixed():      ok('load("data.csv", sep: ",")')
def test_call_ns():         ok("ml.kmeans(k: 5)")
def test_call_trailing_comma(): ok("fn(a, b,)")


# --- Pipes ---

def test_pipe_simple():
    ok('load("data.csv") |> filter(it.age > 18)')

def test_pipe_chain():
    ok('load("data.csv") |> filter(it.age > 18) |> ml.kmeans(k: 5)')

def test_pipe_multiline():
    ok("""
load("data.csv")
|> filter(it.age > 18)
|> ml.kmeans(k: 5)
""")

def test_pipe_indented_multiline():
    ok("""
load("data.csv")
  |> filter(it.age > 18)
  |> ml.kmeans(k: 5)
""")

def test_pipe_quiet():
    ok('load("data.csv") |> filter(it.age > 18) quiet')


# --- Lambdas ---

def test_lambda_single():   ok("x -> x * 2")
def test_lambda_multi():    ok("(x, y) -> x + y")
def test_lambda_no_args():  ok("() -> 42")
def test_lambda_assign():   ok("double = x -> x * 2")
def test_lambda_in_pipe():  ok("data |> map(row -> row)")


# --- Collections ---

def test_list_empty():      ok("[]")
def test_list_ints():       ok("[1, 2, 3]")
def test_list_strings():    ok('["a", "b"]')
def test_list_trailing():   ok("[1, 2, 3,]")

def test_obj_empty():       ok("{}")
def test_obj_fields():      ok('{ name: "alice", age: 25 }')
def test_obj_trailing():    ok("{ a: 1, b: 2, }")
def test_obj_spread():      ok("{ ...row, score: 42 }")
def test_obj_spread_only(): ok("{ ...row }")


# --- Range ---

def test_range():           ok("2..8")
def test_range_in_call():   ok("kmeans(k: 2..8)")


# --- Spread ---

def test_spread_ident():    ok("...row")
def test_spread_field():    ok("...it.data")


# --- Match ---

def test_match_simple():
    ok('match(x, > 5: "hi", _: "lo")')

def test_match_all_ops():
    ok("""
match(x,
  > 10: "a",
  < 5: "b",
  >= 10: "c",
  <= 5: "d",
  == 7: "e",
  != 7: "f",
  _: "g"
)
""")

def test_match_result():
    ok("""
match(result,
  Ok(data): data,
  Err(msg): msg
)
""")


def test_match_multiline():
    ok("""
match(it.income,
  > 50000: "high",
  > 20000: "medium",
  _: "low"
)
""")


# --- Group with block ---

def test_group_block():
    ok("""
load("data.csv")
|> group(by: "region") {
    |> filter(it.age > 18)
    |> ml.kmeans(k: 3)
}
""")


# --- Namespace ---

def test_ns_empty():
    ok("""
ns pipeline {
}
""")

def test_ns_with_assigns():
    ok("""
ns pipeline {
  clean = data -> data
  threshold = 18
}
""")


# --- Use ---

def test_use_name():        ok("use ml")
def test_use_string():      ok('use "./transforms"')
def test_use_as():          ok('use "./transforms" as t')
def test_use_name_as():     ok("use ml as myml")


# --- Unary minus ---

def test_unary_minus_int():     ok("-1")
def test_unary_minus_float():   ok("-3.14")
def test_unary_minus_expr():    ok("-(x + 1)")
def test_unary_minus_in_binop():ok("0 - -1")
def test_unary_minus_in_call(): ok("f(-1)")


# --- Modulo ---

def test_modulo():          ok("x % 3")
def test_modulo_expr():     ok("it.age % 2 == 0")


# --- Aggregation ---

def test_agg_single():      ok('data |> agg(total: sum(it.income))')
def test_agg_multi():       ok('data |> agg(total: sum(it.income), avg: mean(it.income), n: count())')
def test_agg_after_group():
    ok("""
load("data.csv")
|> group(by: "region") {
    |> agg(total: sum(it.income), n: count())
}
""")

def test_sum_call():        ok("sum(it.income)")
def test_mean_call():       ok("mean(it.value)")
def test_count_call():      ok("count()")
def test_min_call():        ok("min(it.age)")
def test_max_call():        ok("max(it.score)")


# --- Object shorthand ---

def test_obj_shorthand_single():    ok("{ x }")
def test_obj_shorthand_multi():     ok("{ x, y, z }")
def test_obj_shorthand_mixed():     ok("{ x, name: \"alice\", y }")


# --- Arrow (lambda) ---

def test_arrow_single():    ok("x -> x * 2")
def test_arrow_multi():     ok("(x, y) -> x + y")
def test_arrow_noargs():    ok("() -> 42")


# --- Semicolons ---

def test_semi_in_parens():  ok("(print(x); f(x))")
def test_semi_multiline():
    ok("""
f = x -> (
  print(x);
  f(x - 1)
)
""")


# --- Sequence expressions ---

def test_seq_two():         ok("(a; b)")
def test_seq_three():       ok("(a; b; c)")
def test_seq_with_pipe():
    ok("""
f = x -> (
  print(x)
  |> f()
)
""")


# --- Multiline lambda body ---

def test_lambda_body_multiline():
    ok("""
clean = data -> (
  data
    |> filter(it.age > 18)
    |> filter(it.income > 0)
)
""")

def test_lambda_body_multiargs():
    ok("""
process = (x, y) -> (
  x + y
)
""")


# --- Multiline kwarg value ---

def test_kwarg_multiline_value():
    ok("""
data |> add(label:
  match(it.x, > 0: "pos", _: "neg"))
""")


# --- Full example from spec ---

# --- Parse errors (err() helper was previously unused) ---

def test_err_unterminated_string():    err('"hello')
def test_err_unterminated_empty():     err('"')
def test_err_unknown_char_dollar():    err('x $ y')
def test_err_unknown_char_backtick():  err('`x`')
def test_err_unknown_char_at_start():  err('$ x')


def test_full_spec_example():
    ok("""
use ml
use viz

clean = data -> data
engineer = data -> data

result = load("customers.csv")
  |> clean()
  |> engineer()
  |> ml.kmeans(k: 2..8, score: silhouette)
  |> ml.umap(dims: 2)

result |> viz.scatter(x: "umap_1", y: "umap_2", color: "cluster")
result |> viz.scatter(x: "umap_1", y: "umap_2", color: "segment")

load("customers.csv")
  |> clean()
  |> engineer()
  |> group(by: "region") {
      |> ml.kmeans(k: 3)
  }
  |> viz.scatter(x: "umap_1", y: "umap_2", color: "cluster")
""")
