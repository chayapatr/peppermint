"""Tests for peppermint.bridge.pep_fn decorator."""
import pytest
from peppermint.bridge import pep_fn, ok, err
from peppermint.interpreter import Ok, Err


@pep_fn
def _add(x, y=0):
    return x + y


@pep_fn
def _always_err(x):
    return err("nope")


@pep_fn
def _raises(x):
    raise ValueError("boom")


@pep_fn
def _identity(x, val=None):
    return val


def test_pep_fn_plain_args():
    result = _add(1, y=2)
    assert result == 3


def test_pep_fn_returns_plain_value():
    assert _add(10, y=5) == 15


def test_pep_fn_exception_becomes_err():
    result = _raises(1)
    assert isinstance(result, Err)
    assert "boom" in result.msg


def test_pep_fn_passes_err_through():
    result = _always_err(1)
    assert isinstance(result, Err)
    assert result.msg == "nope"


def test_pep_fn_evaluates_kwarg_via_interp():
    """_interp.eval should be called on unevaluated AST node kwargs."""
    class FakeNode:
        pass  # not a plain int/str/bool/list — looks like an AST node

    class FakeInterp:
        def eval(self, node, env):
            return 42

    result = _add(1, y=FakeNode(), _interp=FakeInterp(), _env={})
    assert result == 43  # 1 + 42


def test_pep_fn_skips_eval_for_plain_values():
    """Plain str/int/bool/list should not be passed through interp.eval."""
    class StrictInterp:
        def eval(self, node, env):
            raise RuntimeError("should not be called")

    result = _add(1, y=2, _interp=StrictInterp(), _env={})
    assert result == 3


def test_pep_fn_none_kwarg_not_evaluated():
    class StrictInterp:
        def eval(self, node, env):
            raise RuntimeError("should not be called")

    result = _identity(1, val=None, _interp=StrictInterp(), _env={})
    assert result is None


def test_pep_fn_preserves_function_name():
    assert _add.__name__ == "_add"
