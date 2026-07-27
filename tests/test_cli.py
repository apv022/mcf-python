from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .conftest import NODE_REPOSITORY


def run_cli(*arguments: object) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(Path("src").resolve())
    return subprocess.run(
        [sys.executable, "-m", "mcf_compiler", *(str(value) for value in arguments)],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )


def test_help_and_version() -> None:
    help_result = run_cli("--help")
    assert help_result.returncode == 0
    assert "validate" in help_result.stdout
    assert "compile" in help_result.stdout
    version = run_cli("--version")
    assert version.returncode == 0
    assert version.stdout.strip() == "mcf 1.1.0"


def test_validate_success_and_failure_streams() -> None:
    valid = run_cli("validate", NODE_REPOSITORY / "examples/minimal")
    assert valid.returncode == 0
    assert "Valid MCF 1.0 course" in valid.stdout
    assert valid.stderr == ""
    invalid = run_cli("validate", NODE_REPOSITORY / "examples/invalid-traversal")
    assert invalid.returncode == 2
    assert invalid.stdout == ""
    assert "escapes the course root" in invalid.stderr


def test_compile_output_option(tmp_path: Path) -> None:
    result = run_cli(
        "compile", NODE_REPOSITORY / "examples/minimal", "--output", tmp_path / "library"
    )
    assert result.returncode == 0
    assert "Compiled MCF 1.0 A Minimal MCF Course" in result.stdout
    assert (tmp_path / "library/minimal-course/index.html").is_file()


def test_mcf_11_inspect_capabilities_and_version_exit() -> None:
    source = Path("/home/apv/mcf-spec/courses/minimal")
    inspected = run_cli("inspect", source, "--format", "json")
    assert inspected.returncode == 0
    assert '"mcf": "1.1"' in inspected.stdout
    capability_output = run_cli("capabilities")
    assert capability_output.returncode == 0
    assert '"mcf_versions": [' in capability_output.stdout
    mismatch = run_cli("validate", source, "--expected-version", "1.0")
    assert mismatch.returncode == 3
    assert "MCF_VERSION_UNSUPPORTED" in mismatch.stderr


def test_compile_mcf_11_module_and_lesson_packages(tmp_path: Path) -> None:
    spec = Path("/home/apv/mcf-spec")
    for kind, package_id in (
        ("module", "example-module"),
        ("lesson", "standalone-lesson"),
    ):
        output = tmp_path / kind
        result = run_cli("compile", spec / "fixtures/valid" / kind, "--output", output)
        assert result.returncode == 0, result.stderr
        assert "Compiled MCF 1.1" in result.stdout
        assert (output / package_id / "index.html").is_file()
