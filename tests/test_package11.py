from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import yaml

from mcf_compiler import (
    compile_course,
    compile_single_file,
    parse_package,
    validate_capability_declaration,
    validate_package,
)
from mcf_compiler.model import ValidationIssue
from mcf_compiler.parser11 import (
    parse_lesson11,
    parse_question11,
    valid_language,
    validate_asset11,
    validate_completion11,
    validate_relationship11,
    validate_rubric11,
)
from mcf_compiler.yaml_profile import parse_mcf_yaml

from .conftest import NODE_REPOSITORY, SPEC_REPOSITORY


def _suite() -> dict[str, object]:
    return yaml.safe_load((SPEC_REPOSITORY / "conformance/suite.yaml").read_text(encoding="utf-8"))


def test_every_canonical_valid_package_is_accepted() -> None:
    entries = _suite()["valid"]
    assert isinstance(entries, list)
    for entry in entries:
        assert isinstance(entry, dict)
        path = SPEC_REPOSITORY / str(entry["path"])
        result = validate_package(path)
        assert result.valid, (path, result.diagnostics)
        assert parse_package(path).mcf in {"1.0", "1.1"}


def test_every_canonical_invalid_package_has_expected_diagnostic() -> None:
    entries = _suite()["invalid"]
    assert isinstance(entries, list)
    for entry in entries:
        assert isinstance(entry, dict)
        path = SPEC_REPOSITORY / str(entry["path"])
        result = validate_package(path)
        expected = set(entry["expected"])
        actual = {item.code for item in result.diagnostics}
        assert not result.valid, path
        assert expected <= actual, (path, expected, actual)


def test_exact_version_dispatch_and_package_kinds() -> None:
    one_zero = parse_package(SPEC_REPOSITORY / "fixtures/valid/1.0/minimal")
    assert one_zero.mcf == "1.0"
    for kind in ("module", "lesson", "question-bank", "asset-collection"):
        package = parse_package(SPEC_REPOSITORY / "fixtures/valid" / kind)
        assert package.mcf == "1.1"
        assert package.kind == kind.replace("-", "_")


def test_archive_package_is_extracted_and_parsed() -> None:
    package = parse_package(SPEC_REPOSITORY / "fixtures/archives/valid-lesson.mcf.zip")
    assert package.kind == "lesson"
    assert package.source_type == "archive"


def test_canonical_yaml_profile_cases() -> None:
    cases = yaml.safe_load(
        (SPEC_REPOSITORY / "conformance/yaml-cases.yaml").read_text(encoding="utf-8")
    )["cases"]
    for case in cases:
        issues: list[ValidationIssue] = []
        value = parse_mcf_yaml(case["text"], "case.yaml", issues)
        assert (not any(item.severity == "error" for item in issues)) == case["valid"], (
            case["id"],
            value,
            issues,
        )


def test_canonical_question_cases() -> None:
    cases = yaml.safe_load(
        (SPEC_REPOSITORY / "conformance/question-cases.yaml").read_text(encoding="utf-8")
    )["cases"]
    for case in cases:
        issues: list[ValidationIssue] = []
        parse_question11(case["question"], "question.yaml", issues)
        actual = {item.code for item in issues}
        if case.get("valid"):
            assert not {item.code for item in issues if item.severity == "error"}, (
                case["id"],
                issues,
            )
        else:
            assert set(case["expected"]) <= actual, (case["id"], actual)


def test_canonical_activity_cases() -> None:
    cases = yaml.safe_load(
        (SPEC_REPOSITORY / "conformance/activity-cases.yaml").read_text(encoding="utf-8")
    )["cases"]
    for case in cases:
        header = yaml.safe_dump(case["activity"], sort_keys=False).rstrip()
        source = (
            "---\nid: lesson\ntitle: Lesson\n---\n"
            f":::mcf-activity\n{header}\n:::\nContent.\n:::mcf-end\n"
        )
        issues: list[ValidationIssue] = []
        parse_lesson11(source, "lesson.mcf", issues, set())
        actual = {item.code for item in issues}
        if case.get("valid"):
            assert "MCF_ACTIVITY_HEADER_INVALID" not in actual, (case["id"], issues)
        else:
            assert set(case["expected"]) <= actual, (case["id"], actual)


def test_canonical_language_cases() -> None:
    cases = yaml.safe_load(
        (SPEC_REPOSITORY / "conformance/language-cases.yaml").read_text(encoding="utf-8")
    )["cases"]
    for case in cases:
        assert valid_language(case["tag"]) is case["valid"], case["tag"]


def test_canonical_capability_cases() -> None:
    cases = yaml.safe_load(
        (SPEC_REPOSITORY / "conformance/capability-cases.yaml").read_text(encoding="utf-8")
    )["cases"]
    for case in cases:
        issues = validate_capability_declaration(case["value"])
        assert (not issues) is case["valid"], (case["value"], issues)


def test_mcf_11_compiles_to_directory_and_standalone(tmp_path) -> None:
    source = SPEC_REPOSITORY / "courses/feature-showcase"
    directory = compile_course(source, tmp_path / "library").directory
    assert (directory / "course.json").is_file()
    assert (directory / "assets/format-diagram.svg").is_file()
    standalone = compile_single_file(source, tmp_path / "showcase.html").file
    html = standalone.read_text(encoding="utf-8")
    assert 'data-standalone="true"' in html
    # Authored source remains present in normalized data for semantic fidelity;
    # the rendered media element itself must use the embedded byte source.
    assert '<img src="data:image/svg+xml;base64,' in html
    assert 'data-premise="notes"' in html
    assert "data-ordering-item=" in html
    assert "assignment-ui" in html
    assert "Submission declaration:" not in html


def test_canonical_asset_and_relationship_cases() -> None:
    for filename, validator in (
        ("asset-cases.yaml", validate_asset11),
        ("relationship-cases.yaml", validate_relationship11),
    ):
        cases = yaml.safe_load(
            (SPEC_REPOSITORY / "conformance" / filename).read_text(encoding="utf-8")
        )["cases"]
        for case in cases:
            assert (not validator(case["value"])) is case["valid"], (filename, case)


def test_rubric_and_completion_diagnostic_triggers() -> None:
    assert any(
        issue.code == "MCF_RUBRIC_INVALID"
        for issue in validate_rubric11({"id": "rubric", "title": "Invalid", "criteria": []})
    )
    invalid = validate_completion11(
        {"all": [{"activity": "missing", "requirement": "viewed"}]},
        {"known"},
        set(),
        "lesson.mcf",
    )
    assert {issue.code for issue in invalid} == {"MCF_COMPLETION_REFERENCE_UNRESOLVED"}


def _lesson(body: str, *, activity_type: str = "notes") -> str:
    return (
        "---\nid: lesson\ntitle: Lesson\n---\n"
        f":::mcf-activity\ntype: {activity_type}\nid: activity\n:::\n"
        f"{body}\n:::mcf-end\n"
    )


def test_activity_markers_follow_commonmark_fence_boundaries() -> None:
    for fence in ("```", "~~~"):
        issues: list[ValidationIssue] = []
        lesson = parse_lesson11(
            _lesson(f"{fence}mcf\n:::mcf-activity\n:::mcf-end\n{fence}"),
            "lesson.mcf",
            issues,
            set(),
        )
        assert len(lesson.activities) == 1
        assert "MCF_ACTIVITY_NESTED" not in {issue.code for issue in issues}

    issues = []
    parse_lesson11(
        _lesson(":::mcf-activity\n:::mcf-end"),
        "lesson.mcf",
        issues,
        set(),
    )
    assert "MCF_ACTIVITY_NESTED" in {issue.code for issue in issues}


def test_nested_source_question_fences_are_literal_and_crlf_is_normalized() -> None:
    source = _lesson(
        "````markdown\n```mcf-question\nid: literal\n"
        "type: true_false\nprompt: Literal?\nanswer: true\n```\n````"
    ).replace("\n", "\r\n")
    issues: list[ValidationIssue] = []
    lesson = parse_lesson11(source, "lesson.mcf", issues, set())
    assert not lesson.activities[0].questions
    assert not issues


def test_question_yaml_block_scalar_can_contain_shorter_code_fences() -> None:
    issues: list[ValidationIssue] = []
    lesson = parse_lesson11(
        _lesson(
            "````mcf-question\nid: scalar\n"
            "type: true_false\nprompt: |\n  Example:\n  ```\n  code\n  ```\n"
            "answer: true\n````",
            activity_type="practice",
        ),
        "lesson.mcf",
        issues,
        set(),
    )
    assert [question.id for question in lesson.activities[0].questions] == ["scalar"]
    assert not issues


def test_malformed_question_yaml_has_no_fabricated_followup_diagnostics() -> None:
    issues: list[ValidationIssue] = []
    parse_lesson11(
        _lesson("```mcf-question\n[\n```", activity_type="practice"),
        "lesson.mcf",
        issues,
        set(),
    )
    codes = {issue.code for issue in issues}
    assert "MCF_QUESTION_YAML_INVALID" in codes
    assert not codes & {
        "MCF_QUESTION_FIELDS_INVALID",
        "MCF_ID_INVALID",
        "MCF_QUESTION_TYPE_UNSUPPORTED",
    }


def _write_reference_package(root: Path, content: str) -> None:
    (root / "chapters/chapter/lessons").mkdir(parents=True)
    (root / "manifest.yaml").write_text(
        'mcf: "1.1"\nkind: course\nid: course\ntitle: Course\nlanguage: en\n'
        "chapters:\n  - source: chapters/chapter\n",
        encoding="utf-8",
    )
    (root / "chapters/chapter/chapter.yaml").write_text(
        "id: chapter\ntitle: Chapter\nlessons:\n  - lessons/lesson.mcf\n",
        encoding="utf-8",
    )
    (root / "chapters/chapter/lessons/lesson.mcf").write_text(
        _lesson(content),
        encoding="utf-8",
    )


def test_asset_references_are_extracted_only_from_live_markdown(tmp_path: Path) -> None:
    literal = tmp_path / "literal"
    _write_reference_package(
        literal,
        "`[inline](asset:graph)`\n\n```markdown\n"
        "![fenced](asset:graph)\n![missing](missing.svg)\n```",
    )
    result = validate_package(literal)
    assert result.valid, result.diagnostics
    assert compile_course(literal, tmp_path / "compiled").directory.is_dir()

    unresolved = tmp_path / "unresolved"
    _write_reference_package(unresolved, "![live](asset:graph)")
    assert "MCF_ASSET_REFERENCE_UNRESOLVED" in {
        issue.code for issue in validate_package(unresolved).diagnostics
    }

    missing = tmp_path / "missing"
    _write_reference_package(missing, "![live](missing.svg)")
    assert "MCF_FILE_MISSING" in {issue.code for issue in validate_package(missing).diagnostics}


def test_typescript_parity_for_canonical_validity_and_principal_codes() -> None:
    if shutil.which("node") is None:
        return
    suite = _suite()
    entries = [*suite["valid"], *suite["invalid"]]
    paths = [str(SPEC_REPOSITORY / entry["path"]) for entry in entries]
    script = """
import { validatePackage } from './dist/src/package.js';
const output = [];
for (const input of process.argv.slice(1)) {
  const result = await validatePackage(input);
  output.push({
    valid: result.valid,
    version: result.version,
    kind: result.kind,
    codes: result.diagnostics.map((item) => item.code),
  });
}
console.log(JSON.stringify(output));
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script, *paths],
        cwd=NODE_REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    )
    reference = json.loads(completed.stdout)
    for entry, path, expected in zip(entries, paths, reference, strict=True):
        python = validate_package(path)
        assert python.valid is expected["valid"], path
        if "version" in expected:
            assert python.version == expected["version"], path
        if "kind" in expected:
            assert python.kind == expected["kind"], path
        if "expected" in entry:
            principal = set(entry["expected"])
            assert principal <= {item.code for item in python.diagnostics}
            assert principal <= set(expected["codes"])
