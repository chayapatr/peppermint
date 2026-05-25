"""Tests for peppermint.bridge pep_fn, pep_fn_lazy, and pep_fn_static decorators."""
from peppermint.bridge import pep_fn, pep_fn_lazy, pep_fn_static, ok, err
from peppermint.interpreter import Err


# --- fixtures ---

@pep_fn
def _add(x, y=0):
    return x + y

@pep_fn
def _always_err(x):
    return err("nope")

@pep_fn
def _raises(x):
    raise ValueError("boom")

@pep_fn_static
def _static_add(x, y=0):
    return x + y

@pep_fn_static
def _static_raises(x):
    raise ValueError("boom")


# --- pep_fn tests ---

def test_pep_fn_plain_args():
    assert _add(1, y=2) == 3

def test_pep_fn_exception_becomes_err():
    result = _raises(1)
    assert isinstance(result, Err)
    assert "boom" in result.msg

def test_pep_fn_passes_err_through():
    result = _always_err(1)
    assert isinstance(result, Err)
    assert result.msg == "nope"

def test_pep_fn_evaluates_ast_node_kwarg():
    class FakeNode:
        pass

    class FakeInterp:
        def eval(self, node, env):
            return 42

    assert _add(1, y=FakeNode(), _interp=FakeInterp(), _env={}) == 43

def test_pep_fn_skips_eval_for_plain_values():
    class StrictInterp:
        def eval(self, node, env):
            raise RuntimeError("should not be called")

    assert _add(1, y=2, _interp=StrictInterp(), _env={}) == 3

def test_pep_fn_skips_eval_for_none():
    class StrictInterp:
        def eval(self, node, env):
            raise RuntimeError("should not be called")

    assert _add(1, y=0, _interp=StrictInterp(), _env={}) == 1

def test_pep_fn_preserves_function_name():
    assert _add.__name__ == "_add"

def test_pep_fn_lazy_is_alias():
    assert pep_fn_lazy is pep_fn


# --- pep_fn_static tests ---

def test_pep_fn_static_plain_args():
    assert _static_add(1, y=2) == 3

def test_pep_fn_static_exception_becomes_err():
    result = _static_raises(1)
    assert isinstance(result, Err)
    assert "boom" in result.msg

def test_pep_fn_static_strips_meta_kwargs():
    assert _static_add(1, y=2, _interp=object(), _env={}, _block=None) == 3

def test_pep_fn_static_preserves_function_name():
    assert _static_add.__name__ == "_static_add"
