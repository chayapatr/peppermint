import sys
import argparse
sys.setrecursionlimit(50000)
from .parser import parse
from .interpreter import Interpreter, Err, Ok
from .stdlib import build_global_env


def run_file(args):
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
