import sys
import argparse
import os
from pathlib import Path

sys.setrecursionlimit(50000)

# Load .env from cwd or project root
for _env_path in [Path.cwd() / ".env", Path(__file__).parent.parent / ".env"]:
    if _env_path.exists():
        for _line in _env_path.read_text().splitlines():
            if _line.strip() and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())
        break
from .parser import parse, ParseError
from .interpreter import Interpreter, Err, Ok, PepError
from .stdlib import build_global_env
from .diagnostics import report_parse_error, report_pep_error, report_err
from .interpreter import PmFunction, PmRange


def _repl_display(value):
    if value is None:
        return
    if isinstance(value, bool):
        val_str = "true" if value else "false"
        type_str = "bool"
    elif isinstance(value, int):
        val_str = str(value)
        type_str = "num"
    elif isinstance(value, float):
        val_str = str(value)
        type_str = "num"
    elif isinstance(value, str):
        val_str = repr(value)
        type_str = "str"
    elif isinstance(value, PmFunction):
        val_str = repr(value)
        type_str = "fn"
    elif isinstance(value, PmRange):
        val_str = f"{value.start}..{value.end}"
        type_str = "range"
    elif isinstance(value, dict):
        pairs = ", ".join(f"{k}: {v!r}" for k, v in value.items())
        val_str = "{ " + pairs + " }"
        type_str = "obj"
    elif isinstance(value, list):
        rows = len(value)
        cols = len(value[0].keys()) if value and isinstance(value[0], dict) else 0
        val_str = f"List  {rows} rows × {cols} cols" if cols else f"List  {rows} items"
        type_str = ""
    else:
        val_str = str(value)
        type_str = type(value).__name__

    pad = max(2, 34 - len(val_str))
    type_tag = f"\033[33m[{type_str}]\033[0m" if type_str else ""
    print(f"\033[2m{val_str}\033[0m{' ' * pad}{type_tag}")


def run_file(args):
    try:
        src = open(args.file).read()
    except FileNotFoundError:
        print(f"\033[1;31mError:\033[0m × file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    try:
        program = parse(src)
    except ParseError as e:
        report_parse_error(e, src, args.file)
        sys.exit(1)
    except Exception as e:
        print(f"\033[1;31mError:\033[0m × {e}", file=sys.stderr)
        sys.exit(1)

    env = build_global_env()
    interp = Interpreter(env, quiet=args.quiet)

    try:
        result = interp.run(program)
    except PepError as e:
        report_pep_error(e, src, args.file)
        sys.exit(1)
    except Exception as e:
        print(f"\033[1;31mError:\033[0m × {e}", file=sys.stderr)
        sys.exit(1)

    if isinstance(result, Err):
        report_err(result, src, args.file)
        sys.exit(1)


def run_repl(args):
    import readline  # enables arrow keys and history
    env = build_global_env()
    interp = Interpreter(env, quiet=False)

    print("Peppermint REPL  (Ctrl+D to exit)")

    buf = []

    while True:
        prompt = "\033[2m...\033[0m " if buf else "\033[32m>>>\033[0m "
        try:
            line = input(prompt)
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            buf = []
            continue

        stripped = line.rstrip()
        buf.append(line)

        # Try joining with newlines first, then with spaces (handles `1 +\n2` style)
        program = None
        for src in ("\n".join(buf), " ".join(buf)):
            try:
                program = parse(src)
                break
            except Exception:
                pass

        if program is None:
            if stripped == "" and len(buf) == 1:
                buf = []
            continue

        buf = []

        try:
            result = interp.run(program)
        except PepError as e:
            report_pep_error(e, src, "<repl>")  # src is still in scope from the loop above
            continue
        except Exception as e:
            print(f"\033[1;31mError:\033[0m × {e}", file=sys.stderr)
            continue

        if result is None:
            continue
        if isinstance(result, Err):
            report_err(result, src, "<repl>")
        elif isinstance(result, Ok):
            _repl_display(result.value)
        else:
            _repl_display(result)


def main():
    ap = argparse.ArgumentParser(prog="pep", description="Peppermint language")
    ap.add_argument("file", nargs="?", help="Path to .pep file (omit to start REPL)")
    ap.add_argument("--quiet", action="store_true", help="Suppress pipe step summaries")

    args = ap.parse_args()

    if args.file == "lsp":
        try:
            from .lsp.server import start
        except ImportError as e:
            print(f"LSP server not available: {e}\nInstall with: pip install peppermint-lang[lsp]", file=sys.stderr)
            sys.exit(1)
        start()
    elif args.file:
        run_file(args)
    else:
        run_repl(args)


if __name__ == "__main__":
    main()
