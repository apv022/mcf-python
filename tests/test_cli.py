from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .conftest import NODE_REPOSITORY


def run_cli(*arguments: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mcf_compiler", *(str(value) for value in arguments)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_help_and_version() -> None:
    help_result = run_cli("--help")
    assert help_result.returncode == 0
    assert "validate" in help_result.stdout
    assert "compile" in help_result.stdout
    version = run_cli("--version")
    assert version.returncode == 0
    assert version.stdout.strip() == "mcf 1.0.0"


def test_validate_success_and_failure_streams() -> None:
    valid = run_cli("validate", NODE_REPOSITORY / "examples/minimal")
    assert valid.returncode == 0
    assert "Valid MCF 1.0 course" in valid.stdout
    assert valid.stderr == ""
    invalid = run_cli("validate", NODE_REPOSITORY / "examples/invalid-traversal")
    assert invalid.returncode == 1
    assert invalid.stdout == ""
    assert "escapes the course root" in invalid.stderr


def test_compile_output_option(tmp_path: Path) -> None:
    result = run_cli(
        "compile", NODE_REPOSITORY / "examples/minimal", "--output", tmp_path / "library"
    )
    assert result.returncode == 0
    assert "Compiled A Minimal MCF Course" in result.stdout
    assert (tmp_path / "library/minimal-course/index.html").is_file()
