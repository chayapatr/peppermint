from peppermint.parser import parse
from peppermint.lsp.analyzer import analyze

def test_scope_captures_assignment():
    prog = parse('x = 42\ny = "hello"')
    result = analyze(prog)
    assert "x" in result.scope
    assert "y" in result.scope

def test_use_decl_adds_to_scope():
    prog = parse('use ml')
    result = analyze(prog)
    assert "ml" in result.scope

def test_no_undefined_for_stdlib():
    prog = parse('load("a.csv") |> filter(it.age > 18) |> print()')
    result = analyze(prog)
    assert result.undefined_refs == []

def test_undefined_ref_detected():
    prog = parse('x = undefined_var + 1')
    result = analyze(prog)
    names = [name for name, _ in result.undefined_refs]
    assert "undefined_var" in names

def test_lambda_param_in_scope():
    prog = parse('f = x -> x + 1')
    result = analyze(prog)
    assert all(name != "x" for name, _ in result.undefined_refs)

def test_type_inference_load():
    prog = parse('data = load("a.csv")')
    result = analyze(prog)
    assert result.scope["data"].type_hint == "List<Row>"

def test_type_inference_lambda():
    prog = parse('f = x -> x * 2')
    result = analyze(prog)
    assert result.scope["f"].type_hint == "fn"
