import sys
import argparse
from .parser import parse
from .interpreter import Interpreter, Err
from .stdlib import build_global_env


def main():
    ap = argparse.ArgumentParser(prog="pep", description="Run a Peppermint pipeline file")
    ap.add_argument("command", choices=["run"], help="Command to run")
    ap.add_argument("file", help="Path to .pep file")
    ap.add_argument("--quiet", action="store_true", help="Suppress auto-print step summaries")
    args = ap.parse_args()

    try:
        src = open(args.file).read()
    except FileNotFoundError:
        print(f"pep: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    try:
        program = parse(src)
    except Exception as e:
        print(f"pep: parse error: {e}", file=sys.stderr)
        sys.exit(1)

    env = build_global_env()
    interp = Interpreter(env, quiet=args.quiet)

    try:
        result = interp.run(program)
    except Exception as e:
        print(f"pep: runtime error: {e}", file=sys.stderr)
        sys.exit(1)

    if isinstance(result, Err):
        print(f"pep: error: {result.msg}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
