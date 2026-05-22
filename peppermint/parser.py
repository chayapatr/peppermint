from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from lark import Lark, Transformer, Token, Tree
from .ast_nodes import *


@dataclass
class _ContPipe:
    """Internal: a continuation pipe block starting with |>, merged in program()."""
    steps: list

_GRAMMAR = (Path(__file__).parent / "grammar.lark").read_text()
_parser = Lark(_GRAMMAR, parser="earley", start="program", propagate_positions=True, ambiguity="resolve")


def parse(src: str) -> Program:
    tree = _parser.parse(src if src.endswith("\n") else src + "\n")
    return PeppermintTransformer().transform(tree)


def _loc(tree) -> Loc:
    if hasattr(tree, "meta") and tree.meta.line is not None:
        return Loc(tree.meta.line, tree.meta.column)
    return NO_LOC


def _tok_loc(tok: Token) -> Loc:
    return Loc(tok.line or 0, tok.column or 0)


class PeppermintTransformer(Transformer):

    # --- Program ---

    def program(self, items):
        stmts = [i for i in items if i is not None]
        # Merge cont_pipe nodes onto the previous statement
        merged = []
        for node in stmts:
            if isinstance(node, _ContPipe):
                if merged:
                    prev = merged[-1]
                    if isinstance(prev, Pipe):
                        prev.steps.extend(node.steps)
                    elif isinstance(prev, Assign):
                        if isinstance(prev.value, Pipe):
                            prev.value.steps.extend(node.steps)
                        else:
                            prev.value = Pipe(steps=[prev.value] + node.steps)
                    else:
                        merged[-1] = Pipe(steps=[prev] + node.steps)
                # if no previous, discard (shouldn't happen in valid programs)
            else:
                merged.append(node)
        return Program(body=merged)

    def statement(self, items):
        return items[0]

    def cont_pipe(self, items):
        steps = [i for i in items if isinstance(i, PipeStep)]
        return _ContPipe(steps=steps)

    def paren_pipe(self, items):
        source = items[0]
        extra = [i for i in items[1:] if isinstance(i, PipeStep)]
        if not extra:
            return source
        if isinstance(source, Pipe):
            source.steps.extend(extra)
            return source
        return Pipe(steps=[source] + extra)

    def paren_seq(self, items):
        exprs = [i for i in items if not (isinstance(i, Token) and i.type in ("NL", "NEWLINE"))]
        if len(exprs) == 1:
            return exprs[0]
        return Block(stmts=exprs)

    def seq_expr(self, items):
        exprs = [i for i in items if not (isinstance(i, Token) and i.type in ("NL", "NEWLINE"))]
        return Block(stmts=exprs)

    # --- Statements ---

    def assign(self, items):
        name_tok = items[0]
        value = items[1]
        extra_steps = [i for i in items[2:] if isinstance(i, PipeStep)]
        if extra_steps:
            if isinstance(value, Pipe):
                value.steps.extend(extra_steps)
            else:
                value = Pipe(steps=[value] + extra_steps)
        return Assign(name=str(name_tok), value=value, loc=_tok_loc(name_tok))

    def use_decl(self, items):
        path_tok = items[0]
        raw = str(path_tok)
        path = raw.strip('"')
        alias = str(items[1]) if len(items) > 1 else None
        return UseDecl(path=path, alias=alias, loc=_tok_loc(path_tok))

    def ns_decl(self, items):
        name_tok = items[0]
        body = [i for i in items[1:] if isinstance(i, Assign)]
        return NsDecl(name=str(name_tok), body=body, loc=_tok_loc(name_tok))

    # --- Literals ---

    def int_lit(self, items):
        tok = items[0]
        return IntLit(value=int(tok), loc=_tok_loc(tok))

    def float_lit(self, items):
        tok = items[0]
        return FloatLit(value=float(tok), loc=_tok_loc(tok))

    def str_lit(self, items):
        tok = items[0]
        s = str(tok)
        # strip surrounding quotes and unescape
        value = s[1:-1].encode("raw_unicode_escape").decode("unicode_escape")
        return StrLit(value=value, loc=_tok_loc(tok))

    def true_lit(self, items):
        return BoolLit(value=True)

    def false_lit(self, items):
        return BoolLit(value=False)

    def none_lit(self, items):
        return NoneLit()

    def ident(self, items):
        tok = items[0]
        return Ident(name=str(tok), loc=_tok_loc(tok))

    # --- Collections ---

    def list_lit(self, items):
        return ListLit(items=list(items))

    def obj_lit(self, items):
        return ObjLit(entries=list(items))

    def obj_field(self, items):
        key_tok, value = items
        return ObjField(key=str(key_tok), value=value, loc=_tok_loc(key_tok))

    def obj_spread(self, items):
        return ObjSpread(obj=items[0])

    def tuple_lit(self, items):
        return TupleLit(items=list(items))

    def range_expr(self, items):
        start_tok, end_tok = items
        return Range(start=int(start_tok), end=int(end_tok), loc=_tok_loc(start_tok))

    def spread_expr(self, items):
        return Spread(obj=items[0])

    # --- Binary ops ---

    def binop(self, items):
        left, op_tok, right = items
        return BinOp(op=str(op_tok), left=left, right=right)

    # --- Field access ---

    def field_access(self, items):
        obj, name_tok = items
        return FieldAccess(obj=obj, field=str(name_tok))

    # --- Calls ---

    def call_expr(self, items):
        func = items[0]
        args, kwargs = self._split_args(items[1:])
        return Call(func=func, args=args, kwargs=kwargs, block=None)

    def call_with_block(self, items):
        func = items[0]
        block = None
        rest = items[1:]
        if rest and isinstance(rest[-1], list):
            block = rest[-1]
            rest = rest[:-1]
        args, kwargs = self._split_args(rest)
        return Call(func=func, args=args, kwargs=kwargs, block=block)

    def _split_args(self, items):
        args = []
        kwargs = {}
        for item in items:
            if isinstance(item, list):
                # arglist returns a flat list of posarg/kwarg results
                for sub in item:
                    if isinstance(sub, tuple):
                        kwargs[sub[0]] = sub[1]
                    elif sub is not None:
                        args.append(sub)
            elif isinstance(item, tuple):
                kwargs[item[0]] = item[1]
            elif item is not None:
                args.append(item)
        return args, kwargs

    def arglist(self, items):
        return [i for i in items if not isinstance(i, Token) or i.type not in ("NL", "NEWLINE", "_NEWLINE")]

    def posarg(self, items):
        return items[0]

    def kwarg(self, items):
        non_nl = [i for i in items if not (isinstance(i, Token) and i.type in ("NL", "NEWLINE"))]
        key_tok, value = non_nl[0], non_nl[1]
        return (str(key_tok), value)

    # --- Block (sub-pipe for group) ---

    def block(self, items):
        return [i for i in items if isinstance(i, PipeStep)]

    # --- Pipe ---

    def pipe_step(self, items):
        expr = items[0]
        quiet = any(isinstance(i, Token) and i.type == "QUIET" for i in items)
        return PipeStep(expr=expr, quiet=quiet)

    def pipe_expr(self, items):
        # items alternates: source, pipe_step, pipe_step, ...
        # but since pipe_expr is left-recursive via Lark, it comes as nested
        # Lark flattens left-recursive rules so items = [left_pipe_or_expr, pipe_step]
        if len(items) == 2 and isinstance(items[1], PipeStep):
            left, step = items
            if isinstance(left, Pipe):
                left.steps.append(step)
                return left
            else:
                return Pipe(steps=[left, step])
        # fallback: single expr (shouldn't happen with ?pipe_expr)
        return items[0]

    # --- Lambda ---

    def lambda_expr(self, items):
        body = items[-1]
        params = [str(t) for t in items[:-1] if isinstance(t, Token) and t.type not in ("NL", "NEWLINE", "ARROW")]
        return Lambda(params=params, body=body)

    def lambda_expr_noargs(self, items):
        return Lambda(params=[], body=items[0])

    def lambda_body(self, items):
        non_nl = [i for i in items if not (isinstance(i, Token) and i.type in ("NL", "NEWLINE", "ARROW"))]
        body = non_nl[-1]
        params = [str(t) for t in non_nl[:-1] if isinstance(t, Token)]
        return Lambda(params=params, body=body)

    def lambda_body_noargs(self, items):
        non_nl = [i for i in items if not (isinstance(i, Token) and i.type in ("NL", "NEWLINE"))]
        return Lambda(params=[], body=non_nl[0])

    # --- Match ---

    def match_expr(self, items):
        subject = items[0]
        arms = [i for i in items[1:] if isinstance(i, MatchArm)]
        return Match(subject=subject, arms=arms)

    def match_arm(self, items):
        pattern, body = items
        return MatchArm(pattern=pattern, body=body)

    def pat_gt(self, items):   return PatComparison(op=">",  value=self._lit(items[0]))
    def pat_lt(self, items):   return PatComparison(op="<",  value=self._lit(items[0]))
    def pat_gte(self, items):  return PatComparison(op=">=", value=self._lit(items[0]))
    def pat_lte(self, items):  return PatComparison(op="<=", value=self._lit(items[0]))
    def pat_eq(self, items):   return PatComparison(op="==", value=self._lit(items[0]))
    def pat_neq(self, items):  return PatComparison(op="!=", value=self._lit(items[0]))

    def pat_ok(self, items):
        return PatOk(name=str(items[0]))

    def pat_err(self, items):
        return PatErr(name=str(items[0]))

    def pat_tuple(self, items):
        return PatTuple(patterns=list(items))

    def pat_wildcard(self, items):
        return PatWildcard()

    def literal(self, items):
        return items[0]

    def _lit(self, node):
        if isinstance(node, (IntLit, FloatLit, StrLit)):
            return node.value
        if isinstance(node, Token):
            try:
                return int(node)
            except ValueError:
                try:
                    return float(node)
                except ValueError:
                    return str(node).strip('"')
        return node
