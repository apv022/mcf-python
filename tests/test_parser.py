from __future__ import annotations

from mcf_compiler.lesson import parse_lesson_source
from mcf_compiler.model import ValidationIssue
from mcf_compiler.parser import parse_course

from .conftest import NODE_REPOSITORY, SPEC_REPOSITORY


def test_declared_chapter_and_lesson_order_is_preserved() -> None:
    course = parse_course(NODE_REPOSITORY / "examples/calculus-i")
    assert [chapter.id for chapter in course.chapters] == [
        "functions",
        "limits",
        "derivatives",
        "derivative-applications",
        "integrals",
        "integral-applications",
    ]
    assert [lesson.id for lesson in course.chapters[0].lessons] == [
        "functions-and-models",
        "transformations-and-composition",
        "inverse-and-exponential-models",
    ]


def test_every_question_type_and_activity_field_is_parsed() -> None:
    course = parse_course(NODE_REPOSITORY / "examples/showcase")
    assert [lesson.id for lesson in course.chapters[0].lessons] == [
        "rich-content",
        "questions",
    ]
    activities = [
        activity
        for chapter in course.chapters
        for lesson in chapter.lessons
        for activity in lesson.activities
    ]
    assert [question.type for activity in activities for question in activity.questions] == [
        "multiple_choice",
        "multiple_select",
        "true_false",
        "numeric",
        "short_answer",
        "essay",
    ]
    practice = activities[-2]
    assert practice.randomize is False
    assert practice.question_pool_size == 3
    assessment = activities[-1]
    assert assessment.passing_score == 0.7
    assert assessment.randomize is True
    assert assessment.question_pool_size is None
    essay = assessment.questions[-1]
    assert essay.minimum_words == 12
    assert essay.minimum_sentences == 2
    assert essay.keywords == ["local", "progress", "course"]
    assert essay.minimum_keywords == 2


def test_normative_specification_examples_parse() -> None:
    for example in ("minimal", "calculus-i", "feature-showcase"):
        parsed = parse_course(SPEC_REPOSITORY / "courses" / example)
        assert parsed.chapters
        assert all(chapter.lessons for chapter in parsed.chapters)


def test_frontmatter_comments_boundaries_and_source_order() -> None:
    issues: list[ValidationIssue] = []
    lesson = parse_lesson_source(
        """---
id: ordered
title: Ordered
authors: [Author]
---
<!-- allowed outside -->
:::mcf-activity
type: notes
id: first
:::
One
:::mcf-end
:::mcf-activity
type: practice
id: second
:::
Two
:::mcf-end
""",
        "ordered.mcf",
        issues,
    )
    assert not issues
    assert lesson.authors == ["Author"]
    assert [activity.id for activity in lesson.activities] == ["first", "second"]


def test_question_fence_is_replaced_in_place() -> None:
    course = parse_course(NODE_REPOSITORY / "examples/showcase")
    practice = course.chapters[0].lessons[1].activities[0]
    placeholders = [
        practice.content.index(f'data-mcf-question="{question.id}"')
        for question in practice.questions
    ]
    assert placeholders == sorted(placeholders)
