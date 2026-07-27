"""Version-dispatched public package API."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import yaml

from .model import Chapter, Course, Lesson, McfPackage, ValidationError, ValidationIssue
from .package_reader import open_package_source
from .parser import parse_course10
from .parser11 import parse_package11
from .schema import validate_schema
from .yaml_profile import diagnostic, parse_mcf_yaml


@dataclass(slots=True)
class ParseOptions:
    expected_version: str | None = None
    supported_extensions: list[str] = field(default_factory=list)
    allow_remote_resources: bool = False
    package_inputs: list[str | Path] = field(default_factory=list)


@dataclass(slots=True)
class ValidationResult:
    valid: bool
    diagnostics: list[ValidationIssue]
    version: str | None = None
    kind: str | None = None
    package: Course | McfPackage | None = None


def validate_package(
    input_path: str | Path, options: ParseOptions | None = None
) -> ValidationResult:
    settings = options or ParseOptions()
    issues: list[ValidationIssue] = []
    source = open_package_source(input_path, issues)
    if source is None:
        return ValidationResult(False, issues)
    try:
        raw = (source.root / "manifest.yaml").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        issues.append(
            diagnostic(
                "MCF_PACKAGE_ENTRY_MISSING", "manifest.yaml", "Package root has no manifest.yaml."
            )
        )
        source.close()
        return ValidationResult(False, issues)
    try:
        detected = yaml.safe_load(raw)
    except yaml.YAMLError as error:
        issues.append(diagnostic("MCF_YAML_INVALID", "manifest.yaml", str(error)))
        detected = {}
    detected_data = detected if isinstance(detected, dict) else {}
    declared = detected_data.get("mcf")
    manifest = parse_mcf_yaml(raw, "manifest.yaml", issues) if declared == "1.1" else detected_data
    data = manifest if isinstance(manifest, dict) else {}
    if declared not in {"1.0", "1.1"}:
        issues.append(
            diagnostic(
                "MCF_VERSION_UNSUPPORTED", "manifest.yaml", f'Unsupported MCF version "{declared}".'
            )
        )
    if settings.expected_version and settings.expected_version != declared:
        issues.append(
            diagnostic(
                "MCF_VERSION_UNSUPPORTED",
                "manifest.yaml",
                f"Expected MCF {settings.expected_version}, but the package declares {declared}.",
            )
        )
    if declared in {"1.0", "1.1"}:
        issues.extend(validate_schema(data, declared, "manifest.schema.json", "manifest.yaml"))
    parsed: Course | McfPackage | None = None
    if not any(item.code == "MCF_VERSION_UNSUPPORTED" for item in issues):
        if declared == "1.0":
            # ZIP is transport only. Safe extraction happens before exact
            # version dispatch, so the 1.0 parser remains authoritative.
            try:
                parsed = parse_course10(source.root)
                parsed.source_type = source.source_type
                parsed.diagnostics = issues
            except ValidationError as error:
                issues.extend(error.issues)
        else:
            parsed = parse_package11(
                source.root,
                cast(dict[str, Any], data),
                issues,
                source.source_type,
                set(settings.supported_extensions),
            )
    valid = not any(item.severity == "error" for item in issues)
    if not valid or parsed is None:
        source.close()
    elif source.temporary:
        parsed.metadata["_temporary_package_root"] = str(source.temporary)
    return ValidationResult(
        valid,
        issues,
        declared if isinstance(declared, str) else None,
        parsed.kind if parsed else ("course" if declared == "1.0" else data.get("kind")),
        parsed,
    )


def parse_package(
    input_path: str | Path, options: ParseOptions | None = None
) -> Course | McfPackage:
    result = validate_package(input_path, options)
    if not result.valid or result.package is None:
        raise ValidationError(result.diagnostics)
    return result.package


def parse_package_set(
    packages: list[str | Path], options: ParseOptions | None = None
) -> list[Course | McfPackage]:
    settings = options or ParseOptions()
    child_options = ParseOptions(
        expected_version=settings.expected_version,
        supported_extensions=settings.supported_extensions,
        allow_remote_resources=settings.allow_remote_resources,
    )
    parsed = [parse_package(path, child_options) for path in packages]
    issues: list[ValidationIssue] = []
    seen: set[tuple[str, str | None]] = set()
    for item in parsed:
        identity = (item.id, item.version)
        if identity in seen:
            issues.append(
                diagnostic(
                    "MCF_PACKAGE_ID_COLLISION",
                    "manifest.yaml",
                    f"Duplicate package identity {identity!r}.",
                )
            )
        seen.add(identity)
    packages_by_id = {item.id: item for item in parsed}
    banks = {
        item.id: item
        for item in parsed
        if isinstance(item, McfPackage) and item.kind == "question_bank"
    }
    for item in parsed:
        for relationship in item.relationships or []:
            if relationship.get("type") == "requires" and (
                (target := packages_by_id.get(str(relationship.get("package")))) is None
                or (
                    relationship.get("version") is not None
                    and relationship.get("version") != target.version
                )
                or (
                    relationship.get("language") is not None
                    and relationship.get("language") != target.language
                )
            ):
                issues.append(
                    diagnostic(
                        "MCF_RELATIONSHIP_UNRESOLVED",
                        "manifest.yaml",
                        f'Required package "{relationship.get("package")}" is absent.',
                    )
                )
        lessons = (
            [lesson for chapter in item.chapters for lesson in chapter.lessons]
            if item.kind == "course"
            else item.lessons
            if isinstance(item, McfPackage) and item.kind == "module"
            else [item.lesson]
            if isinstance(item, McfPackage) and item.kind == "lesson" and item.lesson
            else []
        )
        for lesson in lessons:
            for activity in lesson.activities:
                for reference in activity.question_references or []:
                    bank = banks.get(str(reference.get("bank")))
                    question = (
                        next(
                            (
                                candidate
                                for candidate in bank.questions
                                if candidate.id == reference.get("question")
                            ),
                            None,
                        )
                        if bank
                        else None
                    )
                    if question is None:
                        issues.append(
                            diagnostic(
                                "MCF_QUESTION_BANK_REFERENCE_UNRESOLVED",
                                lesson.source,
                                f"Question reference {reference!r} does not resolve.",
                            )
                        )
                    else:
                        question.source_reference = reference
                        activity.questions.append(question)
    if issues:
        raise ValidationError(issues)
    return parsed


def parse_course(input_path: str | Path, options: ParseOptions | None = None) -> Course:
    settings = options or ParseOptions()
    parsed = (
        parse_package_set([input_path, *settings.package_inputs], settings)[0]
        if settings.package_inputs
        else parse_package(input_path, settings)
    )
    if parsed.kind not in {"course", "module", "lesson"}:
        raise ValidationError(
            [
                diagnostic(
                    "MCF_PACKAGE_KIND_UNSUPPORTED",
                    "manifest.yaml",
                    f"Compilation requires a course, module, or lesson package; "
                    f"received {parsed.kind}.",
                )
            ]
        )
    if isinstance(parsed, Course):
        return parsed
    if parsed.kind == "course":
        chapters = parsed.chapters
    else:
        lessons = parsed.lessons if parsed.kind == "module" else [cast(Lesson, parsed.lesson)]
        chapters = [Chapter(id=parsed.id, title=parsed.title, source="", lessons=lessons)]
    return Course(
        id=parsed.id,
        title=parsed.title,
        language=parsed.language,
        root=parsed.root,
        chapters=chapters,
        mcf="1.1",
        description=parsed.description,
        authors=parsed.authors,
        license=parsed.license,
        version=parsed.version,
        cover=parsed.cover,
        relationships=parsed.relationships,
        assets=parsed.assets,
        rubrics=parsed.rubrics,
        extensions=parsed.extensions,
        diagnostics=parsed.diagnostics,
        source_type=cast(Any, parsed.source_type),
        # Compilation uses the historical Course adapter internally, but the
        # learner-facing package kind remains part of normalized semantics.
        metadata={
            **parsed.metadata,
            "_source_kind": parsed.kind,
            # The course-shaped compile adapter must not erase the authored
            # standalone entry identity from normalized output.
            **({"entry": parsed.entry} if parsed.kind == "lesson" else {}),
        },
    )


def capabilities(implementation_version: str = "0.0.0") -> dict[str, Any]:
    return {
        "mcf_capabilities": "1.1",
        "implementation": {"name": "mcf-compiler", "version": implementation_version},
        "mcf_versions": ["1.0", "1.1"],
        "conformance": [],
        "package_kinds": ["course", "module", "lesson", "question_bank", "asset_collection"],
        "question_types": [
            "multiple_choice",
            "multiple_select",
            "true_false",
            "numeric",
            "short_answer",
            "essay",
            "open_response",
            "matching",
            "ordering",
        ],
        "features": [
            "directory",
            "archive",
            "structured_diagnostics",
            "static_course_compilation",
            "standalone_html",
            "closed_package_sets",
        ],
        "extensions": [],
        "limits": {
            "archive_entries": 4096,
            "archive_entry_bytes": 64 * 1024 * 1024,
            "archive_total_bytes": 512 * 1024 * 1024,
            "archive_compression_ratio": 200,
            "completion_depth": 8,
        },
    }


def validate_capability_declaration(value: Any) -> list[ValidationIssue]:
    issues = validate_schema(value, "1.1", "capabilities.schema.json", "capabilities.yaml")
    data = value if isinstance(value, dict) else {}
    implementation = data.get("implementation")
    required_arrays = ("mcf_versions", "conformance", "package_kinds", "question_types")
    if (
        data.get("mcf_capabilities") != "1.1"
        or not isinstance(implementation, dict)
        or not isinstance(implementation.get("name"), str)
        or not implementation.get("name")
        or not isinstance(implementation.get("version"), str)
        or any(not isinstance(data.get(key), list) for key in required_arrays)
    ):
        issues.append(
            diagnostic(
                "MCF_SCHEMA_INVALID",
                "capabilities.yaml",
                "Capability declaration has invalid required fields.",
            )
        )
    conformance = data.get("conformance")
    versions = data.get("mcf_versions")
    if (
        isinstance(conformance, list)
        and conformance
        and (not isinstance(versions, list) or "1.0" not in versions or "1.1" not in versions)
    ):
        issues.append(
            diagnostic(
                "MCF_SCHEMA_INVALID",
                "capabilities.yaml",
                "Conformance claims require both MCF 1.0 and MCF 1.1.",
            )
        )
    return issues
