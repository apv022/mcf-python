"""Command-line interface for MCF 1.0 and 1.1."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

import yaml

from . import __version__
from .compiler import compile_course, compile_single_file
from .model import ValidationError, ValidationIssue
from .package import (
    ParseOptions,
    capabilities,
    parse_package,
    parse_package_set,
    validate_package,
)


def _common(parser: argparse.ArgumentParser, *, diagnostics: bool = True) -> None:
    parser.add_argument("--expected-version", choices=["1.0", "1.1"])
    parser.add_argument(
        "--package",
        action="append",
        default=[],
        metavar="PATH",
        help="dependency/package-set input (repeatable)",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="allow remote resource fetching (disabled by default)",
    )
    if diagnostics:
        parser.add_argument("--format", choices=["text", "json"], default="text")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcf", description="Validate, inspect, and compile MCF 1.0 and MCF 1.1 packages"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate an MCF package")
    validate.add_argument("input", help="package directory or .mcf.zip")
    _common(validate)
    inspect = commands.add_parser("inspect", help="inspect package structure and capabilities")
    inspect.add_argument("input", help="package directory or .mcf.zip")
    _common(inspect)
    capability = commands.add_parser("capabilities", help="print the capability declaration")
    capability.add_argument("--format", choices=["json", "yaml"], default="json")
    compile_parser = commands.add_parser(
        "compile", help="compile a static course, module, or lesson reader"
    )
    compile_parser.add_argument("input", help="course, module, or lesson directory or .mcf.zip")
    outputs = compile_parser.add_mutually_exclusive_group()
    outputs.add_argument("-o", "--output", help="course library output (default: courses)")
    outputs.add_argument("--single-file", help="standalone HTML output")
    _common(compile_parser)
    return parser


def _options(arguments: argparse.Namespace) -> ParseOptions:
    return ParseOptions(
        expected_version=arguments.expected_version,
        allow_remote_resources=arguments.allow_remote,
        package_inputs=arguments.package,
    )


def _diagnostic_data(item: ValidationIssue) -> dict[str, Any]:
    return {key: value for key, value in asdict(item).items() if value is not None}


def _print_diagnostics(items: list[ValidationIssue], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps({"diagnostics": [_diagnostic_data(item) for item in items]}, indent=2))
        return
    for item in items:
        print(
            f"{item.severity.upper()} {item.code} {item.file}: {item.message}",
            file=sys.stderr,
        )


def _exit_code(items: list[ValidationIssue]) -> int:
    codes = {item.code for item in items}
    if "MCF_VERSION_UNSUPPORTED" in codes:
        return 3
    if "MCF_EXTENSION_REQUIRED_UNSUPPORTED" in codes:
        return 4
    if "MCF_SECURITY_POLICY_REJECTED" in codes:
        return 5
    return 2


def _lessons(package: Any) -> list[Any]:
    if package.kind == "course":
        return [lesson for chapter in package.chapters for lesson in chapter.lessons]
    if package.kind == "module":
        return list(package.lessons)
    if package.kind == "lesson":
        return [package.lesson]
    return []


def _inspect_report(package: Any) -> dict[str, Any]:
    lessons = _lessons(package)
    required_extensions = [
        name
        for name, entry in (package.extensions or {}).items()
        if isinstance(entry, dict) and entry.get("required")
    ]
    entry_structure: Any
    if package.kind == "course":
        entry_structure = [
            {"id": chapter.id, "lessons": [lesson.id for lesson in chapter.lessons]}
            for chapter in package.chapters
        ]
    elif package.kind == "module":
        entry_structure = [lesson.id for lesson in package.lessons]
    elif package.kind in {"lesson", "question_bank"}:
        entry_structure = package.entry
    else:
        entry_structure = [asset.get("id") for asset in package.assets or []]
    return {
        "mcf": package.mcf,
        "kind": package.kind,
        "id": package.id,
        "package_version": package.version,
        "source_type": package.source_type,
        "entry_structure": entry_structure,
        "dependencies": [
            relationship
            for relationship in package.relationships or []
            if relationship.get("type") == "requires"
        ],
        "required_extensions": required_extensions,
        "detected_capabilities": {
            "activity_types": sorted(
                {activity.type for lesson in lessons for activity in lesson.activities}
            ),
            "question_types": sorted(
                {
                    question.type
                    for lesson in lessons
                    for activity in lesson.activities
                    for question in activity.questions
                }
            ),
        },
        "diagnostics": [_diagnostic_data(item) for item in package.diagnostics],
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.command == "capabilities":
        declaration = capabilities(__version__)
        print(
            json.dumps(declaration, indent=2)
            if arguments.format == "json"
            else yaml.safe_dump(declaration, sort_keys=False).rstrip()
        )
        return 0
    try:
        options = _options(arguments)
        if arguments.command == "validate":
            parsed: Any
            result: dict[str, Any]
            if arguments.package:
                parsed = parse_package_set([arguments.input, *arguments.package], options)[0]
                result = {
                    "valid": True,
                    "mcf": parsed.mcf,
                    "kind": parsed.kind,
                    "diagnostics": [_diagnostic_data(item) for item in parsed.diagnostics],
                }
            else:
                validation = validate_package(arguments.input, options)
                if not validation.valid:
                    _print_diagnostics(validation.diagnostics, arguments.format)
                    return _exit_code(validation.diagnostics)
                parsed = validation.package
                result = {
                    "valid": True,
                    "mcf": validation.version,
                    "kind": validation.kind,
                    "diagnostics": [_diagnostic_data(item) for item in validation.diagnostics],
                }
            if arguments.format == "json":
                print(json.dumps(result, indent=2))
            else:
                assert parsed is not None
                print(f"Valid MCF {parsed.mcf} {parsed.kind}: {parsed.title} ({parsed.id})")
        elif arguments.command == "inspect":
            parsed = (
                parse_package_set([arguments.input, *arguments.package], options)[0]
                if arguments.package
                else parse_package(arguments.input, options)
            )
            report = _inspect_report(parsed)
            if arguments.format == "json":
                print(json.dumps(report, indent=2))
            else:
                print(f"MCF version: {report['mcf']}")
                print(f"Package kind: {report['kind']}")
                print(f"Package: {report['id']}")
                print(f"Source: {report['source_type']}")
                print(f"Entry structure: {json.dumps(report['entry_structure'])}")
                print(f"Dependencies: {json.dumps(report['dependencies'])}")
                print(
                    "Required extensions: " + (", ".join(report["required_extensions"]) or "(none)")
                )
                print(f"Detected capabilities: {json.dumps(report['detected_capabilities'])}")
        elif arguments.single_file:
            single_result = compile_single_file(arguments.input, arguments.single_file, options)
            print(
                f"Compiled MCF {single_result.course.mcf} "
                f"{single_result.course.title} to {single_result.file}"
            )
        else:
            compile_result = compile_course(arguments.input, arguments.output or "courses", options)
            print(
                f"Compiled MCF {compile_result.course.mcf} {compile_result.course.title} "
                f"to {compile_result.directory}"
            )
    except ValidationError as error:
        _print_diagnostics(error.issues, getattr(arguments, "format", "text"))
        return _exit_code(error.issues)
    except (OSError, ValueError) as error:
        _print_diagnostics(
            [ValidationIssue(file="", message=str(error), code="MCF_OPERATIONAL_FAILURE")],
            getattr(arguments, "format", "text"),
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
