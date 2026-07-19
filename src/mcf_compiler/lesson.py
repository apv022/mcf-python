"""Lesson frontmatter, activity-container, and question-fence parsing."""

from __future__ import annotations

import math
import re
from typing import Any, cast

from .model import Activity, Lesson, Option, Question, ValidationIssue
from .yamlio import add_issue, as_object, load_yaml_text, optional_text, string_list, text

ID_RE = re.compile(r"^[a-z][a-z0-9._-]*$")
QUESTION_TYPES = {
    "multiple_choice",
    "multiple_select",
    "true_false",
    "numeric",
    "short_answer",
    "essay",
}
ACTIVITY_TYPES = {"notes", "practice", "assessment"}
FRONTMATTER_RE = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$")
ACTIVITY_RE = re.compile(
    r":::mcf-activity\s*\r?\n([\s\S]*?)\r?\n:::\s*\r?\n([\s\S]*?)"
    r"\r?\n:::mcf-end(?:\s*\r?\n|\s*$)"
)
QUESTION_RE = re.compile(r"```mcf-question\s*\r?\n([\s\S]*?)\r?\n```")
COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")


def identifier(data: dict[str, Any], key: str, file: str, issues: list[ValidationIssue]) -> str:
    value = text(data, key, file, issues) or "invalid"
    if ID_RE.fullmatch(value) is None:
        add_issue(issues, file, f'Identifier "{value}" must match [a-z][a-z0-9._-]*.')
    return value


def _number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def parse_question(raw: str, file: str, issues: list[ValidationIssue]) -> Question | None:
    data = load_yaml_text(raw, file, issues, "mcf-question")
    question_id = identifier(data, "id", file, issues)
    question_type = text(data, "type", file, issues) or "invalid"
    prompt = text(data, "prompt", file, issues) or ""
    if question_type not in QUESTION_TYPES:
        add_issue(issues, file, f'Question "{question_id}" has unsupported type "{question_type}".')

    raw_options = data.get("options")
    options: list[Option] | None = None
    if raw_options is not None:
        if not isinstance(raw_options, list):
            add_issue(issues, file, f'Question "{question_id}" options must be a list.')
        else:
            options = []
            for entry in raw_options:
                option = as_object(entry)
                options.append(
                    Option(
                        id=identifier(option, "id", file, issues),
                        text=text(option, "text", file, issues) or "",
                    )
                )
    option_ids = [option.id for option in options or []]
    if len(set(option_ids)) != len(option_ids):
        add_issue(issues, file, f'Question "{question_id}" has duplicate option IDs.')

    answer = data.get("answer")
    if question_type in {"multiple_choice", "multiple_select"}:
        if not options:
            add_issue(issues, file, f'Question "{question_id}" requires options.')
        answers: object = answer if question_type == "multiple_select" else [answer]
        if (
            not isinstance(answers, list)
            or not answers
            or any(not isinstance(item, str) for item in answers)
        ):
            add_issue(issues, file, f'Question "{question_id}" has an invalid answer.')
        else:
            for selected in cast(list[str], answers):
                if selected not in option_ids:
                    add_issue(
                        issues,
                        file,
                        f'Question "{question_id}" references answer "{selected}", '
                        "but no option with that ID exists.",
                    )
            if question_type == "multiple_select" and len(set(answers)) != len(answers):
                add_issue(
                    issues,
                    file,
                    f'Question "{question_id}" answer must not contain duplicate option IDs.',
                )
    elif raw_options is not None:
        add_issue(
            issues,
            file,
            f'Question "{question_id}" type "{question_type}" must not define options.',
        )
    elif question_type == "true_false" and not isinstance(answer, bool):
        add_issue(issues, file, f'Question "{question_id}" answer must be true or false.')
    elif question_type == "numeric" and not _number(answer):
        add_issue(issues, file, f'Question "{question_id}" answer must be numeric.')
    elif question_type == "short_answer" and not isinstance(answer, str):
        add_issue(issues, file, f'Question "{question_id}" answer must be a string.')
    elif question_type == "essay" and "answer" in data:
        add_issue(
            issues, file, f'Essay question "{question_id}" must not define an objective answer.'
        )

    essay_fields = ("minimum_words", "minimum_sentences", "keywords", "minimum_keywords")
    if question_type != "essay" and any(field in data for field in essay_fields):
        add_issue(
            issues,
            file,
            f'Question "{question_id}" uses essay completion fields but is not an essay.',
        )
    for field_name in ("minimum_words", "minimum_sentences", "minimum_keywords"):
        if field_name in data and not _positive_integer(data[field_name]):
            add_issue(
                issues,
                file,
                f'Essay question "{question_id}" field "{field_name}" must be a positive integer.',
            )
    keywords = string_list(data.get("keywords"), "keywords", file, issues)
    if "keywords" in data and (not keywords or any(not word.strip() for word in keywords)):
        add_issue(
            issues,
            file,
            f'Essay question "{question_id}" keywords must be a non-empty list '
            "of non-empty strings.",
        )
    if keywords and len({word.lower().strip() for word in keywords}) != len(keywords):
        add_issue(issues, file, f'Essay question "{question_id}" keywords must be distinct.')
    if "minimum_keywords" in data and "keywords" not in data:
        add_issue(
            issues, file, f'Essay question "{question_id}" minimum_keywords requires keywords.'
        )
    if (
        _number(data.get("minimum_keywords"))
        and keywords
        and cast(int, data["minimum_keywords"]) > len(keywords)
    ):
        add_issue(
            issues,
            file,
            f'Essay question "{question_id}" minimum_keywords must not exceed '
            "the number of keywords.",
        )

    tolerance = data.get("tolerance")
    if tolerance is not None and (
        question_type != "numeric" or not _number(tolerance) or cast(float, tolerance) < 0
    ):
        add_issue(issues, file, f'Question "{question_id}" has invalid tolerance.')
    points = data.get("points")
    if points is not None and (not _number(points) or cast(float, points) < 0):
        add_issue(issues, file, f'Question "{question_id}" points must be non-negative.')
    required = data.get("required")
    if required is not None and not isinstance(required, bool):
        add_issue(issues, file, f'Question "{question_id}" required must be boolean.')

    typed_answer = cast(str | bool | int | float | list[str] | None, answer)
    return Question(
        id=question_id,
        type=question_type,
        prompt=prompt,
        options=options,
        answer=typed_answer,
        tolerance=cast(float | None, tolerance),
        hint=optional_text(data, "hint", file, issues),
        explanation=optional_text(data, "explanation", file, issues),
        points=cast(float, points) if _number(points) else 1,
        required=required if isinstance(required, bool) else True,
        minimum_words=cast(int | None, data.get("minimum_words")),
        minimum_sentences=cast(int | None, data.get("minimum_sentences")),
        keywords=keywords,
        minimum_keywords=cast(int | None, data.get("minimum_keywords")),
    )


def parse_lesson_source(
    source: str, file: str, issues: list[ValidationIssue] | None = None
) -> Lesson:
    diagnostics = issues if issues is not None else []
    match = FRONTMATTER_RE.match(source)
    if match is None:
        add_issue(diagnostics, file, "Lesson must begin with YAML frontmatter delimited by ---.")
        return Lesson(id="invalid", title="", source=file)
    front = load_yaml_text(match.group(1), file, diagnostics, "frontmatter")
    body = match.group(2)
    activities: list[Activity] = []
    cursor = 0
    for found in ACTIVITY_RE.finditer(body):
        outside = COMMENT_RE.sub("", body[cursor : found.start()]).strip()
        if outside:
            add_issue(
                diagnostics,
                file,
                f'Content outside an activity container near "{outside[:40]}".',
            )
        cursor = found.end()
        metadata = load_yaml_text(found.group(1), file, diagnostics, "activity")
        activity_id = identifier(metadata, "id", file, diagnostics)
        activity_type = text(metadata, "type", file, diagnostics) or "invalid"
        if activity_type not in ACTIVITY_TYPES:
            add_issue(
                diagnostics,
                file,
                f'Activity "{activity_id}" has unsupported type "{activity_type}".',
            )
        passing_score = metadata.get("passing_score")
        if passing_score is not None and (
            activity_type != "assessment"
            or not _number(passing_score)
            or not 0 <= cast(float, passing_score) <= 1
        ):
            add_issue(diagnostics, file, f'Activity "{activity_id}" has invalid passing_score.')
        randomize = metadata.get("randomize")
        if randomize is not None and (
            activity_type not in {"practice", "assessment"} or not isinstance(randomize, bool)
        ):
            add_issue(diagnostics, file, f'Activity "{activity_id}" has invalid randomize.')
        pool_size = metadata.get("question_pool_size")
        if pool_size is not None and (
            activity_type not in {"practice", "assessment"} or not _positive_integer(pool_size)
        ):
            add_issue(
                diagnostics, file, f'Activity "{activity_id}" has invalid question_pool_size.'
            )

        questions: list[Question] = []

        def replace_question(
            question_match: re.Match[str], target: list[Question] = questions
        ) -> str:
            question = parse_question(question_match.group(1), file, diagnostics)
            if question is not None:
                target.append(question)
            return f'\n<div data-mcf-question="{question.id if question else "invalid"}"></div>\n'

        content = QUESTION_RE.sub(replace_question, found.group(2))
        if (
            isinstance(pool_size, int)
            and not isinstance(pool_size, bool)
            and pool_size > len(questions)
        ):
            add_issue(
                diagnostics,
                file,
                f'Activity "{activity_id}" question_pool_size exceeds its '
                f"{len(questions)} available questions.",
            )
        activities.append(
            Activity(
                id=activity_id,
                type=activity_type,
                title=optional_text(metadata, "title", file, diagnostics),
                passing_score=cast(float | None, passing_score),
                randomize=randomize if isinstance(randomize, bool) else None,
                question_pool_size=pool_size if isinstance(pool_size, int) else None,
                content=content,
                questions=questions,
            )
        )

    if COMMENT_RE.sub("", body[cursor:]).strip():
        add_issue(diagnostics, file, "Unclosed activity container or content outside an activity.")
    if not activities:
        add_issue(diagnostics, file, "Lesson must contain at least one activity.")
    activity_ids = [activity.id for activity in activities]
    question_ids = [question.id for activity in activities for question in activity.questions]
    if len(set(activity_ids)) != len(activity_ids):
        add_issue(diagnostics, file, "Activity IDs must be unique within the lesson.")
    if len(set(question_ids)) != len(question_ids):
        add_issue(diagnostics, file, "Question IDs must be unique within the lesson.")

    return Lesson(
        id=identifier(front, "id", file, diagnostics),
        title=text(front, "title", file, diagnostics) or "",
        description=optional_text(front, "description", file, diagnostics),
        authors=string_list(front.get("authors"), "authors", file, diagnostics),
        license=optional_text(front, "license", file, diagnostics),
        source=file,
        activities=activities,
    )
