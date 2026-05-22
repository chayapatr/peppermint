import pytest
from peppermint.parser import parse
from peppermint.ast_nodes import *


def stmt(src: str):
    return parse(src).body[0]


def expr(src: str):
    node = stmt(src)
    if isinstance(node, Assign):
        return node.value
    return node


# --- Literals ---

def test_int():
    node = expr("42")
    assert isinstance(node, IntLit) and node.value == 42

def test_float():
    node = expr("3.14")
    assert isinstance(node, FloatLit) and node.value == 3.14

def test_str():
    node = expr('"hello"')
    assert isinstance(node, StrLit) and node.value == "hello"

def test_true():
    node = expr("true")
    assert isinstance(node, BoolLit) and node.value is True

def test_false():
    node = expr("false")
    assert isinstance(node, BoolLit) and node.value is False

def test_none():
    assert isinstance(expr("none"), NoneLit)


# --- Assignment ---

def test_assign_int():
    node = stmt("x = 42")
    assert isinstance(node, Assign)
    assert node.name == "x"
    assert isinstance(node.value, IntLit) and node.value.value == 42

def test_assign_expr():
    node = stmt("x = 1 + 2")
    assert isinstance(node, Assign)
    assert isinstance(node.value, BinOp)


# --- Field access ---

def test_field_simple():
    node = expr("it.age")
    assert isinstance(node, FieldAccess)
    assert isinstance(node.obj, Ident)
    assert node.obj.name == "it"
    assert node.field == "age"

def test_field_chain():
    node = expr("it.a.b")
    assert isinstance(node, FieldAccess)
    assert node.field == "b"
    assert isinstance(node.obj, FieldAccess)
    assert node.obj.field == "a"


# --- Binary ops ---

def test_binop_add():
    node = expr("x + y")
    assert isinstance(node, BinOp)
    assert node.op == "+"

def test_binop_cmp():
    node = expr("it.age > 18")
    assert isinstance(node, BinOp)
    assert node.op == ">"
    assert isinstance(node.left, FieldAccess)
    assert isinstance(node.right, IntLit)

def test_binop_div():
    node = expr("it.income / it.age")
    assert isinstance(node, BinOp)
    assert node.op == "/"

def test_binop_precedence():
    # x + y * z  should parse as x + (y * z)
    node = expr("x + y * z")
    assert isinstance(node, BinOp)
    assert node.op == "+"
    assert isinstance(node.right, BinOp)
    assert node.right.op == "*"


# --- Calls ---

def test_call_no_args():
    node = expr("load()")
    assert isinstance(node, Call)
    assert isinstance(node.func, Ident)
    assert node.func.name == "load"
    assert node.args == []
    assert node.kwargs == {}

def test_call_posarg():
    node = expr('load("data.csv")')
    assert isinstance(node, Call)
    assert len(node.args) == 1
    assert isinstance(node.args[0], StrLit)

def test_call_kwarg():
    node = expr("kmeans(k: 5)")
    assert isinstance(node, Call)
    assert node.args == []
    assert "k" in node.kwargs
    assert isinstance(node.kwargs["k"], IntLit)

def test_call_ns():
    node = expr("ml.kmeans(k: 5)")
    assert isinstance(node, Call)
    assert isinstance(node.func, FieldAccess)
    assert node.func.field == "kmeans"
    assert isinstance(node.func.obj, Ident)
    assert node.func.obj.name == "ml"


# --- Pipes ---

def test_pipe_simple():
    node = expr('load("data.csv") |> filter(it.age > 18)')
    assert isinstance(node, Pipe)
    assert len(node.steps) == 2
    assert isinstance(node.steps[0], Call)
    assert isinstance(node.steps[1], PipeStep)

def test_pipe_chain():
    node = expr('load("x") |> filter(it.age > 18) |> ml.kmeans(k: 5)')
    assert isinstance(node, Pipe)
    assert len(node.steps) == 3

def test_pipe_quiet():
    node = expr('load("x") |> filter(it.age > 18) quiet')
    assert isinstance(node, Pipe)
    step = node.steps[1]
    assert isinstance(step, PipeStep)
    assert step.quiet is True

def test_pipe_multiline():
    node = parse('load("x")\n|> filter(it.age > 18)\n|> ml.kmeans(k: 5)').body[0]
    assert isinstance(node, Pipe)
    assert len(node.steps) == 3


# --- Lambda ---

def test_lambda_single_param():
    node = expr("x => x * 2")
    assert isinstance(node, Lambda)
    assert node.params == ["x"]
    assert isinstance(node.body, BinOp)

def test_lambda_multi_param():
    node = expr("(x, y) => x + y")
    assert isinstance(node, Lambda)
    assert node.params == ["x", "y"]

def test_lambda_no_params():
    node = expr("() => 42")
    assert isinstance(node, Lambda)
    assert node.params == []

def test_lambda_assign():
    node = stmt("double = x => x * 2")
    assert isinstance(node, Assign)
    assert isinstance(node.value, Lambda)


# --- Collections ---

def test_list_lit():
    node = expr("[1, 2, 3]")
    assert isinstance(node, ListLit)
    assert len(node.items) == 3

def test_obj_lit():
    node = expr('{ name: "alice", age: 25 }')
    assert isinstance(node, ObjLit)
    assert len(node.entries) == 2
    assert isinstance(node.entries[0], ObjField)
    assert node.entries[0].key == "name"

def test_obj_spread():
    node = expr("{ ...row, score: 42 }")
    assert isinstance(node, ObjLit)
    assert isinstance(node.entries[0], ObjSpread)
    assert isinstance(node.entries[1], ObjField)

def test_range():
    node = expr("2..8")
    assert isinstance(node, Range)
    assert node.start == 2
    assert node.end == 8

def test_tuple_lit():
    node = expr("(a, b)")
    assert isinstance(node, TupleLit)
    assert len(node.items) == 2


# --- Match ---

def test_match_simple():
    node = expr('match(x, > 5: "hi", _: "lo")')
    assert isinstance(node, Match)
    assert len(node.arms) == 2
    assert isinstance(node.arms[0].pattern, PatComparison)
    assert node.arms[0].pattern.op == ">"
    assert node.arms[0].pattern.value == 5
    assert isinstance(node.arms[1].pattern, PatWildcard)

def test_match_all_cmp_ops():
    node = expr('match(x, > 1: "a", < 2: "b", >= 3: "c", <= 4: "d", == 5: "e", != 6: "f", _: "g")')
    ops = [arm.pattern.op for arm in node.arms[:-1]]
    assert ops == [">", "<", ">=", "<=", "==", "!="]

def test_match_result():
    node = expr('match(result, Ok(data): data, Err(msg): msg)')
    assert isinstance(node.arms[0].pattern, PatOk)
    assert node.arms[0].pattern.name == "data"
    assert isinstance(node.arms[1].pattern, PatErr)
    assert node.arms[1].pattern.name == "msg"

def test_match_tuple_pattern():
    node = expr('match((it.age, it.income), (> 30, > 50000): "senior high", _: "other")')
    assert isinstance(node.arms[0].pattern, PatTuple)
    assert len(node.arms[0].pattern.patterns) == 2


# --- Group block ---

def test_group_with_block():
    node = parse('data |> group(by: "region") {\n    |> filter(it.age > 18)\n}').body[0]
    assert isinstance(node, Pipe)
    group_step = node.steps[1]
    assert isinstance(group_step, PipeStep)
    call = group_step.expr
    assert isinstance(call, Call)
    assert call.block is not None
    assert len(call.block) == 1


# --- Use / Ns ---

def test_use_name():
    node = stmt("use ml")
    assert isinstance(node, UseDecl)
    assert node.path == "ml"
    assert node.alias is None

def test_use_as():
    node = stmt('use "./transforms" as t')
    assert isinstance(node, UseDecl)
    assert node.path == "./transforms"
    assert node.alias == "t"

def test_ns_decl():
    node = stmt("ns pipeline {\n  clean = x => x\n}")
    assert isinstance(node, NsDecl)
    assert node.name == "pipeline"
    assert len(node.body) == 1
    assert isinstance(node.body[0], Assign)


# --- Full spec example ---

def test_full_example_parses():
    prog = parse("""
use ml
use viz

clean = data => data

result = load("customers.csv")
  |> clean()
  |> ml.kmeans(k: 2..8)
  |> ml.umap(dims: 2)

result |> viz.scatter(x: "umap1", y: "umap2", color: "cluster")

load("customers.csv")
  |> group(by: "region") {
      |> ml.kmeans(k: 3)
  }
  |> viz.scatter(x: "umap1", y: "umap2", color: "cluster")
""")
    assert len(prog.body) == 6
    assert isinstance(prog.body[0], UseDecl)              # use ml
    assert isinstance(prog.body[1], UseDecl)              # use viz
    assert isinstance(prog.body[2], Assign)               # clean = ...
    assert isinstance(prog.body[3], Assign)               # result = load(...) |> ...
    assert isinstance(prog.body[3].value, Pipe)           # RHS is a full pipe
    assert len(prog.body[3].value.steps) == 4             # load + 3 pipe steps
    assert isinstance(prog.body[4], Pipe)                 # result |> viz.scatter(...)
    assert isinstance(prog.body[5], Pipe)                 # load(...) |> group(...) |> viz.scatter(...)
    assert len(prog.body[5].steps) == 3                   # load + group + scatter
