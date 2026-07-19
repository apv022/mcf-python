from __future__ import annotations

import shutil
from pathlib import Path

import pytest

NODE_REPOSITORY = Path("/home/apv/mcf-npm")
SPEC_REPOSITORY = Path("/home/apv/MCF-Specification")


@pytest.fixture
def minimal_course(tmp_path: Path) -> Path:
    target = tmp_path / "minimal"
    shutil.copytree(NODE_REPOSITORY / "examples/minimal", target)
    return target
