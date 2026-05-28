from __future__ import annotations
from .ast_nodes import *


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------

import re

_TOKEN_RE = re.compile(r"""
    (?P<FLOAT>    -?(?:\d+\.(?!\.)|\.\d+)\d*(?:[eE][+-]?\d+)?   )  |
    (?P<SPREAD>   \.\.\.                                  )  |
    (?P<DOTDOT>   \.\.                                    )  |
    (?P<INT>      \d+                                     )  |
    (?P<STRING>   "(?:[^"\\]|\\.)*"                       )  |
    (?P<ARROW>    ->                                      )  |
    (?P<PIPE>     \|>                                     )  |
    (?P<GTE>      >=                                      )  |
    (?P<LTE>      <=                                      )  |
    (?P<EQ>       ==                                      )  |
    (?P<NEQ>      !=                                      )  |
    (?P<GT>       >                                       )  |
    (?P<LT>       <                                       )  |
    (?P<DOT>      \.                                      )  |
    (?P<PLUS>     \+                                      )  |
    (?P<MINUS>    -                                       )  |
    (?P<STAR>     \*                                      )  |
    (?P<SLASH>    /                                       )  |
    (?P<MOD>      %                                       )  |
    (?P<LPAREN>   \(                                      )  |
    (?P<RPAREN>   \)                                      )  |
    (?P<LBRACKET> \[                                      )  |
    (?P<RBRACKET> \]                                      )  |
    (?P<LBRACE>   \{                                      )  |
    (?P<RBRACE>   \}                                      )  |
    (?P<COMMA>    ,                                       )  |
    (?P<COLON>    :                                       )  |
    (?P<EQUALS>   =                                       )  |
    (?P<NL>       [\n;]+                                  )  |
    (?P<NAME>     [a-zA-Z_][a-zA-Z0-9_]*                  )  |
    (?P<WS>       [ \t]+                                  )  |
    (?P<COMMENT>  \#[^\n]*                                )
""", re.VERBOSE)

_KEYWORDS = {"true", "false", "none", "ns", "use", "as", "quiet", "match", "and", "or", "not"}


class Token:
    __slots__ = ("type", "value", "line", "col")

    def __init__(self, type_: str, value: str, line: int, col: int):
        self.type = type_
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, {self.line}:{self.col})"


def tokenize(src: str) -> list[Token]:
    tokens: list[Token] = []
    line = 1
    line_start = 0
    for m in _TOKEN_RE.finditer(src):
        kind = m.lastgroup
        value = m.group()
        col = m.start() - line_start + 1
        if kind in ("WS", "COMMENT"):
            if "\n" in value:
                count = value.count("\n")
                line += count
                line_start = m.start() + value.rfind("\n") + 1
            continue
        if kind == "NL":
            count = value.count("\n")
            nl_line = line
            tokens.append(Token("NL", value, nl_line, col))
            if count:
                line += count
                line_start = m.start() + value.rfind("\n") + 1
            continue
        if kind == "NAME" and value in _KEYWORDS:
            tokens.append(Token(value.upper(), value, line, col))
        else:
            tokens.append(Token(kind, value, line, col))
    tokens.append(Token("EOF", "", line, len(src) - line_start + 1))
    return tokens


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class ParseError(Exception):
    def __init__(self, msg: str, line: int = 0, col: int = 0):
        super().__init__(f"Parse error at {line}:{col}: {msg}")
        self.line = line
        self.col = col


class Parser:
    def __init__(self, tokens: list[Token]):
        self._tokens = tokens
        self._pos = 0

    # --- Token stream helpers ---

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _cur(self) -> Token:
        return self._tokens[self._pos]

    def _peek2(self) -> Token:
        i = self._pos + 1
        while i < len(self._tokens) and self._tokens[i].type == "NL":
            i += 1
        return self._tokens[i]

    def _at(self, *types: str) -> bool:
        return self._peek().type in types

    def _at_after_nl(self, *types: str) -> bool:
        """Check if the next non-NL token is one of types."""
        i = self._pos
        while i < len(self._tokens) and self._tokens[i].type == "NL":
            i += 1
        return self._tokens[i].type in types

    def _eat(self, *types: str) -> Token:
        tok = self._peek()
        if tok.type not in types:
            raise ParseError(
                f"expected {' or '.join(types)}, got {tok.type} ({tok.value!r})",
                tok.line, tok.col,
            )
        self._pos += 1
        return tok

    def _skip_nl(self):
        while self._at("NL"):
            self._pos += 1

    def _loc(self, tok: Token) -> Loc:
        return Loc(tok.line, tok.col)

    # --- Top level ---

    def parse_program(self) -> Program:
        stmts = []
        self._skip_nl()
        while not self._at("EOF"):
            stmt = self._parse_statement()
            if stmt is not None:
                # cont_pipe: a statement starting with |> merges onto previous
                if isinstance(stmt, _ContPipe):
                    if stmts:
                        prev = stmts[-1]
                        if isinstance(prev, Pipe):
                            prev.steps.extend(stmt.steps)
                        elif isinstance(prev, Assign):
                            if isinstance(prev.value, Pipe):
                                prev.value.steps.extend(stmt.steps)
                            else:
                                prev.value = Pipe(steps=[prev.value] + stmt.steps)
                        else:
                            stmts[-1] = Pipe(steps=[prev] + stmt.steps)
                else:
                    stmts.append(stmt)
            self._skip_nl()
        return Program(body=stmts)

    def _parse_statement(self):
        # Continuation pipe: |> at statement level
        if self._at("PIPE"):
            steps = []
            while self._at("PIPE"):
                self._eat("PIPE")
                steps.append(self._parse_pipe_step())
                self._skip_nl()  # allow newlines between cont-pipe steps? No -- eat only if next is also |>
            return _ContPipe(steps=steps)

        tok = self._peek()

        if tok.type == "USE":
            return self._parse_use()
        if tok.type == "NS":
            return self._parse_ns()

        # assign: NAME = expr  (only if followed by EQUALS, not ARROW)
        if tok.type == "NAME" and self._peek2().type == "EQUALS":
            return self._parse_assign()

        return self._parse_expr()

    # --- Statements ---

    def _parse_use(self) -> UseDecl:
        tok = self._eat("USE")
        loc = self._loc(tok)
        path_tok = self._eat("NAME", "STRING")
        path = path_tok.value.strip('"')
        alias = None
        if self._at("AS"):
            self._eat("AS")
            alias = self._eat("NAME").value
        return UseDecl(path=path, alias=alias, loc=loc)

    def _parse_ns(self) -> NsDecl:
        tok = self._eat("NS")
        loc = self._loc(tok)
        name = self._eat("NAME").value
        self._eat("LBRACE")
        self._skip_nl()
        body = []
        while not self._at("RBRACE", "EOF"):
            if self._at("NL"):
                self._skip_nl()
                continue
            name_tok = self._peek()
            if name_tok.type == "NAME" and self._peek2().type == "EQUALS":
                body.append(self._parse_assign())
            else:
                raise ParseError("expected assignment inside ns", name_tok.line, name_tok.col)
            self._skip_nl()
        self._eat("RBRACE")
        return NsDecl(name=name, body=body, loc=loc)

    def _parse_assign(self) -> Assign:
        name_tok = self._eat("NAME")
        self._eat("EQUALS")
        value = self._parse_expr()
        return Assign(name=name_tok.value, value=value, loc=self._loc(name_tok))

    # --- Expressions (precedence climbing) ---

    def _parse_expr(self):
        return self._parse_lambda()

    def _parse_lambda(self):
        # () -> expr  or  () -> (body)
        if self._at("LPAREN"):
            saved = self._pos
            try:
                result = self._try_parse_lambda_paren()
                if result is not None:
                    return result
            except ParseError:
                pass
            self._pos = saved

        # NAME -> expr  or  NAME -> (body)
        if self._at("NAME") and self._peek2().type == "ARROW":
            name_tok = self._eat("NAME")
            self._eat("ARROW")
            body = self._parse_lambda_body()
            return Lambda(params=[name_tok.value], body=body, loc=self._loc(name_tok))

        return self._parse_pipe()

    def _try_parse_lambda_paren(self):
        """Try to parse `(params) -> body` or `() -> body`. Raises ParseError if not a lambda."""
        tok = self._eat("LPAREN")
        loc = self._loc(tok)
        self._skip_nl()

        if self._at("RPAREN"):
            # () -> ...
            self._eat("RPAREN")
            if not self._at("ARROW"):
                raise ParseError(self._cur().line, self._cur().col, "not a lambda")
            self._eat("ARROW")
            body = self._parse_lambda_body()
            return Lambda(params=[], body=body, loc=loc)

        # Try to collect NAME, NAME, ... then RPAREN ARROW
        if not self._at("NAME"):
            raise ParseError(self._cur().line, self._cur().col, "not a lambda")
        params = [self._eat("NAME").value]
        self._skip_nl()
        while self._at("COMMA"):
            self._eat("COMMA")
            self._skip_nl()
            params.append(self._eat("NAME").value)
            self._skip_nl()
        self._eat("RPAREN")
        if not self._at("ARROW"):
            raise ParseError(self._cur().line, self._cur().col, "not a lambda")
        self._eat("ARROW")
        body = self._parse_lambda_body()
        return Lambda(params=params, body=body, loc=loc)

    def _parse_lambda_body(self):
        self._skip_nl()
        node = self._parse_expr()
        # allow |> continuation across newlines in a lambda body
        while self._at("NL") and self._at_after_nl("PIPE"):
            self._skip_nl()
            while self._at("PIPE"):
                self._eat("PIPE")
                step = self._parse_pipe_step()
                if isinstance(node, Pipe):
                    node.steps.append(step)
                else:
                    node = Pipe(steps=[node, step])
        return node

    def _parse_paren_item(self):
        """An item inside paren_body: assignment or full expr, optionally followed by |> steps."""
        if self._at("NAME") and self._peek2().type == "EQUALS":
            node = self._parse_assign()
        else:
            node = self._parse_expr()
        # Allow inline pipe continuations after the expr (when not already consumed by pipe_or_cmp)
        while self._at("PIPE"):
            self._eat("PIPE")
            step = self._parse_pipe_step()
            if isinstance(node, Pipe):
                node.steps.append(step)
            else:
                node = Pipe(steps=[node, step])
        return node

    def _parse_pipe(self):
        node = self._parse_pipe_or_cmp()
        return node

    def _parse_pipe_or_cmp(self):
        node = self._parse_logic()
        while self._at("PIPE"):
            self._eat("PIPE")
            step = self._parse_pipe_step()
            if isinstance(node, Pipe):
                node.steps.append(step)
            else:
                node = Pipe(steps=[node, step])
        return node

    def _parse_pipe_step(self) -> PipeStep:
        expr = self._parse_postfix()
        quiet = False
        if self._at("QUIET"):
            self._eat("QUIET")
            quiet = True
        return PipeStep(expr=expr, quiet=quiet)

    def _parse_logic(self):
        node = self._parse_cmp()
        while self._at("AND", "OR"):
            op_tok = self._eat("AND", "OR")
            self._skip_nl()
            right = self._parse_cmp()
            node = BinOp(op=op_tok.value, left=node, right=right)
        return node

    _CMP_OPS = {"GT", "LT", "GTE", "LTE", "EQ", "NEQ"}
    _CMP_STR = {"GT": ">", "LT": "<", "GTE": ">=", "LTE": "<=", "EQ": "==", "NEQ": "!="}

    def _parse_cmp(self):
        node = self._parse_add()
        if self._at("DOTDOT"):
            self._eat("DOTDOT")
            end = self._parse_add()
            return Range(start=node, end=end, loc=node.loc if hasattr(node, 'loc') else NO_LOC)
        while self._at(*self._CMP_OPS):
            op_tok = self._eat(*self._CMP_OPS)
            right = self._parse_add()
            node = BinOp(op=self._CMP_STR[op_tok.type], left=node, right=right)
        return node

    def _parse_add(self):
        node = self._parse_mul()
        while self._at("PLUS", "MINUS"):
            op_tok = self._eat("PLUS", "MINUS")
            self._skip_nl()
            right = self._parse_mul()
            node = BinOp(op=op_tok.value, left=node, right=right)
        return node

    def _parse_mul(self):
        node = self._parse_unary()
        while self._at("STAR", "SLASH", "MOD"):
            op_tok = self._eat("STAR", "SLASH", "MOD")
            self._skip_nl()
            right = self._parse_unary()
            node = BinOp(op=op_tok.value, left=node, right=right)
        return node

    def _parse_unary(self):
        if self._at("MINUS"):
            tok = self._eat("MINUS")
            operand = self._parse_postfix()
            return Neg(operand=operand, loc=self._loc(tok))
        if self._at("NOT"):
            tok = self._eat("NOT")
            operand = self._parse_unary()
            return BinOp(op="not", left=operand, right=None, loc=self._loc(tok))
        return self._parse_postfix()

    def _parse_postfix(self):
        node = self._parse_atom()
        while True:
            if self._at("DOT"):
                self._eat("DOT")
                field_tok = self._eat("NAME")
                node = FieldAccess(obj=node, field=field_tok.value, loc=self._loc(field_tok))
            elif self._at("LPAREN"):
                lparen = self._eat("LPAREN")
                self._skip_nl()
                args, kwargs, inline_block = [], {}, None
                if not self._at("RPAREN"):
                    args, kwargs, inline_block = self._parse_arglist()
                self._eat("RPAREN")
                block = inline_block
                if self._at("LBRACE"):
                    block = self._parse_block()
                node = Call(func=node, args=args, kwargs=kwargs, block=block, loc=self._loc(lparen))
            elif self._at("LBRACKET"):
                lbracket = self._eat("LBRACKET")
                index = self._parse_cmp()  # may return Range if .. present
                self._eat("RBRACKET")
                if isinstance(index, Range):
                    node = Call(func=Ident(name="slice", loc=self._loc(lbracket)), args=[node, index.start, index.end], kwargs={}, block=None, loc=self._loc(lbracket))
                else:
                    node = Call(func=Ident(name="get", loc=self._loc(lbracket)), args=[node, index], kwargs={}, block=None, loc=self._loc(lbracket))
            else:
                break
        return node

    def _parse_arglist(self):
        args, kwargs = [], {}
        inline_block = None
        self._skip_nl()
        while not self._at("RPAREN", "EOF"):
            # inline block: |> step |> step ... inside call args
            if self._at("PIPE"):
                steps = []
                while self._at("PIPE"):
                    self._eat("PIPE")
                    steps.append(self._parse_pipe_step())
                    self._skip_nl()
                inline_block = steps
                break
            # kwarg: NAME COLON expr
            elif self._at("NAME") and self._peek2().type == "COLON":
                key_tok = self._eat("NAME")
                self._eat("COLON")
                self._skip_nl()
                val = self._parse_expr()
                kwargs[key_tok.value] = val
            else:
                args.append(self._parse_expr())
            self._skip_nl()
            if self._at("COMMA"):
                self._eat("COMMA")
                self._skip_nl()
            else:
                break
        return args, kwargs, inline_block

    def _parse_block(self) -> list:
        """{ |> step ... } sub-pipe block for group."""
        self._eat("LBRACE")
        self._skip_nl()
        steps = []
        while not self._at("RBRACE", "EOF"):
            self._eat("PIPE")
            steps.append(self._parse_pipe_step())
            self._skip_nl()
        self._eat("RBRACE")
        return steps

    def _parse_atom(self):
        tok = self._peek()

        if tok.type == "INT":
            self._eat("INT")
            return IntLit(value=int(tok.value), loc=self._loc(tok))

        if tok.type == "FLOAT":
            self._eat("FLOAT")
            return FloatLit(value=float(tok.value), loc=self._loc(tok))

        if tok.type == "STRING":
            self._eat("STRING")
            raw = tok.value[1:-1]
            value = raw.encode("raw_unicode_escape").decode("unicode_escape")
            return StrLit(value=value, loc=self._loc(tok))

        if tok.type == "TRUE":
            self._eat("TRUE")
            return BoolLit(value=True, loc=self._loc(tok))

        if tok.type == "FALSE":
            self._eat("FALSE")
            return BoolLit(value=False, loc=self._loc(tok))

        if tok.type == "NONE":
            self._eat("NONE")
            return NoneLit(loc=self._loc(tok))

        if tok.type == "MATCH":
            return self._parse_match()

        if tok.type == "SPREAD":
            self._eat("SPREAD")
            obj = self._parse_postfix()
            return Spread(obj=obj, loc=self._loc(tok))

        if tok.type == "LBRACKET":
            return self._parse_list()

        if tok.type == "LBRACE":
            return self._parse_obj()

        if tok.type == "LPAREN":
            return self._parse_paren_expr()

        if tok.type == "NAME":
            self._eat("NAME")
            return Ident(name=tok.value, loc=self._loc(tok))

        raise ParseError(f"unexpected token {tok.type} ({tok.value!r})", tok.line, tok.col)

    def _parse_paren_expr(self):
        """( expr ) or ( stmt; stmt; ... ) block."""
        tok = self._eat("LPAREN")
        self._skip_nl()

        if self._at("RPAREN"):
            raise ParseError("empty parentheses in expression context", tok.line, tok.col)

        stmts = []
        while not self._at("RPAREN", "EOF"):
            if self._at("PIPE") and stmts:
                prev = stmts[-1]
                while self._at("PIPE"):
                    self._eat("PIPE")
                    step = self._parse_pipe_step()
                    if isinstance(prev, Pipe):
                        prev.steps.append(step)
                    else:
                        prev = Pipe(steps=[prev, step])
                stmts[-1] = prev
            else:
                stmts.append(self._parse_paren_item())
            if self._at("NL"):
                self._skip_nl()
            else:
                break
        self._eat("RPAREN")
        if len(stmts) == 1:
            return stmts[0]
        return Block(stmts=stmts)

    def _parse_list(self) -> ListLit:
        tok = self._eat("LBRACKET")
        self._skip_nl()
        items = []
        while not self._at("RBRACKET", "EOF"):
            items.append(self._parse_expr())
            self._skip_nl()
            if self._at("COMMA"):
                self._eat("COMMA")
                self._skip_nl()
            else:
                break
        self._eat("RBRACKET")
        return ListLit(items=items, loc=self._loc(tok))

    def _parse_obj(self) -> ObjLit:
        tok = self._eat("LBRACE")
        self._skip_nl()
        entries = []
        while not self._at("RBRACE", "EOF"):
            if self._at("SPREAD"):
                spread_tok = self._eat("SPREAD")
                obj = self._parse_postfix()
                entries.append(ObjSpread(obj=obj, loc=self._loc(spread_tok)))
            elif self._at("NAME"):
                name_tok = self._eat("NAME")
                if self._at("COLON"):
                    self._eat("COLON")
                    self._skip_nl()
                    val = self._parse_expr()
                    entries.append(ObjField(key=name_tok.value, value=val, loc=self._loc(name_tok)))
                else:
                    entries.append(ObjShorthand(key=name_tok.value, loc=self._loc(name_tok)))
            else:
                break
            self._skip_nl()
            if self._at("COMMA"):
                self._eat("COMMA")
                self._skip_nl()
            else:
                break
        self._eat("RBRACE")
        return ObjLit(entries=entries, loc=self._loc(tok))

    def _parse_match(self) -> Match:
        tok = self._eat("MATCH")
        loc = self._loc(tok)
        self._eat("LPAREN")
        self._skip_nl()
        subject = self._parse_expr()
        self._skip_nl()
        self._eat("COMMA")
        self._skip_nl()
        arms = []
        while not self._at("RPAREN", "EOF"):
            arms.append(self._parse_match_arm())
            self._skip_nl()
            if self._at("COMMA"):
                self._eat("COMMA")
                self._skip_nl()
            else:
                break
        self._eat("RPAREN")
        return Match(subject=subject, arms=arms, loc=loc)

    _PAT_CMP = {"GT": ">", "LT": "<", "GTE": ">=", "LTE": "<=", "EQ": "==", "NEQ": "!="}

    def _parse_match_arm(self) -> MatchArm:
        tok = self._peek()
        if tok.type in self._PAT_CMP:
            self._eat(tok.type)
            pat_val = self._parse_pat_val()
            pattern = PatComparison(op=self._PAT_CMP[tok.type], value=pat_val)
        elif tok.type == "NAME" and tok.value == "_":
            self._eat("NAME")
            pattern = PatWildcard(loc=self._loc(tok))
        elif tok.type == "NAME" and tok.value == "Ok":
            self._eat("NAME")
            self._eat("LPAREN")
            name = self._eat("NAME").value
            self._eat("RPAREN")
            pattern = PatOk(name=name, loc=self._loc(tok))
        elif tok.type == "NAME" and tok.value == "Err":
            self._eat("NAME")
            self._eat("LPAREN")
            name = self._eat("NAME").value
            self._eat("RPAREN")
            pattern = PatErr(name=name, loc=self._loc(tok))
        elif tok.type in ("INT", "FLOAT", "STRING", "TRUE", "FALSE", "NONE"):
            pat_val = self._parse_pat_val()
            pattern = PatComparison(op="==", value=pat_val)
        else:
            raise ParseError(f"expected match pattern, got {tok.type}", tok.line, tok.col)
        self._eat("COLON")
        self._skip_nl()
        body = self._parse_expr()
        return MatchArm(pattern=pattern, body=body)

    def _parse_pat_val(self):
        tok = self._peek()
        if tok.type == "INT":
            self._eat("INT")
            return int(tok.value)
        if tok.type == "FLOAT":
            self._eat("FLOAT")
            return float(tok.value)
        if tok.type == "STRING":
            self._eat("STRING")
            return tok.value[1:-1].encode("raw_unicode_escape").decode("unicode_escape")
        if tok.type == "TRUE":
            self._eat("TRUE")
            return True
        if tok.type == "FALSE":
            self._eat("FALSE")
            return False
        if tok.type == "NONE":
            self._eat("NONE")
            return None
        if tok.type == "NAME":
            self._eat("NAME")
            return Ident(name=tok.value, loc=self._loc(tok))
        raise ParseError(f"expected pattern value, got {tok.type}", tok.line, tok.col)


class _ContPipe:
    def __init__(self, steps):
        self.steps = steps


def parse(src: str) -> Program:
    if not src.endswith("\n"):
        src += "\n"
    tokens = tokenize(src)
    return Parser(tokens).parse_program()


# Keep _normalize as a no-op shim so test imports don't break
def _normalize(src: str) -> str:
    return src
