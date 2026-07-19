from __future__ import annotations

import os
from pathlib import Path

import pytest

from mcf_compiler.lesson import parse_lesson_source
from mcf_compiler.model import ValidationError, ValidationIssue
from mcf_compiler.parser import parse_course, validate_course

from .conftest import SPEC_REPOSITORY


@pytest.mark.parametrize(
    ("fixture", "message"),
    [
        ("missing-title", 'Required field "title"'),
        ("unsupported-version", "Unsupported MCF version"),
        ("path-traversal", "escapes the course root"),
        ("duplicate-option", "duplicate option IDs"),
    ],
)
def test_normative_invalid_fixtures_are_rejected(fixture: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse_course(SPEC_REPOSITORY / "fixtures/invalid" / fixture)


def test_validation_accumulates_multiple_diagnostics(minimal_course: Path) -> None:
    (minimal_course / "manifest.yaml").write_text(
        "mcf: '2.0'\nid: BAD ID\nchapters: []\n", encoding="utf-8"
    )
    issues = validate_course(minimal_course)
    messages = "\n".join(issue.message for issue in issues)
    assert "Unsupported MCF version" in messages
    assert "Identifier" in messages
    assert 'Required field "title"' in messages
    assert 'Required field "language"' in messages
    assert "non-empty ordered list" in messages


def test_invalid_yaml_missing_asset_and_backslash_are_reported(minimal_course: Path) -> None:
    manifest = minimal_course / "manifest.yaml"
    manifest.write_text("mcf: [\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="Invalid YAML"):
        parse_course(minimal_course)

    manifest.write_text(
        """mcf: '1.0'
id: example
title: Example
language: en
chapters:
  - source: chapters\\start
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="forward slashes"):
        parse_course(minimal_course)


def test_missing_and_symlinked_assets_are_rejected(minimal_course: Path, tmp_path: Path) -> None:
    lesson = minimal_course / "chapters/start/lessons/01-welcome.mcf"
    source = lesson.read_text(encoding="utf-8")
    lesson.write_text(
        source.replace("This is", "![x](../../../assets/missing.png)\n\nThis is"), encoding="utf-8"
    )
    with pytest.raises(ValidationError, match="does not exist"):
        parse_course(minimal_course)

    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    assets = minimal_course / "assets"
    assets.mkdir(exist_ok=True)
    link = assets / "outside.txt"
    os.symlink(outside, link)
    lesson.write_text(
        source.replace("This is", "[outside](../../../assets/outside.txt)\n\nThis is"),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="escapes the course root"):
        parse_course(minimal_course)


def test_activity_and_question_semantics_accumulate() -> None:
    issues: list[ValidationIssue] = []
    parse_lesson_source(
        """---
id: bad
title: Bad
---
:::mcf-activity
type: notes
id: duplicate
passing_score: 2
randomize: yes
question_pool_size: 10
:::
```mcf-question
id: q
type: multiple_select
prompt: Pick
options:
  - {id: a, text: A}
  - {id: a, text: Again}
answer: [a, missing, a]
points: -1
```
:::mcf-end
:::mcf-activity
type: notes
id: duplicate
:::
```mcf-question
id: q
type: essay
prompt: Explain
answer: no
minimum_words: 0
keywords: [Same, same]
minimum_keywords: 3
```
:::mcf-end
""",
        "bad.mcf",
        issues,
    )
    messages = "\n".join(issue.message for issue in issues)
    for expected in (
        "invalid passing_score",
        "invalid randomize",
        "invalid question_pool_size",
        "duplicate option IDs",
        "no option with that ID",
        "duplicate option IDs",
        "points must be non-negative",
        "must not define an objective answer",
        "positive integer",
        "keywords must be distinct",
        "Activity IDs must be unique",
        "Question IDs must be unique",
    ):
        assert expected in messages
