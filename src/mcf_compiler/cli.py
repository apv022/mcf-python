"""Command-line interface for validation and compilation."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__
from .compiler import compile_course, compile_single_file
from .model import ValidationError
from .parser import parse_course


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcf", description="Compile MCF 1.0 courses into static offline readers"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate an MCF course package")
    validate.add_argument("course", help="MCF course directory")
    compile_parser = commands.add_parser("compile", help="compile a static course reader")
    compile_parser.add_argument("course", help="MCF course directory")
    outputs = compile_parser.add_mutually_exclusive_group()
    outputs.add_argument("-o", "--output", help="course library output (default: courses)")
    outputs.add_argument("--single-file", help="standalone HTML output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "validate":
            course = parse_course(arguments.course)
            print(f"Valid MCF 1.0 course: {course.title} ({course.id})")
        else:
            if arguments.single_file:
                result = compile_single_file(arguments.course, arguments.single_file)
                print(f"Compiled {result.course.title} to {result.file}")
            else:
                result = compile_course(arguments.course, arguments.output or "courses")
                print(f"Compiled {result.course.title} to {result.directory}")
    except ValidationError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
