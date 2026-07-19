"""Static reader generation and safe output-library management."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from importlib.resources import as_file, files
from pathlib import Path
from typing import Any, cast

from .model import Activity, Course, Lesson, ValidationError, ValidationIssue
from .parser import parse_course
from .render import encoded_lesson_id, escape, lesson_body, page


@dataclass(frozen=True, slots=True)
class CompileResult:
    course: Course
    directory: Path


def _without_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _without_none(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_without_none(item) for item in value]
    return value


def unique_lessons(course: Course) -> list[Lesson]:
    lessons: dict[str, Lesson] = {}
    for chapter in course.chapters:
        for lesson in chapter.lessons:
            lessons.setdefault(lesson.id, lesson)
    return list(lessons.values())


def _activity_data(activity: Activity) -> dict[str, Any]:
    value = asdict(activity)
    value.pop("content", None)
    return cast(dict[str, Any], _without_none(value))


def course_data(course: Course) -> dict[str, Any]:
    lessons = unique_lessons(course)
    return cast(
        dict[str, Any],
        _without_none(
            {
                "id": course.id,
                "title": course.title,
                "language": course.language,
                "description": course.description,
                "authors": course.authors,
                "license": course.license,
                "version": course.version,
                "cover": course.cover,
                "chapters": [
                    {
                        "id": chapter.id,
                        "title": chapter.title,
                        "description": chapter.description,
                        "lessons": [
                            {
                                "id": lesson.id,
                                "title": lesson.title,
                                "description": lesson.description,
                                "activities": [
                                    _activity_data(activity) for activity in lesson.activities
                                ],
                            }
                            for lesson in chapter.lessons
                        ],
                    }
                    for chapter in course.chapters
                ],
                "lessons": [
                    {
                        "id": lesson.id,
                        "title": lesson.title,
                        "activities": [_activity_data(activity) for activity in lesson.activities],
                    }
                    for lesson in lessons
                ],
            }
        ),
    )


def _json(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False).replace("<", "\\u003c")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _copy_packaged_file(relative: str, target: Path) -> None:
    resource = files("mcf_compiler").joinpath("assets", relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    with resource.open("rb") as source, target.open("wb") as destination:
        shutil.copyfileobj(source, destination)


def reader_styles() -> str:
    styles = files("mcf_compiler").joinpath("assets", "reader", "styles")
    names = sorted(item.name for item in styles.iterdir() if item.name.endswith(".css"))
    return "\n".join(styles.joinpath(name).read_text(encoding="utf-8") for name in names)


def _copy_packaged_tree(relative: str, target: Path) -> None:
    resource = files("mcf_compiler").joinpath("assets", relative)
    with as_file(resource) as source:
        shutil.copytree(source, target, dirs_exist_ok=True)


def _copy_course_file(course: Course, source: Path, target: Path) -> None:
    try:
        root = course.root.resolve(strict=True)
        lexical_source = Path(os.path.abspath(source))
        relative = lexical_source.relative_to(root)
        resolved_source = lexical_source.resolve(strict=True)
        resolved_source.relative_to(root)
    except (OSError, ValueError) as error:
        raise ValidationError(
            [ValidationIssue(source.as_posix(), "Asset path escapes the course root.")]
        ) from error
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(resolved_source, destination)


def _copy_source_assets(course: Course, target: Path) -> None:
    assets = course.root / "assets"
    if not assets.exists():
        return
    for source in assets.rglob("*"):
        if source.is_dir():
            continue
        _copy_course_file(course, source, target)


def _copy_referenced_files(course: Course, target: Path) -> None:
    if course.cover and not course.cover.lower().startswith(("http:", "https:")):
        _copy_course_file(course, course.root / course.cover, target)
    reference_pattern = __import__("re").compile(
        r"!?\[[^\]]*\]\(([^\s)]+)|@\[(?:audio|video)\]\(([^\s)]+)"
    )
    for lesson in unique_lessons(course):
        fields: list[str] = []
        for activity in lesson.activities:
            fields.append(activity.content)
            for question in activity.questions:
                fields.extend([question.prompt, question.hint or "", question.explanation or ""])
                fields.extend(option.text for option in question.options or [])
        for content in fields:
            for match in reference_pattern.finditer(content):
                reference = match.group(1) or match.group(2)
                if reference.lower().startswith(
                    ("http:", "https:", "youtube:", "mailto:")
                ) or reference.startswith("#"):
                    continue
                source = (course.root / lesson.source).parent / reference
                _copy_course_file(course, source, target)


def sidebar(course: Course, current: str | None = None) -> str:
    prefix = "" if current else "lessons/"
    chapter_html: list[str] = []
    for chapter in course.chapters:
        links = "\n".join(
            f'      <a class="lesson-link {"current" if lesson.id == current else ""}" '
            f'data-lesson-id="{escape(lesson.id)}" '
            f'href="{prefix}{encoded_lesson_id(lesson.id)}.html">{escape(lesson.title)}</a>'
            for lesson in chapter.lessons
        )
        chapter_html.append(
            f"""    <div>
      <div class="chapter-label">{escape(chapter.title)}</div>
{links}
    </div>"""
        )
    return f"""<aside class="sidebar">
  <a href="../index.html">← Course library</a>
  <h1>{escape(course.title)}</h1>
  <div class="progress"><i data-progress-bar style="width:0"></i></div>
  <b data-progress>0%</b>
  <nav>
{chr(10).join(chapter_html)}
  </nav>
</aside>"""


def lesson_page(course: Course, lesson: Lesson, index: int, lessons: list[Lesson]) -> str:
    previous = lessons[index - 1] if index else None
    following = lessons[index + 1] if index + 1 < len(lessons) else None
    previous_link = (
        f'<a class="button" href="{encoded_lesson_id(previous.id)}.html">'
        f"← {escape(previous.title)}</a>"
        if previous
        else "<span></span>"
    )
    next_link = (
        f'<a class="button" href="{encoded_lesson_id(following.id)}.html">'
        f"{escape(following.title)} →</a>"
        if following
        else '<a class="button" href="../index.html">Course overview</a>'
    )
    description = f"<p>{escape(lesson.description)}</p>" if lesson.description else ""
    body = f"""<div class="course-shell">
{sidebar(course, lesson.id)}
<main class="main">
  <div class="lesson">
    <header class="lesson-header">
      <span class="eyebrow">Lesson {index + 1} of {len(lessons)}</span>
      <h1>{escape(lesson.title)}</h1>
      {description}
    </header>
{lesson_body(lesson, course)}
    <div class="badge hidden">
      <div class="badge-mark">✓</div>
      <h2>Course complete</h2>
      <p>{escape(course.title)}</p>
      <p>Completed <span data-completion-date></span></p>
    </div>
    <nav class="lesson-nav">
      {previous_link}
      {next_link}
    </nav>
  </div>
</main>
</div>
<script>
window.MCF_COURSE = {_json(course_data(course))};
</script>"""
    html = page(
        f"{lesson.title} · {course.title}",
        course.language,
        body,
        "../styles.css",
        "../player.js",
        "../katex/katex.min.css",
    )
    return html.replace("<body>", f'<body data-lesson="{escape(lesson.id)}">', 1)


def _library_entry(course: Course) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        _without_none(
            {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "authors": course.authors,
                "version": course.version,
                "cover": course.cover,
                "lessons": [lesson.id for lesson in unique_lessons(course)],
            }
        ),
    )


def update_library(output: Path, course: Course) -> None:
    catalog_file = output / "courses.json"
    catalog: list[dict[str, Any]] = []
    try:
        candidate = json.loads(catalog_file.read_text(encoding="utf-8"))
        if isinstance(candidate, list):
            catalog = [item for item in candidate if isinstance(item, dict)]
    except (OSError, json.JSONDecodeError):
        pass
    catalog = [item for item in catalog if item.get("id") != course.id]
    catalog.append(_library_entry(course))
    catalog.sort(key=lambda item: str(item.get("title", "")).casefold())
    _atomic_write(catalog_file, json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")
    library_runtime = (
        files("mcf_compiler").joinpath("assets", "reader", "library.js").read_text(encoding="utf-8")
    )
    _atomic_write(
        output / "library.js", f"window.MCF_LIBRARY = {_json(catalog)};\n{library_runtime}"
    )
    library_body = """<main class="library">
  <header>
    <span class="eyebrow">Local-first learning</span>
    <h1>Course library</h1>
    <p>Your compiled MCF courses, available offline.</p>
  </header>
  <section id="courses" class="course-grid"></section>
</main>"""
    _atomic_write(
        output / "index.html",
        page("MCF Course Library", "en", library_body, "styles.css", "library.js"),
    )
    _atomic_write(output / "styles.css", reader_styles())


def compile_course(input_path: str | Path, output: str | Path = "courses") -> CompileResult:
    course = parse_course(input_path)
    output_root = Path(output).expanduser().resolve()
    if output_root.exists() and not output_root.is_dir():
        raise OSError(f"Output path is not a directory: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / course.id
    if target.exists() and not target.is_dir():
        raise OSError(f"Course output path is not a directory: {target}")
    staging = Path(tempfile.mkdtemp(prefix=f".{course.id}.tmp-", dir=output_root))
    backup = output_root / f".{course.id}.previous"
    try:
        (staging / "lessons").mkdir()
        data = course_data(course)
        _atomic_write(
            staging / "course.json", json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        )
        _atomic_write(staging / "styles.css", reader_styles())
        _copy_packaged_file("reader/player.js", staging / "player.js")
        _copy_packaged_tree("katex", staging / "katex")
        _copy_source_assets(course, staging)
        _copy_referenced_files(course, staging)
        lessons = unique_lessons(course)
        for index, lesson in enumerate(lessons):
            _atomic_write(
                staging / "lessons" / f"{lesson.id}.html",
                lesson_page(course, lesson, index, lessons),
            )
        overview = f"""<div class="course-shell">
{sidebar(course)}
<main class="main">
  <div class="lesson">
    <h1>{escape(course.title)}</h1>
    <p>{escape(course.description or "")}</p>
    <p>{escape(", ".join(course.authors or []))}</p>
    <div class="progress"><i data-progress-bar></i></div>
    <b data-progress>0%</b>
    <p><a class="button" href="lessons/{encoded_lesson_id(lessons[0].id)}.html">Start course</a></p>
    <div class="progress-actions">
      <button data-export>Export progress</button>
      <label class="button">Import progress<input data-import type="file"
        accept="application/json" hidden></label>
    </div>
    <div class="badge hidden">
      <div class="badge-mark">✓</div>
      <h2>Course complete</h2>
      <p>{escape(course.title)}</p>
      <p>Completed <span data-completion-date></span></p>
    </div>
  </div>
</main>
</div>
<script>
window.MCF_COURSE = {_json(data)};
</script>"""
        _atomic_write(
            staging / "index.html",
            page(
                course.title,
                course.language,
                overview,
                "styles.css",
                "player.js",
                "katex/katex.min.css",
            ),
        )

        if backup.exists():
            shutil.rmtree(backup)
        if target.exists():
            os.replace(target, backup)
        try:
            os.replace(staging, target)
        except BaseException:
            if backup.exists():
                os.replace(backup, target)
            raise
        if backup.exists():
            shutil.rmtree(backup)
        update_library(output_root, course)
        return CompileResult(course=course, directory=target)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
