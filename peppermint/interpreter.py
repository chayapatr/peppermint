from __future__ import annotations
import inspect
from dataclasses import dataclass
from typing import Any
from .ast_nodes import *

_fn_accepts_interp: dict = {}

def _check_accepts_interp(fn) -> bool:
    """Return True if fn accepts **kwargs or explicit _interp parameter."""
    cached = _fn_accepts_interp.get(id(fn))
    if cached is not None:
        return cached
    try:
        sig = inspect.signature(fn)
        result = any(
            p.kind == inspect.Parameter.VAR_KEYWORD or p.name == '_interp'
            for p in sig.parameters.values()
        )
    except (ValueError, TypeError):
        result = False
    _fn_accepts_interp[id(fn)] = result
    return result


# --- Tail call sentinel ---

@dataclass
class _TailCall:
    fn: "PmFunction"
    args: list
    env: "Env"


# --- Runtime values ---

@dataclass
class Ok:
    value: Any
    def __repr__(self): return f"Ok({self.value!r})"

@dataclass
class Err:
    msg: str
    cause: "PepError | None" = None
    def __repr__(self): return f"Err({self.msg!r})"

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

@dataclass
class ColRef:
    """Reference to a column across all rows — produced by col.field."""
    field: str
    def __repr__(self): return f"col.{self.field}"

class _ColProxy:
    """Sentinel object bound to 'col' in the global env."""
    def __getattr__(self, field: str) -> ColRef:
        return ColRef(field)
    def __repr__(self): return "col"


# --- Environment ---

class Env:
    def __init__(self, parent: "Env | None" = None):
        self._vars: dict[str, Any] = {}
        self.parent = parent

    def get(self, name: str, loc=None) -> Any:
        if name in self._vars:
            return self._vars[name]
        if self.parent:
            return self.parent.get(name, loc)
        raise PepError(f"undefined variable '{name}'", loc=loc, span=len(name))

    def set(self, name: str, value: Any):
        self._vars[name] = value

    def extend(self, bindings: dict[str, Any]) -> "Env":
        child = Env(parent=self)
        for k, v in bindings.items():
            child.set(k, v)
        return child


class PepError(Exception):
    def __init__(self, msg: str, loc: "Loc | None" = None, span: int = 0):
        super().__init__(msg)
        self.loc = loc
        self.span = span


# --- Interpreter ---

class Interpreter:
    def __init__(self, global_env: Env, quiet: bool = False, cache=None):
        self.env = global_env
        self.quiet = quiet
        self._cache = cache  # Cache instance or None

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
            case Range(start=s, end=e): return PmRange(self.eval(s, env), self.eval(e, env))
            case Ident(name=n, loc=l):  return env.get(n, loc=l)
            case Assign():              return self.eval_assign(node, env)
            case UseDecl():             return self.eval_use(node, env)
            case NsDecl():              return self.eval_ns(node, env)
            case Lambda():              return PmFunction(node.params, node.body, env)
            case FieldAccess():         return self.eval_field(node, env)
            case Neg():                 return -self.eval(node.operand, env)
            case BinOp():               return self.eval_binop(node, env)
            case Call():                return self.eval_call(node, None, env)
            case Pipe():                return self.eval_pipe(node, env)
            case Block():               return self.eval_block(node, env)
            case Match():               return self.eval_match(node, env)
            case ListLit():             return self.eval_list(node, env)
            case TupleLit():            return tuple(self.eval(i, env) for i in node.items)
            case ObjLit():              return self.eval_obj(node, env)
            case Spread(obj=o):         return self.eval(o, env)
            case Literal(value=v):              return v
            case InterpolatedStr(parts=parts):
                pieces = []
                for p in parts:
                    v = self.eval(p, env)
                    if isinstance(v, Ok): v = v.value
                    pieces.append("" if v is None else str(v))
                return "".join(pieces)
            case PmFunction() | PmRange() | Ok() | Err():
                return node  # already a runtime value, pass through
            case _ if not isinstance(node, type) and not hasattr(node, '__dataclass_fields__'):
                return node  # plain Python value (list, dict, int, etc.)
            case _:
                raise PepError(f"cannot eval node: {type(node).__name__}")

    # --- Assignment ---

    def eval_assign(self, node: Assign, env: Env) -> Any:
        value = self.eval(node.value, env)
        # Flatten nested Ok(Ok(...)) but preserve a single Ok/Err wrapper
        while isinstance(value, Ok) and isinstance(value.value, Ok):
            value = value.value
        env.set(node.name, value)
        if isinstance(value, PmFunction):
            value.closure.set(node.name, value)
        return value

    # --- Use / Ns ---

    def eval_use(self, node: UseDecl, env: Env) -> None:
        import os
        path = node.path

        from .stdlib import load_stdlib
        from pathlib import Path
        _libs_path = Path(__file__).parent / "libs"
        _is_stdlib = (
            (_libs_path / f"{path}.py").exists() or
            (_libs_path / f"{path}_.py").exists()
        )

        if _is_stdlib:
            ns = load_stdlib(path)
            target = node.alias or path
            env.set(target, ns)
        elif path.endswith(".py"):
            # Python file — load via bridge
            from .bridge import load_python_file
            if not os.path.isabs(path):
                path = os.path.join(os.getcwd(), path)
            fns = load_python_file(path)
            alias = node.alias or os.path.splitext(os.path.basename(path))[0]
            env.set(alias, fns)
        else:
            # .pep file — eval and expose as namespace
            from .parser import parse as pep_parse
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
        from .context import Context
        obj = self.eval(node.obj, env)
        if isinstance(obj, Ok):
            obj = obj.value
        if isinstance(obj, Context):
            if node.field == "data":
                return obj.data
            if node.field == "errors":
                return obj.errors
            if node.field in obj.artifacts:
                return obj.artifacts[node.field]
            available = "data, errors" + (", " + ", ".join(obj.artifacts) if obj.artifacts else "")
            raise PepError(f"context has no field '{node.field}'. available: {available}", loc=node.loc, span=len(node.field))
        if isinstance(obj, _ColProxy):
            return ColRef(node.field)
        if isinstance(obj, dict):
            if node.field not in obj:
                if hasattr(obj, '__missing__'):
                    return obj.__missing__(node.field)
                available = ", ".join(obj.keys())
                raise PepError(f"field '{node.field}' does not exist. available: {available}", loc=node.loc, span=len(node.field))
            return obj[node.field]
        raise PepError(f"cannot access field '{node.field}' on {type(obj).__name__}", loc=node.loc, span=len(node.field))

    # --- Binary ops ---

    def eval_binop(self, node: BinOp, env: Env) -> Any:
        # Short-circuit for and/or/not
        if node.op == "and":
            left = self.eval(node.left, env)
            left = left.value if isinstance(left, Ok) else left
            return left and self.eval(node.right, env)
        if node.op == "or":
            left = self.eval(node.left, env)
            left = left.value if isinstance(left, Ok) else left
            return left or self.eval(node.right, env)
        if node.op == "not":
            left = self.eval(node.left, env)
            left = left.value if isinstance(left, Ok) else left
            return not left
        left = self.eval(node.left, env)
        right = self.eval(node.right, env)
        left = left.value if isinstance(left, Ok) else left
        right = right.value if isinstance(right, Ok) else right
        match node.op:
            case "+":  return left + right
            case "-":  return left - right
            case "*":  return left * right
            case "/":  return left / right
            case "%":  return left % right
            case ">":  return left > right
            case "<":  return left < right
            case ">=": return left >= right
            case "<=": return left <= right
            case "==": return left == right
            case "!=": return left != right
            case _: raise PepError(f"unknown operator '{node.op}'")

    # --- List literal ---

    def eval_list(self, node, env: Env):
        items = [self.eval(i, env) for i in node.items]
        return [i.value if isinstance(i, Ok) else i for i in items]

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
            elif isinstance(entry, ObjShorthand):
                try:
                    result[entry.key] = env.get(entry.key)
                except Exception:
                    result[entry.key] = True
        return result

    # --- Pipe ---

    def eval_block(self, node: Block, env: Env) -> Any:
        block_env = Env(parent=env)
        result = None
        for stmt in node.stmts:
            result = self.eval(stmt, block_env)
        return result

    def eval_pipe(self, node: Pipe, env: Env, depth: int = 0) -> Any:
        # Source enters the pipe — always wrap in Ok so every step sees Result
        first = node.steps[0]
        source = self.eval(first, env)
        result = source if isinstance(source, (Ok, Err)) else Ok(source)

        for step in node.steps[1:]:
            if isinstance(result, Err):
                break  # short-circuit

            value = result.value  # always Ok here, safe to unwrap

            if not isinstance(step, PipeStep):
                raise PepError(f"pipe step must be a PipeStep, got {type(step).__name__}")

            show = not (step.quiet or self.quiet)
            from .context import Context as _Ctx
            before = value.data if isinstance(value, _Ctx) else (value if isinstance(value, list) else None)

            try:
                expr = step.expr
                if isinstance(expr, (Ident, FieldAccess)):
                    expr = Call(func=expr, args=[], kwargs={}, block=None, loc=expr.loc)

                # Cache check
                ck = None
                if self._cache:
                    from .cache import cache_key_for_step
                    step_src = self._call_name(step.expr)
                    ck = cache_key_for_step(step_src, value)
                    cached = self._cache.get_step(ck)
                    if cached is not None:
                        result = Ok(cached)
                        after = cached
                        from .context import Context as _Ctx
                        after_list = after.data if isinstance(after, _Ctx) else (after if isinstance(after, list) else None)
                        if show and after_list is not None:
                            self._print_step(step.expr, before, after_list, depth=depth, cached=True)
                        continue

                step_result = self.eval_call(expr, value, env, depth=depth)
                result = step_result if isinstance(step_result, (Ok, Err)) else Ok(step_result)

                # Cache write
                if ck and isinstance(result, Ok):
                    self._cache.set_step(ck, result.value)

            except PepError as e:
                step_name = self._call_name(step.expr)
                result = Err(f"{step_name}: {e}", cause=e)
            except Exception as e:
                step_name = self._call_name(step.expr)
                result = Err(f"{step_name}: {e}")

            after = result.value if isinstance(result, Ok) else result
            from .context import Context as _Ctx
            after_list = after.data if isinstance(after, _Ctx) else (after if isinstance(after, list) else None)
            if show and after_list is not None:
                self._print_step(step.expr, before, after_list, depth=depth)

        # If the pipe started with an assignment (x = source |> ...), update x to the final result
        if isinstance(first, Assign):
            final = result.value if isinstance(result, Ok) else result
            env.set(first.name, final)

        return result

    def _print_step(self, call_node, before: list | None, after: list, depth: int = 0, cached: bool = False):
        import sys
        indent = "  " * depth
        name = self._call_name(call_node)
        desc = f"{indent}\033[2m|>\033[0m \033[36m{name}\033[0m"
        desc_plain = f"{indent}|> {name}"
        rows = len(after)
        cols = len(after[0].keys()) if after and isinstance(after[0], dict) else 0
        pad = max(0, 34 - len(desc_plain))
        shape = f"\033[2mList\033[0m  \033[1m{rows}\033[0m rows × \033[1m{cols}\033[0m cols" if cols > 0 else f"\033[2mList\033[0m  \033[1m{rows}\033[0m items"
        line = f"{desc}{' ' * pad}\033[2m→\033[0m {shape}"
        if before is not None:
            dropped = len(before) - rows
            before_cols = set(before[0].keys()) if before and isinstance(before[0], dict) else set()
            after_cols = set(after[0].keys()) if after and isinstance(after[0], dict) else set()
            added_cols = after_cols - before_cols
            if dropped > 0:
                line += f"  \033[31m({dropped} dropped)\033[0m"
            if added_cols:
                line += f"  \033[32m(+{', '.join(added_cols)})\033[0m"
        if isinstance(call_node, Call) and "concurrent" in call_node.kwargs:
            try:
                n = self.eval(call_node.kwargs["concurrent"], {})
                line += f"  \033[2m[{n} concurrent]\033[0m"
            except Exception:
                pass
        if cached:
            line += f"  \033[2m[cached]\033[0m"
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

    def eval_call(self, node: Call, pipe_value: Any, env: Env, tail: bool = False, depth: int = 0) -> Any:
        # Resolve the callable
        if isinstance(node.func, FieldAccess):
            ns = self.eval(node.func.obj, env)
            if isinstance(ns, dict) and node.func.field in ns:
                fn = ns[node.func.field]
            else:
                raise PepError(f"'{self._call_name(node.func.obj)}' has no function '{node.func.field}'", loc=node.func.loc, span=len(node.func.field))
        elif isinstance(node.func, Ident):
            fn = env.get(node.func.name, loc=node.func.loc)
        else:
            fn = self.eval(node.func, env)

        # Unwrap Ok wrapper so curried lambdas (f(x)(y)) work naturally
        if isinstance(fn, Ok):
            fn = fn.value

        # Inject pipe value as first positional arg (always evaluated)
        if pipe_value is not None:
            pre = [pipe_value]
        else:
            pre = []

        # Call
        if isinstance(fn, PmFunction):
            # PmFunctions get fully evaluated args, unwrapped from Ok
            def _unwrap(v):
                return v.value if isinstance(v, Ok) else v
            args = pre + [_unwrap(self.eval(a, env)) for a in node.args]
            kwargs = {k: _unwrap(self.eval(v, env)) for k, v in node.kwargs.items()}
            if tail:
                return _TailCall(fn=fn, args=args, env=env)
            return self._call_pm_function(fn, args, kwargs, node.block, env, call_loc=node.loc)
        elif callable(fn):
            # Only defer AST nodes for functions that explicitly handle them via make_row_fn.
            # All other stdlib functions get fully-evaluated args.
            defers = getattr(fn, '_accepts_deferred', False)
            if defers:
                args = pre + [self._eval_or_defer(a, env) for a in node.args]
                kwargs = {k: self._eval_or_defer(v, env) for k, v in node.kwargs.items()}
            else:
                def _unwrap_ok(v):
                    return v.value if isinstance(v, Ok) else v
                args = pre + [_unwrap_ok(self.eval(a, env)) for a in node.args]
                kwargs = {k: _unwrap_ok(self.eval(v, env)) for k, v in node.kwargs.items()}
            _VOLATILE = {"embed", "llm"}
            fn_name = self._call_name(node.func).split(".")[-1]
            extra = {}
            if _check_accepts_interp(fn):
                extra = {"_block": node.block, "_env": env, "_interp": self, "_depth": depth}
            if self._cache and fn_name in _VOLATILE:
                extra["_row_cache"] = self._cache
            result = fn(*args, **kwargs, **extra) if extra else fn(*args, **kwargs)
            # Unwrap nested Ok(Ok(...))
            while isinstance(result, Ok) and isinstance(result.value, Ok):
                result = result.value
            if not isinstance(result, (Ok, Err)):
                result = Ok(result)
            return result
        else:
            raise PepError(f"'{self._call_name(node.func)}' is not callable (got {type(fn).__name__})", loc=node.loc)

    def _call_pm_function(self, fn: PmFunction, args: list, kwargs: dict, block, env: Env, call_loc=None) -> Any:
        # Trampoline: loop on tail calls to avoid growing the Python call stack
        while True:
            if len(args) != len(fn.params):
                raise PepError(f"expected {len(fn.params)} args, got {len(args)}", loc=call_loc)
            bindings = dict(zip(fn.params, args))
            call_env = fn.closure.extend(bindings)
            result = self.eval_tail(fn.body, call_env)
            if isinstance(result, _TailCall):
                fn, args = result.fn, result.args
                continue
            if not isinstance(result, (Ok, Err)):
                result = Ok(result)
            return result

    def eval_tail(self, node, env: Env) -> Any:
        """Like eval, but returns _TailCall instead of recursing for tail-position PmFunction calls."""
        match node:
            case Call():
                return self.eval_call(node, None, env, tail=True)
            case Match():
                return self.eval_match_tail(node, env)
            case Block():
                return self.eval_block_tail(node, env)
            case _:
                return self.eval(node, env)

    def eval_match_tail(self, node: Match, env: Env) -> Any:
        subject = self.eval(node.subject, env)
        has_result_pattern = any(isinstance(arm.pattern, (PatOk, PatErr)) for arm in node.arms)
        if not has_result_pattern and isinstance(subject, Ok):
            subject = subject.value
        for arm in node.arms:
            matched, bindings = self._match_pattern(arm.pattern, subject, env)
            if matched:
                arm_env = env.extend(bindings)
                return self.eval_tail(arm.body, arm_env)
        return Err("no match")

    def eval_block_tail(self, node: Block, env: Env) -> Any:
        block_env = Env(parent=env)
        result = None
        for i, stmt in enumerate(node.stmts):
            if i == len(node.stmts) - 1:
                result = self.eval_tail(stmt, block_env)
            else:
                result = self.eval(stmt, block_env)
        return result

    # --- Match ---

    def eval_match(self, node: Match, env: Env) -> Any:
        subject = self.eval(node.subject, env)
        has_result_pattern = any(isinstance(arm.pattern, (PatOk, PatErr)) for arm in node.arms)
        if not has_result_pattern and isinstance(subject, Ok):
            subject = subject.value

        for arm in node.arms:
            matched, bindings = self._match_pattern(arm.pattern, subject, env)
            if matched:
                arm_env = env.extend(bindings)
                return self.eval(arm.body, arm_env)

        return Err("no match")

    def _match_pattern(self, pattern, value, env: Env) -> tuple[bool, dict]:
        match pattern:
            case PatWildcard():
                return True, {}

            case PatComparison(op=op, value=v):
                # v may be a literal or an Ident (variable pattern)
                rhs = self.eval(v, env) if isinstance(v, Ident) else v
                match op:
                    case ">":  result = value > rhs
                    case "<":  result = value < rhs
                    case ">=": result = value >= rhs
                    case "<=": result = value <= rhs
                    case "==": result = value == rhs
                    case "!=": result = value != rhs
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
                    ok, bindings = self._match_pattern(pat, val, env)
                    if not ok:
                        return False, {}
                    all_bindings.update(bindings)
                return True, all_bindings

            case _:
                return False, {}

    # --- Arg evaluation ---

    def _uses_it(self, node) -> bool:
        """Return True if the AST node references `it` anywhere."""
        if isinstance(node, Ident):
            return node.name == "it"
        if isinstance(node, Lambda):
            return False  # `it` inside a lambda is scoped there, not injected by caller
        for attr in getattr(node, '__dataclass_fields__', {}):
            child = getattr(node, attr)
            if isinstance(child, list):
                if any(self._uses_it(c) for c in child if hasattr(c, '__dataclass_fields__') or isinstance(c, Ident)):
                    return True
            elif hasattr(child, '__dataclass_fields__') or isinstance(child, Ident):
                if self._uses_it(child):
                    return True
        return False

    def _eval_or_defer(self, node, env):
        """Evaluate the node now if it doesn't reference `it`; otherwise leave as AST."""
        if self._uses_it(node):
            return node
        return self.eval(node, env)

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
