"""Portable, course-root-contained path discovery and reference checks."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from .model import ValidationIssue
from .yamlio import add_issue

REMOTE_RE = re.compile(r"^https?:", re.IGNORECASE)
YOUTUBE_RE = re.compile(r"^youtube:([A-Za-z0-9_-]+)$", re.IGNORECASE)


def portable_path(
    root: Path,
    base: Path,
    reference: str,
    display: str,
    issues: list[ValidationIssue],
) -> Path | None:
    if "\\" in reference:
        add_issue(issues, display, f"Path must use forward slashes: {reference}")
        return None
    candidate = (base / reference).resolve(strict=False)
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        add_issue(issues, display, f"Path escapes the course root: {reference}")
        return None
    return candidate


def is_really_contained(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError):
        return False
    return True


def is_valid_remote(reference: str) -> bool:
    parsed = urlparse(reference)
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.hostname)


def validate_reference(
    reference: str,
    root: Path,
    base: Path,
    display: str,
    issues: list[ValidationIssue],
) -> None:
    if reference.lower().startswith("youtube:"):
        if YOUTUBE_RE.fullmatch(reference) is None:
            add_issue(issues, display, f"Invalid YouTube provider reference: {reference}")
        return
    if REMOTE_RE.match(reference):
        if not is_valid_remote(reference):
            add_issue(issues, display, f"Invalid remote URL: {reference}")
        return
    if reference.lower().startswith("mailto:") or reference.startswith("#"):
        return
    candidate = portable_path(root, base, reference, display, issues)
    if candidate is None:
        return
    if not candidate.is_file():
        add_issue(issues, display, f"Referenced local asset does not exist: {reference}")
    elif not is_really_contained(root, candidate):
        add_issue(issues, display, f"Path escapes the course root: {reference}")
