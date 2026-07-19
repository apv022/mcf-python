"""Typed intermediate representation for MCF 1.0 source packages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, TypeAlias

QuestionType: TypeAlias = Literal[
    "multiple_choice", "multiple_select", "true_false", "numeric", "short_answer", "essay"
]
ActivityType: TypeAlias = Literal["notes", "practice", "assessment"]
Answer: TypeAlias = str | bool | int | float | list[str] | None


@dataclass(slots=True)
class Option:
    id: str
    text: str


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


@dataclass(slots=True)
class Lesson:
    id: str
    title: str
    source: str
    activities: list[Activity] = field(default_factory=list)
    description: str | None = None
    authors: list[str] | None = None
    license: str | None = None


@dataclass(slots=True)
class Chapter:
    id: str
    title: str
    source: str
    lessons: list[Lesson] = field(default_factory=list)
    description: str | None = None


@dataclass(slots=True)
class Course:
    id: str
    title: str
    language: str
    root: Path
    chapters: list[Chapter] = field(default_factory=list)
    mcf: Literal["1.0"] = "1.0"
    description: str | None = None
    authors: list[str] | None = None
    license: str | None = None
    version: str | None = None
    cover: str | None = None


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    file: str
    message: str
    severity: Literal["error", "warning"] = "error"

    def __str__(self) -> str:
        return f"{self.file}:\n{self.message}"


class ValidationError(Exception):
    """Raised after all discoverable source errors have been accumulated."""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        super().__init__("\n\n".join(str(item) for item in issues))
