from __future__ import annotations
import sys
from .parser import ParseError
from .interpreter import Err, PepError


def render(
    msg: str,
    src: str,
    filename: str,
    line: int,
    col: int,
    span: int = 1,
    label: str | None = None,
    file=None,
):
    if file is None:
        file = sys.stderr

    label = label or msg
    lines = src.splitlines() if src else []
    line_str = str(line)
    pad = len(line_str)
    g = " " * (pad + 2)

    print(f"\033[1;31mError:\033[0m × {msg}", file=file)
    print(f"{g}\033[2m╭─[\033[0m{filename}:{line}:{col}\033[2m]\033[0m", file=file)

    show_line = line if 0 < line <= len(lines) else len(lines)
    if show_line > 0 and lines:
        source_line = lines[show_line - 1]
        show_str = str(show_line)
        print(f" {show_str} \033[2m│\033[0m {source_line}", file=file)

        col0 = (col - 1) if line <= len(lines) else len(source_line)
        col0 = max(0, min(col0, len(source_line)))
        left_pad = " " * col0
        span = max(span, 1)
        mid = span // 2

        if span == 1:
            print(f"{g}\033[2m·\033[0m {left_pad}\033[1;33m^\033[0m", file=file)
            print(f"{g}\033[2m·\033[0m {left_pad}\033[2m╰──\033[0m {label}", file=file)
        else:
            bar = "─" * mid + "┬" + "─" * (span - mid - 1)
            print(f"{g}\033[2m·\033[0m {left_pad}\033[1;33m{bar}\033[0m", file=file)
            print(f"{g}\033[2m·\033[0m {left_pad}{' ' * mid}\033[2m╰──\033[0m {label}", file=file)

    print(f"{g}\033[2m╰────\033[0m", file=file)


def report_parse_error(e: ParseError, src: str, filename: str, file=None):
    msg = str(e.args[0]).split(": ", 1)[-1]
    render(msg, src, filename, e.line, e.col, span=1, label="parse error", file=file)


def report_pep_error(e: PepError, src: str, filename: str, file=None):
    loc = e.loc
    if loc and loc.line:
        render(str(e), src, filename, loc.line, loc.col, span=e.span, file=file)
    else:
        print(f"\033[1;31mError:\033[0m × {e}", file=file or sys.stderr)


def report_err(result: Err, src: str, filename: str, file=None):
    cause = result.cause
    if cause and cause.loc and cause.loc.line:
        render(result.msg, src, filename, cause.loc.line, cause.loc.col, span=cause.span, file=file)
    else:
        print(f"\033[1;31mError:\033[0m × {result.msg}", file=file or sys.stderr)
