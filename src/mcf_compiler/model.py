"""Typed intermediate representation shared by MCF 1.0 and MCF 1.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeAlias

QuestionType: TypeAlias = Literal[
    "multiple_choice",
    "multiple_select",
    "true_false",
    "numeric",
    "short_answer",
    "essay",
    "open_response",
    "matching",
    "ordering",
]
ActivityType: TypeAlias = Literal["notes", "practice", "assessment", "assignment"]
PackageKind: TypeAlias = Literal["course", "module", "lesson", "question_bank", "asset_collection"]
Answer: TypeAlias = Any


@dataclass(slots=True)
class Option:
    id: str
    text: str
    feedback: str | None = None
    weight: float | None = None


@dataclass(slots=True)
class Question:
    id: str
    type: QuestionType | str
    prompt: str
    options: list[Option] | None = None
    answer: Answer = None
    tolerance: float | None = None
    hint: str | None = None
    explanation: str | None = None
    points: float = 1
    required: bool = True
    minimum_words: int | None = None
    minimum_sentences: int | None = None
    keywords: list[str] | None = None
    minimum_keywords: int | None = None
    evaluation: str | None = None
    answers: list[str] | None = None
    unit: str | None = None
    normalization: dict[str, Any] | None = None
    scoring: str | None = None
    rubric: str | None = None
    premises: list[Option] | None = None
    responses: list[Option] | None = None
    items: list[Option] | None = None
    reuse_responses: bool | None = None
    learning_outcomes: list[str] | None = None
    extensions: dict[str, Any] | None = None
    source_reference: dict[str, Any] | None = None


@dataclass(slots=True)
class Activity:
    id: str
    type: ActivityType | str
    content: str
    questions: list[Question] = field(default_factory=list)
    title: str | None = None
    passing_score: float | None = None
    randomize: bool | None = None
    question_pool_size: int | None = None
    evaluation: str | None = None
    submission: dict[str, Any] | None = None
    rubric: str | None = None
    question_references: list[dict[str, Any]] | None = None
    extensions: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Lesson:
    id: str
    title: str
    source: str
    activities: list[Activity] = field(default_factory=list)
    description: str | None = None
    authors: list[str] | None = None
    license: str | None = None
    rubrics: list[dict[str, Any]] | None = None
    completion: dict[str, Any] | None = None
    extensions: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Chapter:
    id: str
    title: str
    source: str
    lessons: list[Lesson] = field(default_factory=list)
    description: str | None = None
    extensions: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Course:
    id: str
    title: str
    language: str
    root: Path
    chapters: list[Chapter] = field(default_factory=list)
    mcf: Literal["1.0", "1.1"] = "1.0"
    kind: Literal["course"] = "course"
    description: str | None = None
    authors: list[str] | None = None
    license: str | None = None
    version: str | None = None
    cover: str | None = None
    relationships: list[dict[str, Any]] | None = None
    assets: list[dict[str, Any]] | None = None
    rubrics: list[dict[str, Any]] | None = None
    extensions: dict[str, Any] | None = None
    diagnostics: list[ValidationIssue] = field(default_factory=list)
    source_type: Literal["directory", "archive"] = "directory"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class McfPackage:
    mcf: Literal["1.1"]
    kind: PackageKind
    id: str
    title: str
    language: str
    root: Path
    version: str | None = None
    description: str | None = None
    authors: list[str] | None = None
    license: str | None = None
    cover: str | None = None
    chapters: list[Chapter] = field(default_factory=list)
    lessons: list[Lesson] = field(default_factory=list)
    lesson: Lesson | None = None
    entry: str | None = None
    questions: list[Question] = field(default_factory=list)
    relationships: list[dict[str, Any]] | None = None
    assets: list[dict[str, Any]] | None = None
    rubrics: list[dict[str, Any]] | None = None
    extensions: dict[str, Any] | None = None
    diagnostics: list[ValidationIssue] = field(default_factory=list)
    source_type: Literal["directory", "archive"] = "directory"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    file: str
    message: str
    severity: Literal["error", "warning"] = "error"
    code: str = "MCF_SCHEMA_INVALID"
    location: dict[str, int] | None = None
    object_id: str | None = None

    def __str__(self) -> str:
        where = self.file
        if self.location and self.location.get("line"):
            where += f":{self.location['line']}:{self.location.get('column', 1)}"
        return f"{where}: {self.code}: {self.message}"


class ValidationError(Exception):
    """Raised after all discoverable source errors have been accumulated."""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        super().__init__("\n\n".join(str(item) for item in issues))
