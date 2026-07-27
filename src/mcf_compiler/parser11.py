"""Native MCF 1.1 package and lesson parser."""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path
from typing import Any, cast

from .model import Activity, Chapter, Lesson, McfPackage, Option, Question, ValidationIssue
from .package_reader import valid_package_path
from .paths import is_really_contained
from .schema import validate_schema
from .yaml_profile import diagnostic, parse_mcf_yaml

ID = re.compile(r"^[a-z][a-z0-9._-]*$")
EXTENSION = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+){2,}$")
LANGUAGE = re.compile(
    r"^(?:[A-Za-z]{2,3}(?:-[A-Za-z]{3}){0,3}|[A-Za-z]{4}|[A-Za-z]{5,8})"
    r"(?:-[A-Za-z0-9]{1,8})*$|^x(?:-[A-Za-z0-9]{1,8})+$"
)
GRANDFATHERED_LANGUAGES = {"i-klingon"}


def valid_language(value: str) -> bool:
    if value.lower() in GRANDFATHERED_LANGUAGES:
        return True
    if LANGUAGE.fullmatch(value) is None:
        return False
    parts = value.lower().split("-")
    variants = [part for part in parts[1:] if len(part) >= 4]
    singletons = [part for part in parts[1:] if len(part) == 1]
    return len(variants) == len(set(variants)) and len(singletons) == len(set(singletons))


KINDS = {"course", "module", "lesson", "question_bank", "asset_collection"}
QUESTION_TYPES = {
    "multiple_choice",
    "multiple_select",
    "true_false",
    "numeric",
    "short_answer",
    "essay",
    "open_response",
    "matching",
    "ordering",
}
OBJECTIVE = QUESTION_TYPES - {"essay", "open_response"}
ACTIVITY_TYPES = {"notes", "practice", "assessment", "assignment"}
FRONTMATTER = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$")
ACTIVITY = re.compile(
    r":::mcf-activity[ \t]*\r?\n([\s\S]*?)\r?\n:::[ \t]*\r?\n"
    r"([\s\S]*?)\r?\n:::mcf-end(?:[ \t]*\r?\n|[ \t]*$)"
)
QUESTION = re.compile(r"```mcf-question[ \t]*\r?\n([\s\S]*?)\r?\n```")
QUESTION_REF = re.compile(r"```mcf-question-ref[ \t]*\r?\n([\s\S]*?)\r?\n```")
COMMENT = re.compile(r"<!--[\s\S]*?-->")
REFERENCE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)|@\[(?:audio|video)\]\(([^)\s]+)")
COMMON_METADATA = {
    "subjects",
    "keywords",
    "level",
    "estimated_duration",
    "prerequisites",
    "learning_outcomes",
}
RELATIONSHIP_TYPES = {
    "translation_of",
    "has_translation",
    "is_version_of",
    "has_version",
    "derived_from",
    "requires",
    "supplements",
}
ALTERNATE_PURPOSES = {
    "accessible_alternative",
    "low_bandwidth",
    "print",
    "transcoded",
}


def _add(
    issues: list[ValidationIssue],
    code: str,
    file: str,
    message: str,
    object_id: str | None = None,
) -> None:
    issues.append(diagnostic(code, file, message, object_id=object_id))


def _mapping(
    value: Any, issues: list[ValidationIssue], file: str, code: str = "MCF_SCHEMA_INVALID"
) -> dict[str, Any]:
    if isinstance(value, dict):
        return cast(dict[str, Any], value)
    _add(issues, code, file, "Expected a YAML mapping.")
    return {}


def _required_string(
    data: dict[str, Any],
    key: str,
    issues: list[ValidationIssue],
    file: str,
    code: str = "MCF_SCHEMA_INVALID",
) -> str:
    value = data.get(key)
    if isinstance(value, str) and value:
        return value
    _add(issues, code, file, f'"{key}" must be a non-empty string.')
    return ""


def _id(value: Any, issues: list[ValidationIssue], file: str, object_id: str | None = None) -> str:
    if not isinstance(value, str) or ID.fullmatch(value) is None:
        _add(issues, "MCF_ID_INVALID", file, f'Invalid identifier "{value}".', object_id)
        return value if isinstance(value, str) else "invalid"
    return value


def _unknown(
    data: dict[str, Any],
    allowed: set[str],
    issues: list[ValidationIssue],
    file: str,
    code: str,
) -> None:
    for key in data.keys() - allowed:
        _add(issues, code, file, f'Unknown core field "{key}".')


def _extensions(
    value: Any, issues: list[ValidationIssue], file: str, supported: set[str]
) -> dict[str, Any] | None:
    if value is None:
        return None
    data = _mapping(value, issues, file)
    for name, raw in data.items():
        if EXTENSION.fullmatch(name) is None:
            _add(
                issues,
                "MCF_EXTENSION_NAME_INVALID",
                file,
                f'Invalid extension namespace "{name}".',
            )
        entry = raw if isinstance(raw, dict) else {}
        if (
            not isinstance(raw, dict)
            or not isinstance(entry.get("required"), bool)
            or "data" not in entry
        ):
            _add(issues, "MCF_SCHEMA_INVALID", file, f'Extension "{name}" is malformed.')
        elif name not in supported:
            issues.append(
                diagnostic(
                    "MCF_EXTENSION_REQUIRED_UNSUPPORTED"
                    if entry["required"]
                    else "MCF_EXTENSION_OPTIONAL_UNSUPPORTED",
                    file,
                    f'Extension "{name}" is not supported.',
                    "error" if entry["required"] else "info",
                )
            )
    return data


def validate_relationship11(value: Any, file: str = "manifest.yaml") -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    data = _mapping(value, issues, file)
    if data.get("type") not in RELATIONSHIP_TYPES:
        _add(issues, "MCF_SCHEMA_INVALID", file, "Invalid relationship type.")
    _id(data.get("package"), issues, file)
    href = data.get("href")
    if href is not None and (
        not isinstance(href, str)
        or (
            not href.startswith("https://")
            and (not valid_package_path(href) or not href.endswith(".mcf.zip"))
        )
    ):
        _add(issues, "MCF_SCHEMA_INVALID", file, "Invalid relationship href.")
    if isinstance(data.get("language"), str) and not valid_language(data["language"]):
        _add(issues, "MCF_LANGUAGE_INVALID", file, "Invalid relationship language.")
    return issues


def validate_asset11(value: Any, file: str = "manifest.yaml") -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    data = _mapping(value, issues, file)
    _id(data.get("id"), issues, file)
    if not isinstance(data.get("source"), str) or not valid_package_path(data["source"]):
        _add(issues, "MCF_SCHEMA_INVALID", file, "Invalid asset source.")
    alternates = data.get("alternates")
    if alternates is not None:
        if not isinstance(alternates, list) or not alternates:
            _add(issues, "MCF_SCHEMA_INVALID", file, "Asset alternates must be non-empty.")
        else:
            for raw in alternates:
                alternate = raw if isinstance(raw, dict) else {}
                if (
                    not isinstance(raw, dict)
                    or not isinstance(alternate.get("source"), str)
                    or not valid_package_path(alternate["source"])
                    or alternate.get("purpose") not in ALTERNATE_PURPOSES
                ):
                    _add(issues, "MCF_SCHEMA_INVALID", file, "Invalid asset alternate.")
    return issues


def validate_rubric11(value: Any, file: str = "manifest.yaml") -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    data = _mapping(value, issues, file)
    _id(data.get("id"), issues, file)
    _required_string(data, "title", issues, file)
    criteria = data.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        _add(issues, "MCF_RUBRIC_INVALID", file, "Rubric criteria must be non-empty.")
        return issues
    for raw_criterion in criteria:
        criterion = raw_criterion if isinstance(raw_criterion, dict) else {}
        levels = criterion.get("levels")
        if (
            not isinstance(raw_criterion, dict)
            or ID.fullmatch(str(criterion.get("id"))) is None
            or not isinstance(criterion.get("description"), str)
            or not criterion["description"]
            or not isinstance(levels, list)
            or len(levels) < 2
        ):
            _add(issues, "MCF_RUBRIC_INVALID", file, "Invalid rubric criterion.")
            continue
        for level in levels:
            if (
                not isinstance(level, dict)
                or ID.fullmatch(str(level.get("id"))) is None
                or not isinstance(level.get("description"), str)
                or not isinstance(level.get("points"), (int, float))
                or isinstance(level.get("points"), bool)
                or level["points"] < 0
            ):
                _add(issues, "MCF_RUBRIC_INVALID", file, "Invalid rubric level.")
    return issues


def validate_completion11(
    value: Any,
    activities: set[str],
    questions: set[str],
    file: str,
    depth: int = 0,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if depth > 8 or not isinstance(value, dict) or set(value) not in ({"all"}, {"any"}):
        _add(issues, "MCF_COMPLETION_INVALID", file, "Invalid completion expression.")
        return issues
    entries = next(iter(value.values()))
    if not isinstance(entries, list) or not entries:
        _add(issues, "MCF_COMPLETION_INVALID", file, "Completion groups must be non-empty.")
        return issues
    requirements = {
        "viewed",
        "attempted",
        "answered",
        "submitted",
        "passed",
        "manually_marked_complete",
    }
    for entry in entries:
        if isinstance(entry, dict) and ("all" in entry or "any" in entry):
            issues.extend(validate_completion11(entry, activities, questions, file, depth + 1))
            continue
        if not isinstance(entry, dict):
            _add(issues, "MCF_COMPLETION_INVALID", file, "Invalid completion condition.")
            continue
        activity = entry.get("activity")
        question = entry.get("question")
        if (
            (isinstance(activity, str) == isinstance(question, str))
            or entry.get("requirement") not in requirements
            or (
                "minimum_score" in entry
                and (
                    entry.get("requirement") != "passed"
                    or not isinstance(entry["minimum_score"], (int, float))
                    or not 0 <= entry["minimum_score"] <= 1
                )
            )
        ):
            _add(issues, "MCF_COMPLETION_INVALID", file, "Invalid completion condition.")
        elif (activity and activity not in activities) or (question and question not in questions):
            _add(
                issues,
                "MCF_COMPLETION_REFERENCE_UNRESOLVED",
                file,
                "Completion condition refers to an unknown target.",
            )
    return issues


def _read_yaml(root: Path, relative: str, issues: list[ValidationIssue]) -> Any:
    try:
        return parse_mcf_yaml((root / relative).read_text(encoding="utf-8"), relative, issues)
    except (OSError, UnicodeError):
        _add(issues, "MCF_FILE_MISSING", relative, "Referenced file does not exist.")
        return {}


def _safe_path(
    root: Path,
    relative: Any,
    file: str,
    issues: list[ValidationIssue],
    *,
    directory: bool = False,
) -> Path | None:
    if not isinstance(relative, str) or not valid_package_path(relative):
        code = (
            "MCF_PATH_TRAVERSAL"
            if isinstance(relative, str) and ".." in relative.split("/")
            else "MCF_PATH_INVALID"
        )
        _add(issues, code, file, f'Invalid package path "{relative}".')
        return None
    target = root.joinpath(*relative.split("/"))
    try:
        good_type = target.is_dir() if directory else target.is_file()
        if not good_type or not is_really_contained(root, target):
            raise OSError
    except OSError:
        _add(
            issues,
            "MCF_FILE_MISSING",
            file,
            f"Referenced {'directory' if directory else 'file'} does not exist: {relative}",
        )
        return None
    return target


def _items(
    value: Any, issues: list[ValidationIssue], file: str, question_id: str
) -> list[Option] | None:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) < 2:
        _add(
            issues,
            "MCF_QUESTION_FIELDS_INVALID",
            file,
            "Question item lists require at least two entries.",
            question_id,
        )
        return []
    result: list[Option] = []
    for raw in value:
        item = _mapping(raw, issues, file, "MCF_QUESTION_FIELDS_INVALID")
        result.append(
            Option(
                _id(item.get("id"), issues, file, question_id),
                _required_string(item, "text", issues, file, "MCF_QUESTION_FIELDS_INVALID"),
                item.get("feedback") if isinstance(item.get("feedback"), str) else None,
                float(item["weight"])
                if isinstance(item.get("weight"), (int, float))
                and not isinstance(item.get("weight"), bool)
                else None,
            )
        )
    if len({item.id for item in result}) != len(result):
        _add(
            issues,
            "MCF_QUESTION_DUPLICATE_ITEM_ID",
            file,
            "Question item IDs repeat.",
            question_id,
        )
    return result


def parse_question11(
    value: Any,
    file: str,
    issues: list[ValidationIssue],
    supported_extensions: set[str] | None = None,
) -> Question | None:
    data = _mapping(value, issues, file, "MCF_QUESTION_FIELDS_INVALID")
    issues.extend(
        validate_schema(
            data,
            "1.1",
            "question.schema.json",
            file,
            code="MCF_QUESTION_FIELDS_INVALID",
        )
    )
    question_id = _id(data.get("id"), issues, file)
    question_type = data.get("type")
    if question_type not in QUESTION_TYPES:
        _add(
            issues,
            "MCF_QUESTION_TYPE_UNSUPPORTED",
            file,
            f'Unsupported question type "{question_type}".',
            question_id,
        )
        return None
    prompt = _required_string(data, "prompt", issues, file, "MCF_QUESTION_FIELDS_INVALID")
    options = _items(data.get("options"), issues, file, question_id)
    premises = _items(data.get("premises"), issues, file, question_id)
    responses = _items(data.get("responses"), issues, file, question_id)
    items = _items(data.get("items"), issues, file, question_id)
    answer = data.get("answer")
    option_ids = [item.id for item in options or []]
    if len(set(option_ids)) != len(option_ids):
        _add(
            issues,
            "MCF_QUESTION_DUPLICATE_OPTION_ID",
            file,
            "Option IDs repeat.",
            question_id,
        )
    if question_type in {"multiple_choice", "multiple_select"}:
        answers = answer if question_type == "multiple_select" else [answer]
        if (
            len(option_ids) < 2
            or not isinstance(answers, list)
            or not answers
            or any(item not in option_ids for item in answers)
        ):
            _add(
                issues,
                "MCF_QUESTION_ANSWER_REFERENCE_INVALID",
                file,
                "Answer refers to a missing option.",
                question_id,
            )
        if (
            question_type == "multiple_select"
            and isinstance(answers, list)
            and len(set(answers)) != len(answers)
        ):
            _add(
                issues,
                "MCF_QUESTION_ANSWER_REFERENCE_INVALID",
                file,
                "Answer contains duplicate option IDs.",
                question_id,
            )
        weighted = [item.weight is not None for item in options or []]
        if (
            question_type == "multiple_choice"
            and any(weighted)
            and (
                not all(weighted)
                or any(
                    item.weight is not None and not 0 <= item.weight <= 1 for item in options or []
                )
            )
        ):
            _add(
                issues,
                "MCF_QUESTION_FIELDS_INVALID",
                file,
                "Choice option weights must be complete and between zero and one.",
                question_id,
            )
        if question_type == "multiple_select" and any(weighted):
            _add(
                issues,
                "MCF_QUESTION_FIELDS_INVALID",
                file,
                "Multiple-select questions forbid option weights.",
                question_id,
            )
    elif question_type == "true_false" and not isinstance(answer, bool):
        _add(issues, "MCF_QUESTION_FIELDS_INVALID", file, "Answer must be boolean.", question_id)
    elif question_type == "numeric" and (
        not isinstance(answer, (int, float)) or isinstance(answer, bool)
    ):
        _add(issues, "MCF_QUESTION_FIELDS_INVALID", file, "Answer must be numeric.", question_id)
    elif question_type == "numeric" and isinstance(data.get("tolerance"), dict):
        tolerance_map = data["tolerance"]
        if (
            not tolerance_map
            or set(tolerance_map) - {"absolute", "relative"}
            or any(
                not isinstance(item, (int, float)) or isinstance(item, bool) or item < 0
                for item in tolerance_map.values()
            )
            or (answer == 0 and "relative" in tolerance_map)
        ):
            _add(
                issues,
                "MCF_QUESTION_FIELDS_INVALID",
                file,
                "Invalid numeric tolerance.",
                question_id,
            )
    elif question_type == "short_answer":
        answers = data.get("answers")
        if ("answer" in data and "answers" in data) or (
            not isinstance(answer, str)
            and not (
                isinstance(answers, list)
                and answers
                and all(isinstance(item, str) for item in answers)
            )
        ):
            _add(
                issues,
                "MCF_QUESTION_FIELDS_INVALID",
                file,
                "Short answer requires answer or answers.",
                question_id,
            )
    elif question_type == "matching":
        premise_ids = {item.id for item in premises or []}
        response_ids = {item.id for item in responses or []}
        if (
            not isinstance(answer, dict)
            or set(answer) != premise_ids
            or any(value not in response_ids for value in answer.values())
        ):
            _add(
                issues,
                "MCF_QUESTION_ANSWER_REFERENCE_INVALID",
                file,
                "Matching answer does not resolve to its premises and responses.",
                question_id,
            )
    elif question_type == "ordering":
        item_ids = [item.id for item in items or []]
        if (
            not isinstance(answer, list)
            or len(answer) != len(item_ids)
            or set(answer) != set(item_ids)
        ):
            _add(
                issues,
                "MCF_QUESTION_ANSWER_REFERENCE_INVALID",
                file,
                "Ordering answer must contain every item exactly once.",
                question_id,
            )
    elif question_type in {"essay", "open_response"} and "answer" in data:
        _add(
            issues,
            "MCF_QUESTION_FIELDS_INVALID",
            file,
            "Subjective questions must not define an objective answer.",
            question_id,
        )

    completion = any(
        key in data
        for key in ("minimum_words", "minimum_sentences", "keywords", "minimum_keywords")
    )
    evaluation = data.get("evaluation")
    if evaluation is None:
        evaluation = (
            "automatic"
            if question_type in OBJECTIVE
            else "manual"
            if question_type == "essay"
            else "completion"
            if completion
            else "ungraded"
        )
    valid_evaluation = (
        evaluation == "automatic"
        if question_type in OBJECTIVE
        else evaluation in {"manual", "completion"}
        if question_type == "essay"
        else evaluation == ("completion" if completion else "ungraded")
    )
    if not valid_evaluation:
        _add(
            issues,
            "MCF_QUESTION_FIELDS_INVALID",
            file,
            f'Invalid evaluation "{evaluation}" for {question_type}.',
            question_id,
        )
    if question_type == "open_response" and evaluation == "completion" and not completion:
        _add(
            issues,
            "MCF_QUESTION_FIELDS_INVALID",
            file,
            "Completion evaluation requires a completion rule.",
            question_id,
        )
    points = data.get("points", 1)
    required = data.get("required", True)
    if not isinstance(points, (int, float)) or isinstance(points, bool) or points < 0:
        _add(
            issues, "MCF_QUESTION_FIELDS_INVALID", file, "points must be non-negative.", question_id
        )
        points = 1
    if not isinstance(required, bool):
        _add(issues, "MCF_QUESTION_FIELDS_INVALID", file, "required must be boolean.", question_id)
        required = True
    tolerance = data.get("tolerance")
    if tolerance is not None and question_type != "numeric":
        _add(issues, "MCF_QUESTION_FIELDS_INVALID", file, "tolerance is numeric-only.", question_id)
    for key in ("minimum_words", "minimum_sentences", "minimum_keywords"):
        if key in data and (
            not isinstance(data[key], int) or isinstance(data[key], bool) or data[key] < 1
        ):
            _add(
                issues,
                "MCF_QUESTION_FIELDS_INVALID",
                file,
                f"{key} must be a positive integer.",
                question_id,
            )
    keywords = data.get("keywords")
    if keywords is not None and (
        not isinstance(keywords, list)
        or not keywords
        or not all(isinstance(item, str) and item.strip() for item in keywords)
    ):
        _add(issues, "MCF_QUESTION_FIELDS_INVALID", file, "keywords is invalid.", question_id)
        keywords = None
    return Question(
        id=question_id,
        type=question_type,
        prompt=prompt,
        options=options,
        answer=answer,
        answers=data.get("answers") if isinstance(data.get("answers"), list) else None,
        tolerance=tolerance,
        unit=data.get("unit") if isinstance(data.get("unit"), str) else None,
        normalization=data.get("normalization")
        if isinstance(data.get("normalization"), dict)
        else None,
        scoring=data.get("scoring") if isinstance(data.get("scoring"), str) else None,
        hint=data.get("hint") if isinstance(data.get("hint"), str) else None,
        explanation=data.get("explanation") if isinstance(data.get("explanation"), str) else None,
        points=float(points),
        required=required,
        evaluation=cast(str, evaluation),
        minimum_words=data.get("minimum_words")
        if isinstance(data.get("minimum_words"), int)
        else None,
        minimum_sentences=data.get("minimum_sentences")
        if isinstance(data.get("minimum_sentences"), int)
        else None,
        keywords=keywords,
        minimum_keywords=data.get("minimum_keywords")
        if isinstance(data.get("minimum_keywords"), int)
        else None,
        rubric=data.get("rubric") if isinstance(data.get("rubric"), str) else None,
        premises=premises,
        responses=responses,
        items=items,
        reuse_responses=data.get("reuse_responses")
        if isinstance(data.get("reuse_responses"), bool)
        else None,
        learning_outcomes=data.get("learning_outcomes")
        if isinstance(data.get("learning_outcomes"), list)
        else None,
        extensions=_extensions(data.get("extensions"), issues, file, supported_extensions or set()),
    )


def parse_lesson11(
    source: str,
    file: str,
    issues: list[ValidationIssue],
    supported_extensions: set[str],
) -> Lesson:
    match = FRONTMATTER.fullmatch(source)
    if match is None:
        _add(
            issues,
            "MCF_LESSON_FRONTMATTER_INVALID",
            file,
            "Lesson must begin with one YAML frontmatter block.",
        )
        return Lesson("invalid", "", file)
    front = _mapping(parse_mcf_yaml(match.group(1), file, issues), issues, file)
    issues.extend(
        validate_schema(
            front,
            "1.1",
            "lesson-frontmatter.schema.json",
            file,
            code="MCF_LESSON_FRONTMATTER_INVALID",
        )
    )
    body = match.group(2)
    activities: list[Activity] = []
    cursor = 0
    for found in ACTIVITY.finditer(body):
        if COMMENT.sub("", body[cursor : found.start()]).strip():
            _add(
                issues,
                "MCF_LESSON_CONTENT_OUTSIDE_ACTIVITY",
                file,
                "Lesson content occurs outside an activity.",
            )
        cursor = found.end()
        metadata = _mapping(parse_mcf_yaml(found.group(1), file, issues), issues, file)
        issues.extend(
            validate_schema(
                metadata,
                "1.1",
                "activity.schema.json",
                file,
                code="MCF_ACTIVITY_HEADER_INVALID",
            )
        )
        activity_id = _id(metadata.get("id"), issues, file)
        activity_type = metadata.get("type")
        if activity_type not in ACTIVITY_TYPES:
            _add(
                issues,
                "MCF_ACTIVITY_TYPE_UNSUPPORTED",
                file,
                f'Unsupported activity type "{activity_type}".',
                activity_id,
            )
        evaluation = metadata.get("evaluation")
        submission = metadata.get("submission")
        invalid_header = (
            (activity_type == "notes" and evaluation not in {None, "ungraded"})
            or (
                activity_type == "practice"
                and (
                    evaluation not in {None, "automatic", "manual", "completion"}
                    or submission is not None
                )
            )
            or (activity_type == "assessment" and evaluation == "ungraded")
            or (
                activity_type == "assignment"
                and (
                    evaluation not in {None, "manual", "completion"}
                    or not isinstance(submission, dict)
                )
            )
        )
        if invalid_header:
            _add(
                issues,
                "MCF_ACTIVITY_HEADER_INVALID",
                file,
                f'Invalid fields for activity type "{activity_type}".',
                activity_id,
            )
        questions: list[Question] = []
        references: list[dict[str, Any]] = []

        def question_replace(
            question_match: re.Match[str], target: list[Question] = questions
        ) -> str:
            parsed = parse_question11(
                parse_mcf_yaml(
                    question_match.group(1),
                    file,
                    issues,
                    "MCF_QUESTION_YAML_INVALID",
                ),
                file,
                issues,
                supported_extensions,
            )
            if parsed:
                target.append(parsed)
            return f'\n<div data-mcf-question="{parsed.id if parsed else "invalid"}"></div>\n'

        content = QUESTION.sub(question_replace, found.group(2))

        def reference_replace(
            reference_match: re.Match[str],
            target: list[dict[str, Any]] = references,
        ) -> str:
            raw = _mapping(parse_mcf_yaml(reference_match.group(1), file, issues), issues, file)
            bank = _id(raw.get("bank"), issues, file)
            question = _id(raw.get("question"), issues, file)
            target.append({"bank": bank, "question": question})
            return f'\n<div data-mcf-question-ref="{bank}:{question}"></div>\n'

        content = QUESTION_REF.sub(reference_replace, content)
        passing = metadata.get("passing_score")
        if passing is not None and (
            activity_type != "assessment"
            or not isinstance(passing, (int, float))
            or isinstance(passing, bool)
            or not 0 <= passing <= 1
        ):
            _add(
                issues,
                "MCF_ACTIVITY_HEADER_INVALID",
                file,
                "Invalid passing_score.",
                activity_id,
            )
        pool = metadata.get("question_pool_size")
        if pool is not None and (
            not isinstance(pool, int)
            or isinstance(pool, bool)
            or pool < 1
            or pool > len(questions) + len(references)
        ):
            _add(
                issues,
                "MCF_QUESTION_POOL_INVALID",
                file,
                "Invalid question_pool_size.",
                activity_id,
            )
        activities.append(
            Activity(
                id=activity_id,
                type=cast(Any, activity_type),
                content=content,
                questions=questions,
                title=metadata.get("title") if isinstance(metadata.get("title"), str) else None,
                passing_score=float(passing) if isinstance(passing, (int, float)) else None,
                randomize=metadata.get("randomize")
                if isinstance(metadata.get("randomize"), bool)
                else None,
                question_pool_size=pool if isinstance(pool, int) else None,
                evaluation=metadata.get("evaluation")
                if isinstance(metadata.get("evaluation"), str)
                else None,
                submission=metadata.get("submission")
                if isinstance(metadata.get("submission"), dict)
                else None,
                rubric=metadata.get("rubric") if isinstance(metadata.get("rubric"), str) else None,
                question_references=references or None,
                extensions=_extensions(
                    metadata.get("extensions"), issues, file, supported_extensions
                ),
                metadata={key: metadata[key] for key in COMMON_METADATA if key in metadata},
            )
        )
    if COMMENT.sub("", body[cursor:]).strip():
        _add(
            issues,
            "MCF_ACTIVITY_UNTERMINATED",
            file,
            "Unterminated activity or content outside an activity.",
        )
    if ":::mcf-activity" in "".join(activity.content for activity in activities):
        _add(issues, "MCF_ACTIVITY_NESTED", file, "Nested activities are not permitted.")
    if not activities:
        _add(issues, "MCF_SCHEMA_INVALID", file, "Lesson requires at least one activity.")
    if len({item.id for item in activities}) != len(activities):
        _add(issues, "MCF_ID_DUPLICATE", file, "Activity identifiers must be unique.")
    all_questions = [question.id for activity in activities for question in activity.questions]
    if len(set(all_questions)) != len(all_questions):
        _add(issues, "MCF_ID_DUPLICATE", file, "Question identifiers must be unique.")
    return Lesson(
        id=_id(front.get("id"), issues, file),
        title=_required_string(front, "title", issues, file),
        source=file,
        activities=activities,
        description=front.get("description") if isinstance(front.get("description"), str) else None,
        authors=front.get("authors") if isinstance(front.get("authors"), list) else None,
        license=front.get("license") if isinstance(front.get("license"), str) else None,
        rubrics=front.get("rubrics") if isinstance(front.get("rubrics"), list) else None,
        completion=front.get("completion") if isinstance(front.get("completion"), dict) else None,
        extensions=_extensions(front.get("extensions"), issues, file, supported_extensions),
        metadata={key: front[key] for key in COMMON_METADATA if key in front},
    )


def _load_lesson(
    root: Path,
    relative: Any,
    issues: list[ValidationIssue],
    supported_extensions: set[str],
) -> Lesson | None:
    path = _safe_path(root, relative, "manifest.yaml", issues)
    if path is None:
        return None
    assert isinstance(relative, str)
    if not relative.endswith(".mcf"):
        _add(issues, "MCF_PATH_INVALID", "manifest.yaml", "Lesson must use .mcf extension.")
    try:
        return parse_lesson11(
            path.read_text(encoding="utf-8"), relative, issues, supported_extensions
        )
    except (OSError, UnicodeError):
        _add(issues, "MCF_FILE_MISSING", relative, "Unable to read lesson.")
        return None


def parse_package11(
    root: Path,
    manifest: dict[str, Any],
    issues: list[ValidationIssue],
    source_type: str,
    supported_extensions: set[str],
) -> McfPackage:
    kind = manifest.get("kind")
    if kind not in KINDS:
        _add(issues, "MCF_PACKAGE_KIND_UNSUPPORTED", "manifest.yaml", f'Unsupported kind "{kind}".')
        kind = "course"
    package_id = _id(manifest.get("id"), issues, "manifest.yaml")
    title = _required_string(manifest, "title", issues, "manifest.yaml")
    language = manifest.get("language")
    if not isinstance(language, str) or not valid_language(language):
        _add(
            issues,
            "MCF_LANGUAGE_INVALID",
            "manifest.yaml",
            f'Invalid BCP 47 language tag "{language}".',
        )
        language = language if isinstance(language, str) else ""
    relationships = manifest.get("relationships")
    if relationships is not None and not isinstance(relationships, list):
        _add(issues, "MCF_SCHEMA_INVALID", "manifest.yaml", "relationships must be a list.")
        relationships = None
    for relationship in relationships or []:
        issues.extend(validate_relationship11(relationship))
    assets = manifest.get("assets")
    if assets is not None and not isinstance(assets, list):
        _add(issues, "MCF_SCHEMA_INVALID", "manifest.yaml", "assets must be a list.")
        assets = None
    for asset in assets or []:
        data = _mapping(asset, issues, "manifest.yaml")
        issues.extend(validate_asset11(data))
        asset_path = _safe_path(root, data.get("source"), "manifest.yaml", issues)
        for alternate in data.get("alternates", []):
            if isinstance(alternate, dict):
                _safe_path(root, alternate.get("source"), "manifest.yaml", issues)
        integrity = data.get("integrity")
        if asset_path is not None and isinstance(integrity, str) and "-" in integrity:
            algorithm, encoded = integrity.split("-", 1)
            if algorithm in {"sha256", "sha384", "sha512"}:
                actual = base64.b64encode(
                    hashlib.new(algorithm, asset_path.read_bytes()).digest()
                ).decode("ascii")
                if actual != encoded:
                    _add(
                        issues,
                        "MCF_ASSET_INTEGRITY_MISMATCH",
                        "manifest.yaml",
                        f'Asset integrity mismatch for "{data.get("id")}".',
                    )
    chapters: list[Chapter] = []
    lessons: list[Lesson] = []
    lesson: Lesson | None = None
    questions: list[Question] = []
    entry = manifest.get("entry") if isinstance(manifest.get("entry"), str) else None
    if kind == "course":
        raw_chapters = manifest.get("chapters")
        if not isinstance(raw_chapters, list) or not raw_chapters:
            _add(
                issues, "MCF_SCHEMA_INVALID", "manifest.yaml", "Course chapters must be non-empty."
            )
        else:
            for raw in raw_chapters:
                source = raw.get("source") if isinstance(raw, dict) else None
                directory = _safe_path(root, source, "manifest.yaml", issues, directory=True)
                if directory is None or not isinstance(source, str):
                    continue
                chapter_file = f"{source}/chapter.yaml"
                chapter_data = _mapping(
                    _read_yaml(root, chapter_file, issues), issues, chapter_file
                )
                issues.extend(
                    validate_schema(
                        chapter_data,
                        "1.1",
                        "chapter.schema.json",
                        chapter_file,
                    )
                )
                chapter_lessons: list[Lesson] = []
                refs = chapter_data.get("lessons")
                if not isinstance(refs, list) or not refs:
                    _add(issues, "MCF_SCHEMA_INVALID", chapter_file, "lessons must be non-empty.")
                else:
                    for ref in refs:
                        relative = f"{source}/{ref}" if isinstance(ref, str) else ref
                        parsed = _load_lesson(root, relative, issues, supported_extensions)
                        if parsed:
                            chapter_lessons.append(parsed)
                chapters.append(
                    Chapter(
                        id=_id(chapter_data.get("id"), issues, chapter_file),
                        title=_required_string(chapter_data, "title", issues, chapter_file),
                        source=source,
                        lessons=chapter_lessons,
                        description=chapter_data.get("description")
                        if isinstance(chapter_data.get("description"), str)
                        else None,
                        extensions=_extensions(
                            chapter_data.get("extensions"),
                            issues,
                            chapter_file,
                            supported_extensions,
                        ),
                        metadata={
                            key: chapter_data[key] for key in COMMON_METADATA if key in chapter_data
                        },
                    )
                )
    elif kind == "module":
        refs = manifest.get("lessons")
        if not isinstance(refs, list) or not refs:
            _add(issues, "MCF_SCHEMA_INVALID", "manifest.yaml", "Module lessons must be non-empty.")
        else:
            for raw in refs:
                relative = raw.get("source") if isinstance(raw, dict) else None
                parsed = _load_lesson(root, relative, issues, supported_extensions)
                if parsed:
                    lessons.append(parsed)
    elif kind == "lesson":
        lesson = _load_lesson(root, entry, issues, supported_extensions)
    elif kind == "question_bank":
        path = _safe_path(root, entry, "manifest.yaml", issues)
        if path is not None and entry:
            bank = _mapping(_read_yaml(root, entry, issues), issues, entry)
            issues.extend(
                validate_schema(
                    bank,
                    "1.1",
                    "question-bank.schema.json",
                    entry,
                )
            )
            raw_questions = bank.get("questions")
            if not isinstance(raw_questions, list) or not raw_questions:
                _add(issues, "MCF_SCHEMA_INVALID", entry, "Question bank must contain questions.")
            else:
                questions = [
                    parsed_question
                    for raw in raw_questions
                    if (
                        parsed_question := parse_question11(
                            raw, entry, issues, supported_extensions
                        )
                    )
                ]
    for rubric in manifest.get("rubrics") or []:
        issues.extend(validate_rubric11(rubric))
    rubric_ids = {
        rubric.get("id")
        for rubric in manifest.get("rubrics") or []
        if isinstance(rubric, dict) and isinstance(rubric.get("id"), str)
    }
    content_lessons = (
        [lesson] if lesson else lessons + [item for chapter in chapters for item in chapter.lessons]
    )
    asset_ids = {
        asset.get("id")
        for asset in assets or []
        if isinstance(asset, dict) and isinstance(asset.get("id"), str)
    }
    if len(asset_ids) != len(assets or []):
        _add(issues, "MCF_ID_DUPLICATE", "manifest.yaml", "Asset identifiers must be unique.")
    if len(rubric_ids) != len(manifest.get("rubrics") or []):
        _add(issues, "MCF_ID_DUPLICATE", "manifest.yaml", "Rubric identifiers must be unique.")
    chapter_ids = [chapter.id for chapter in chapters]
    if len(set(chapter_ids)) != len(chapter_ids):
        _add(issues, "MCF_ID_DUPLICATE", "manifest.yaml", "Chapter identifiers must be unique.")
    lesson_ids = [item.id for item in content_lessons]
    if len(set(lesson_ids)) != len(lesson_ids):
        _add(issues, "MCF_ID_DUPLICATE", "manifest.yaml", "Lesson identifiers must be unique.")
    if isinstance(manifest.get("cover"), str):
        _safe_path(root, manifest["cover"], "manifest.yaml", issues)
    for item in content_lessons:
        for rubric in item.rubrics or []:
            issues.extend(validate_rubric11(rubric, item.source))
        local_rubric_ids = rubric_ids | {
            rubric.get("id")
            for rubric in item.rubrics or []
            if isinstance(rubric, dict) and isinstance(rubric.get("id"), str)
        }
        for activity in item.activities:
            references = [activity.rubric] + [question.rubric for question in activity.questions]
            for reference in references:
                if reference and reference not in local_rubric_ids:
                    _add(
                        issues,
                        "MCF_RUBRIC_REFERENCE_UNRESOLVED",
                        item.source,
                        f'Rubric "{reference}" does not resolve.',
                    )
            rich_fields = [activity.content]
            for question in activity.questions:
                rich_fields.extend(
                    [
                        question.prompt,
                        question.hint or "",
                        question.explanation or "",
                        *(option.text for option in question.options or []),
                        *(part.text for part in question.premises or []),
                        *(part.text for part in question.responses or []),
                        *(part.text for part in question.items or []),
                    ]
                )
            for content in rich_fields:
                for match in REFERENCE.finditer(content):
                    reference = match.group(1) or match.group(2)
                    if reference.startswith("asset:"):
                        if reference.removeprefix("asset:") not in asset_ids:
                            _add(
                                issues,
                                "MCF_ASSET_REFERENCE_UNRESOLVED",
                                item.source,
                                f'Asset reference "{reference}" does not resolve.',
                            )
                    elif not re.match(r"^(?:https?:|youtube:|mailto:|#)", reference, re.IGNORECASE):
                        if "\\" in reference or "\0" in reference:
                            _add(
                                issues,
                                "MCF_PATH_INVALID",
                                item.source,
                                f'Invalid content path "{reference}".',
                            )
                            continue
                        candidate = (root / Path(item.source).parent / Path(reference)).resolve()
                        try:
                            candidate.relative_to(root.resolve())
                        except ValueError:
                            _add(
                                issues,
                                "MCF_PATH_TRAVERSAL",
                                item.source,
                                f"Content path escapes the package: {reference}",
                            )
                        else:
                            if not candidate.is_file() or not is_really_contained(root, candidate):
                                _add(
                                    issues,
                                    "MCF_FILE_MISSING",
                                    item.source,
                                    f"Referenced file does not exist: {reference}",
                                )
        if item.completion is not None:
            issues.extend(
                validate_completion11(
                    item.completion,
                    {activity.id for activity in item.activities},
                    {
                        question.id
                        for activity in item.activities
                        for question in activity.questions
                    },
                    item.source,
                )
            )
    return McfPackage(
        mcf="1.1",
        kind=cast(Any, kind),
        id=package_id,
        title=title,
        language=language,
        root=root,
        version=manifest.get("version") if isinstance(manifest.get("version"), str) else None,
        description=manifest.get("description")
        if isinstance(manifest.get("description"), str)
        else None,
        authors=manifest.get("authors") if isinstance(manifest.get("authors"), list) else None,
        license=manifest.get("license") if isinstance(manifest.get("license"), str) else None,
        cover=manifest.get("cover") if isinstance(manifest.get("cover"), str) else None,
        chapters=chapters,
        lessons=lessons,
        lesson=lesson,
        entry=entry,
        questions=questions,
        relationships=relationships,
        assets=assets,
        rubrics=manifest.get("rubrics") if isinstance(manifest.get("rubrics"), list) else None,
        extensions=_extensions(
            manifest.get("extensions"), issues, "manifest.yaml", supported_extensions
        ),
        diagnostics=issues,
        source_type=cast(Any, source_type),
        metadata={key: manifest[key] for key in COMMON_METADATA if key in manifest},
    )
