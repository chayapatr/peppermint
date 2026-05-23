import sys
import argparse
sys.setrecursionlimit(50000)
from .parser import parse, ParseError
from .interpreter import Interpreter, Err, Ok, PepError
from .stdlib import build_global_env


def _render_error(kind: str, msg: str, src: str | None, line: int, col: int, span: int, filename: str):
    lines = src.splitlines() if src else []
    line_str = str(line)
    pad = len(line_str)

    # Source line format: " {line_str} │ {content}"
    # │ sits at column index pad+2 (0-based): 1 space + line_str + 1 space
    # All gutter lines put their box char at the same column index.
    g = " " * (pad + 2)  # spaces before │ / · / ╭ / ╰
    print(f"\033[1;31mError:\033[0m × {msg}", file=sys.stderr)
    print(f"{g}\033[2m╭─[\033[0m{filename}:{line}:{col}\033[2m]\033[0m", file=sys.stderr)

    # If line is past the file (e.g. unexpected EOF), show last line and point to end
    show_line = line if 0 < line <= len(lines) else len(lines)
    if show_line > 0 and lines:
        source_line = lines[show_line - 1]
        show_str = str(show_line)
        print(f" {show_str} \033[2m│\033[0m {source_line}", file=sys.stderr)

        col0 = (col - 1) if line <= len(lines) else len(source_line)
        col0 = max(0, min(col0, len(source_line)))
        left_pad = " " * col0
        span = max(span, 1)
        mid = span // 2

        if span == 1:
            print(f"{g}\033[2m·\033[0m {left_pad}\033[1;33m^\033[0m", file=sys.stderr)
            print(f"{g}\033[2m·\033[0m {left_pad}\033[2m╰──\033[0m {kind}", file=sys.stderr)
        else:
            bar = "─" * mid + "┬" + "─" * (span - mid - 1)
            print(f"{g}\033[2m·\033[0m {left_pad}\033[1;33m{bar}\033[0m", file=sys.stderr)
            print(f"{g}\033[2m·\033[0m {left_pad}{' ' * mid}\033[2m╰──\033[0m {kind}", file=sys.stderr)

    print(f"{g}\033[2m╰────\033[0m", file=sys.stderr)


def run_file(args):
    try:
        src = open(args.file).read()
    except FileNotFoundError:
        print(f"\033[1;31mError:\033[0m × file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    try:
        program = parse(src)
    except ParseError as e:
        _render_error("parse error", str(e.args[0]).split(": ", 1)[-1], src, e.line, e.col, 1, args.file)
        sys.exit(1)
    except Exception as e:
        print(f"\033[1;31mError:\033[0m × {e}", file=sys.stderr)
        sys.exit(1)

    env = build_global_env()
    interp = Interpreter(env, quiet=args.quiet)

    try:
        result = interp.run(program)
    except PepError as e:
        loc = e.loc
        if loc and loc.line:
            _render_error(str(e), str(e), src, loc.line, loc.col, e.span, args.file)
        else:
            print(f"\033[1;31mError:\033[0m × {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\033[1;31mError:\033[0m × {e}", file=sys.stderr)
        sys.exit(1)

    if isinstance(result, Err):
        cause = result.cause
        if cause and cause.loc and cause.loc.line:
            _render_error(str(cause), result.msg, src, cause.loc.line, cause.loc.col, cause.span, args.file)
        else:
            print(f"\033[1;31mError:\033[0m × {result.msg}", file=sys.stderr)
        sys.exit(1)


def run_repl(args):
    import readline  # enables arrow keys and history
    env = build_global_env()
    interp = Interpreter(env, quiet=False)

    print("Peppermint REPL  (Ctrl+D to exit)")

    buf = []

    while True:
        prompt = "... " if buf else ">>> "
        try:
            line = input(prompt)
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            buf = []
            continue

        # Continuation: lines ending with |> or inside open brackets
        stripped = line.rstrip()
        buf.append(line)

        # Try to parse what we have — if it fails, wait for more input
        src = "\n".join(buf)
        try:
            program = parse(src)
        except Exception:
            # Check if user left input empty (just pressed enter on empty buf)
            if stripped == "" and len(buf) == 1:
                buf = []
            continue

        buf = []

        try:
            result = interp.run(program)
        except Exception as e:
            print(f"error: {e}")
            continue

        if result is None:
            continue
        if isinstance(result, Err):
            print(f"<<< Err: {result.msg}")
        elif isinstance(result, Ok):
            if result.value is not None:
                print(f"<<< {result.value}")
        else:
            print(f"<<< {result}")


def main():
    ap = argparse.ArgumentParser(prog="pep", description="Peppermint language")
    sub = ap.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run a .pep file")
    run_p.add_argument("file", help="Path to .pep file")
    run_p.add_argument("--quiet", action="store_true", help="Suppress pipe step summaries")

    sub.add_parser("repl", help="Start interactive REPL")

    args = ap.parse_args()

    if args.command == "run":
        run_file(args)
    elif args.command == "repl":
        run_repl(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
