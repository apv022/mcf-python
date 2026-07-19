"""MCF package discovery, ordered loading, and semantic validation."""

from __future__ import annotations

import re
from pathlib import Path

from .lesson import identifier, parse_lesson_source
from .model import Chapter, Course, Lesson, ValidationError, ValidationIssue
from .paths import is_really_contained, portable_path, validate_reference
from .yamlio import add_issue, as_object, load_yaml_file, optional_text, string_list, text

REFERENCE_RE = re.compile(r"!?\[[^\]]*\]\(([^\s)]+)|@\[(?:audio|video)\]\(([^\s)]+)")


def _reference_fields(lesson: Lesson) -> list[str]:
    result: list[str] = []
    for activity in lesson.activities:
        result.append(activity.content)
        for question in activity.questions:
            result.extend([question.prompt, question.hint or "", question.explanation or ""])
            result.extend(option.text for option in question.options or [])
    return result


def parse_course(input_path: str | Path) -> Course:
    root = Path(input_path).expanduser().resolve()
    issues: list[ValidationIssue] = []
    if not root.is_dir():
        raise ValidationError(
            [ValidationIssue(file=str(input_path), message="Course directory does not exist.")]
        )
    manifest = load_yaml_file(root / "manifest.yaml", "manifest.yaml", issues)
    if manifest.get("mcf") != "1.0":
        add_issue(
            issues,
            "manifest.yaml",
            f'Unsupported MCF version "{manifest.get("mcf")}". '
            'This compiler currently supports "1.0".',
        )
    chapters_root = root / "chapters"
    if not chapters_root.is_dir():
        add_issue(issues, "manifest.yaml", "Required chapters/ directory does not exist.")

    chapters: list[Chapter] = []
    chapter_entries = manifest.get("chapters")
    if not isinstance(chapter_entries, list) or not chapter_entries:
        add_issue(issues, "manifest.yaml", 'Field "chapters" must be a non-empty ordered list.')
    else:
        for entry in chapter_entries:
            source = as_object(entry).get("source")
            if not isinstance(source, str):
                add_issue(issues, "manifest.yaml", "Each chapter entry must contain source.")
                continue
            chapter_dir = portable_path(root, root, source, "manifest.yaml", issues)
            if chapter_dir is None:
                continue
            try:
                chapter_dir.relative_to(chapters_root.resolve())
            except ValueError:
                add_issue(
                    issues, "manifest.yaml", f"Chapter source must be under chapters/: {source}"
                )
            if not chapter_dir.is_dir():
                add_issue(issues, "manifest.yaml", f"Chapter path does not exist: {source}")
                continue
            if not is_really_contained(root, chapter_dir):
                add_issue(
                    issues, "manifest.yaml", f"Chapter path escapes the course root: {source}"
                )
                continue

            display = f"{source}/chapter.yaml"
            chapter_data = load_yaml_file(chapter_dir / "chapter.yaml", display, issues)
            if not (chapter_dir / "lessons").is_dir():
                add_issue(issues, display, "Required lessons/ directory does not exist.")
            lessons: list[Lesson] = []
            lesson_entries = chapter_data.get("lessons")
            if not isinstance(lesson_entries, list) or not lesson_entries:
                add_issue(issues, display, 'Field "lessons" must be a non-empty ordered list.')
            else:
                for lesson_ref in lesson_entries:
                    if not isinstance(lesson_ref, str):
                        add_issue(issues, display, "Lesson entries must be paths.")
                        continue
                    lesson_path = portable_path(root, chapter_dir, lesson_ref, display, issues)
                    if lesson_path is None:
                        continue
                    if lesson_path.suffix != ".mcf":
                        add_issue(issues, display, f"Lesson must use .mcf extension: {lesson_ref}")
                    if not lesson_path.is_file():
                        add_issue(issues, display, f"Lesson path does not exist: {lesson_ref}")
                        continue
                    if not is_really_contained(root, lesson_path):
                        add_issue(
                            issues, display, f"Lesson path escapes the course root: {lesson_ref}"
                        )
                        continue
                    lesson_display = lesson_path.relative_to(root).as_posix()
                    try:
                        lesson_source = lesson_path.read_text(encoding="utf-8")
                    except (OSError, UnicodeError) as error:
                        add_issue(issues, lesson_display, f"Unable to read lesson: {error}")
                        continue
                    lessons.append(parse_lesson_source(lesson_source, lesson_display, issues))
            chapters.append(
                Chapter(
                    id=identifier(chapter_data, "id", display, issues),
                    title=text(chapter_data, "title", display, issues) or "",
                    description=optional_text(chapter_data, "description", display, issues),
                    source=source,
                    lessons=lessons,
                )
            )

    chapter_ids = [chapter.id for chapter in chapters]
    if len(set(chapter_ids)) != len(chapter_ids):
        add_issue(issues, "manifest.yaml", "Chapter IDs must be unique within the course.")
    lesson_sources: dict[str, set[str]] = {}
    for chapter in chapters:
        for lesson in chapter.lessons:
            lesson_sources.setdefault(lesson.id, set()).add(lesson.source)
    if any(len(sources) > 1 for sources in lesson_sources.values()):
        add_issue(
            issues,
            "manifest.yaml",
            "Distinct lesson files must use unique lesson IDs within the course.",
        )

    course = Course(
        id=identifier(manifest, "id", "manifest.yaml", issues),
        title=text(manifest, "title", "manifest.yaml", issues) or "",
        language=text(manifest, "language", "manifest.yaml", issues) or "",
        description=optional_text(manifest, "description", "manifest.yaml", issues),
        authors=string_list(manifest.get("authors"), "authors", "manifest.yaml", issues),
        license=optional_text(manifest, "license", "manifest.yaml", issues),
        version=optional_text(manifest, "version", "manifest.yaml", issues),
        cover=optional_text(manifest, "cover", "manifest.yaml", issues),
        root=root,
        chapters=chapters,
    )
    if course.cover:
        validate_reference(course.cover, root, root, "manifest.yaml", issues)
    for chapter in chapters:
        for lesson in chapter.lessons:
            base = (root / lesson.source).parent
            for content in _reference_fields(lesson):
                for match in REFERENCE_RE.finditer(content):
                    validate_reference(
                        match.group(1) or match.group(2), root, base, lesson.source, issues
                    )
    if any(item.severity == "error" for item in issues):
        raise ValidationError(issues)
    return course


def validate_course(input_path: str | Path) -> list[ValidationIssue]:
    """Return diagnostics without raising, useful for integrations and editors."""

    try:
        parse_course(input_path)
    except ValidationError as error:
        return error.issues
    return []
