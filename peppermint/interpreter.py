from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .ast_nodes import *


# --- Runtime values ---

@dataclass
class Ok:
    value: Any
    def __repr__(self): return f"Ok({self.value!r})"

@dataclass
class Err:
    msg: str
    def __repr__(self): return f"Err({self.msg!r})"

@dataclass
class ListValue:
    rows: list[dict]
    schema: dict[str, type]

    def __repr__(self):
        return f"List  {len(self.rows)} rows × {len(self.schema)} cols"

@dataclass
class PmFunction:
    params: list[str]
    body: Any   # Expr
    closure: "Env"

    def __repr__(self): return f"<fn({', '.join(self.params)})>"

@dataclass
class PmRange:
    start: int
    end: int


# --- Environment ---

class Env:
    def __init__(self, parent: "Env | None" = None):
        self._vars: dict[str, Any] = {}
        self.parent = parent

    def get(self, name: str) -> Any:
        if name in self._vars:
            return self._vars[name]
        if self.parent:
            return self.parent.get(name)
        raise PepError(f"undefined variable '{name}'")

    def set(self, name: str, value: Any):
        self._vars[name] = value

    def extend(self, bindings: dict[str, Any]) -> "Env":
        child = Env(parent=self)
        for k, v in bindings.items():
            child.set(k, v)
        return child


class PepError(Exception):
    pass


# --- Interpreter ---

class Interpreter:
    def __init__(self, global_env: Env, quiet: bool = False):
        self.env = global_env
        self.quiet = quiet

    def run(self, program: Program) -> Any:
        result = None
        for node in program.body:
            result = self.eval(node, self.env)
        return result

    def eval(self, node, env: Env) -> Any:
        match node:
            case IntLit(value=v):       return v
            case FloatLit(value=v):     return v
            case StrLit(value=v):       return v
            case BoolLit(value=v):      return v
            case NoneLit():             return None
            case Range(start=s, end=e): return PmRange(s, e)
            case Ident(name=n):         return env.get(n)
            case Assign():              return self.eval_assign(node, env)
            case UseDecl():             return self.eval_use(node, env)
            case NsDecl():              return self.eval_ns(node, env)
            case Lambda():              return PmFunction(node.params, node.body, env)
            case FieldAccess():         return self.eval_field(node, env)
            case BinOp():               return self.eval_binop(node, env)
            case Call():                return self.eval_call(node, None, env)
            case Pipe():                return self.eval_pipe(node, env)
            case Match():               return self.eval_match(node, env)
            case ListLit():             return [self.eval(i, env) for i in node.items]
            case TupleLit():            return tuple(self.eval(i, env) for i in node.items)
            case ObjLit():              return self.eval_obj(node, env)
            case Spread(obj=o):         return self.eval(o, env)
            case _:
                raise PepError(f"cannot eval node: {type(node).__name__}")

    # --- Assignment ---

    def eval_assign(self, node: Assign, env: Env) -> Any:
        value = self.eval(node.value, env)
        env.set(node.name, value)
        return value

    # --- Use / Ns ---

    def eval_use(self, node: UseDecl, env: Env) -> None:
        if node.path in ("ml", "viz", "math", "io"):
            ns = env.get(f"_ns_{node.path}")
            target = node.alias or node.path
            env.set(target, ns)
        else:
            # file import — eval the file and store under alias
            import os
            from .parser import parse as pep_parse
            path = node.path
            if not os.path.isabs(path):
                path = os.path.join(os.getcwd(), path)
            src = open(path).read()
            prog = pep_parse(src)
            child_env = Env(parent=env)
            child_interp = Interpreter(child_env, quiet=True)
            child_interp.run(prog)
            alias = node.alias or os.path.splitext(os.path.basename(path))[0]
            env.set(alias, child_env._vars)
        return None

    def eval_ns(self, node: NsDecl, env: Env) -> None:
        ns_env = Env(parent=env)
        for assign in node.body:
            self.eval_assign(assign, ns_env)
        env.set(node.name, ns_env._vars)
        return None

    # --- Field access ---

    def eval_field(self, node: FieldAccess, env: Env) -> Any:
        obj = self.eval(node.obj, env)
        if isinstance(obj, dict):
            if node.field not in obj:
                available = ", ".join(obj.keys())
                raise PepError(f"field '{node.field}' does not exist. available: {available}")
            return obj[node.field]
        raise PepError(f"cannot access field '{node.field}' on {type(obj).__name__}")

    # --- Binary ops ---

    def eval_binop(self, node: BinOp, env: Env) -> Any:
        left = self.eval(node.left, env)
        right = self.eval(node.right, env)
        match node.op:
            case "+":  return left + right
            case "-":  return left - right
            case "*":  return left * right
            case "/":  return left / right
            case ">":  return left > right
            case "<":  return left < right
            case ">=": return left >= right
            case "<=": return left <= right
            case "==": return left == right
            case "!=": return left != right
            case _: raise PepError(f"unknown operator '{node.op}'")

    # --- Object literal ---

    def eval_obj(self, node: ObjLit, env: Env) -> dict:
        result = {}
        for entry in node.entries:
            if isinstance(entry, ObjField):
                result[entry.key] = self.eval(entry.value, env)
            elif isinstance(entry, ObjSpread):
                val = self.eval(entry.obj, env)
                if isinstance(val, dict):
                    result.update(val)
                else:
                    raise PepError(f"spread requires an object, got {type(val).__name__}")
        return result

    # --- Pipe ---

    def eval_pipe(self, node: Pipe, env: Env) -> Any:
        # First step is the source expression
        result = self.eval(node.steps[0], env)

        for step in node.steps[1:]:
            if isinstance(result, Err):
                break  # short-circuit

            value = result.value if isinstance(result, Ok) else result

            if not isinstance(step, PipeStep):
                raise PepError(f"pipe step must be a PipeStep, got {type(step).__name__}")

            show = not (step.quiet or self.quiet)
            before = value if isinstance(value, ListValue) else None

            result = self.eval_call(step.expr, value, env)

            after = result.value if isinstance(result, Ok) else result
            if show and isinstance(before, ListValue) and isinstance(after, ListValue):
                self._print_step(step.expr, before, after)
            elif show and isinstance(after, ListValue) and before is None:
                self._print_step(step.expr, None, after)

        return result

    def _print_step(self, call_node, before: ListValue | None, after: ListValue):
        name = self._call_name(call_node)
        desc = f"|> {name}"
        rows = len(after.rows)
        cols = len(after.schema)
        line = f"{desc:<30} → List  {rows} rows × {cols} cols"
        if before is not None:
            dropped = len(before.rows) - rows
            added_cols = set(after.schema) - set(before.schema)
            if dropped > 0:
                line += f"  ({dropped} dropped)"
            if added_cols:
                line += f"  (+{', '.join(added_cols)})"
        import sys
        print(line, file=sys.stderr)

    def _call_name(self, node) -> str:
        if isinstance(node, Call):
            if isinstance(node.func, FieldAccess):
                return f"{self._call_name(node.func.obj)}.{node.func.field}"
            if isinstance(node.func, Ident):
                return node.func.name
        if isinstance(node, Ident):
            return node.name
        if isinstance(node, FieldAccess):
            return f"{self._call_name(node.obj)}.{node.field}"
        return "?"

    # --- Call ---

    def eval_call(self, node: Call, pipe_value: Any, env: Env) -> Any:
        # Resolve the callable
        if isinstance(node.func, FieldAccess):
            ns = self.eval(node.func.obj, env)
            if isinstance(ns, dict) and node.func.field in ns:
                fn = ns[node.func.field]
            else:
                raise PepError(f"'{self._call_name(node.func.obj)}' has no function '{node.func.field}'")
        elif isinstance(node.func, Ident):
            fn = env.get(node.func.name)
        else:
            fn = self.eval(node.func, env)

        # Inject pipe value as first positional arg (always evaluated)
        if pipe_value is not None:
            pre = [pipe_value]
        else:
            pre = []

        # Call
        if isinstance(fn, PmFunction):
            # PmFunctions get fully evaluated args
            args = pre + [self.eval(a, env) for a in node.args]
            kwargs = {k: self.eval(v, env) for k, v in node.kwargs.items()}
            return self._call_pm_function(fn, args, kwargs, node.block, env)
        elif callable(fn):
            # Stdlib Python functions: pass AST nodes for non-pipe args so they
            # can use make_row_fn for it-injection. Pipe value is already evaluated.
            args = pre + list(node.args)
            kwargs = dict(node.kwargs)  # AST nodes as values
            # Eagerly evaluate kwargs that are plain literals/idents (not row-dependent)
            # We pass raw AST + _interp/_env/_block so stdlib can decide
            try:
                result = fn(*args, **kwargs, _block=node.block, _env=env, _interp=self)
            except TypeError:
                result = fn(*args, **kwargs)
            # Unwrap nested Ok(Ok(...))
            while isinstance(result, Ok) and isinstance(result.value, Ok):
                result = result.value
            if not isinstance(result, (Ok, Err)):
                result = Ok(result)
            return result
        else:
            raise PepError(f"'{self._call_name(node.func)}' is not callable (got {type(fn).__name__})")

    def _call_pm_function(self, fn: PmFunction, args: list, kwargs: dict, block, env: Env) -> Any:
        if len(args) != len(fn.params):
            raise PepError(f"expected {len(fn.params)} args, got {len(args)}")
        bindings = dict(zip(fn.params, args))
        call_env = fn.closure.extend(bindings)
        result = self.eval(fn.body, call_env)
        if not isinstance(result, (Ok, Err)):
            result = Ok(result)
        return result

    # --- Match ---

    def eval_match(self, node: Match, env: Env) -> Any:
        subject = self.eval(node.subject, env)

        for arm in node.arms:
            matched, bindings = self._match_pattern(arm.pattern, subject)
            if matched:
                arm_env = env.extend(bindings)
                return self.eval(arm.body, arm_env)

        return Err("no match")

    def _match_pattern(self, pattern, value) -> tuple[bool, dict]:
        match pattern:
            case PatWildcard():
                return True, {}

            case PatComparison(op=op, value=v):
                match op:
                    case ">":  result = value > v
                    case "<":  result = value < v
                    case ">=": result = value >= v
                    case "<=": result = value <= v
                    case "==": result = value == v
                    case "!=": result = value != v
                    case _: result = False
                return result, {}

            case PatOk(name=n):
                if isinstance(value, Ok):
                    return True, {n: value.value}
                return False, {}

            case PatErr(name=n):
                if isinstance(value, Err):
                    return True, {n: value.msg}
                return False, {}

            case PatTuple(patterns=pats):
                if not isinstance(value, tuple) or len(value) != len(pats):
                    return False, {}
                all_bindings = {}
                for pat, val in zip(pats, value):
                    ok, bindings = self._match_pattern(pat, val)
                    if not ok:
                        return False, {}
                    all_bindings.update(bindings)
                return True, all_bindings

            case _:
                return False, {}

    # --- it injection ---

    def make_row_fn(self, expr_node, env: Env):
        """Wrap an expression that may use 'it' into a callable row -> value."""
        if isinstance(expr_node, Lambda):
            fn = PmFunction(expr_node.params, expr_node.body, env)
            def call_lambda(row):
                return self._call_pm_function(fn, [row], {}, None, env)
            return call_lambda
        else:
            def eval_with_it(row):
                row_env = env.extend({"it": row})
                return self.eval(expr_node, row_env)
            return eval_with_it
