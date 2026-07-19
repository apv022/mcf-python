"""YAML loading and scalar validation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeAlias, cast

import yaml

from .model import ValidationIssue

Data: TypeAlias = dict[str, Any]


def add_issue(issues: list[ValidationIssue], file: str, message: str) -> None:
    issues.append(ValidationIssue(file=file, message=message))


def as_object(value: object) -> Data:
    return cast(Data, value) if isinstance(value, dict) else {}


def load_yaml_text(raw: str, display: str, issues: list[ValidationIssue], kind: str) -> Data:
    try:
        return as_object(yaml.safe_load(raw))
    except yaml.YAMLError as error:
        label = f"{kind} YAML" if kind else "YAML"
        add_issue(issues, display, f"Invalid {label}: {error}")
        return {}


def load_yaml_file(path: Path, display: str, issues: list[ValidationIssue]) -> Data:
    try:
        return load_yaml_text(path.read_text(encoding="utf-8"), display, issues, "")
    except (OSError, UnicodeError) as error:
        add_issue(issues, display, f"Invalid YAML: {error}")
        return {}


def text(
    data: Data,
    key: str,
    file: str,
    issues: list[ValidationIssue],
    *,
    required: bool = True,
) -> str | None:
    value = data.get(key)
    if isinstance(value, str) and value:
        return value
    if required:
        add_issue(issues, file, f'Required field "{key}" must be a non-empty string.')
    return None


def optional_text(data: Data, key: str, file: str, issues: list[ValidationIssue]) -> str | None:
    if key not in data:
        return None
    return text(data, key, file, issues)


def string_list(
    value: object, key: str, file: str, issues: list[ValidationIssue]
) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return cast(list[str], value)
    add_issue(issues, file, f'Field "{key}" must be a list of strings.')
    return None
