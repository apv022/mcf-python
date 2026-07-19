from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mcf_compiler.compiler import compile_course

from .conftest import NODE_REPOSITORY


def test_end_to_end_output_and_library_preservation(tmp_path: Path) -> None:
    compile_course(NODE_REPOSITORY / "examples/minimal", tmp_path)
    compile_course(NODE_REPOSITORY / "examples/showcase", tmp_path)
    catalog = json.loads((tmp_path / "courses.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in catalog] == ["minimal-course", "mcf-showcase"]
    target = tmp_path / "mcf-showcase"
    assert (target / "assets/audio/t-rex-roar.mp3").is_file()
    assert (target / "assets/video/flower.mp4").is_file()
    assert any((target / "katex/fonts").glob("*.woff2"))
    assert "localStorage" in (target / "player.js").read_text(encoding="utf-8")
    assert "import " not in (target / "player.js").read_text(encoding="utf-8")
    lesson_html = (target / "lessons/rich-content.html").read_text(encoding="utf-8")
    assert lesson_html.startswith('<!doctype html>\n<html lang="en">\n<head>')
    assert "../katex/katex.min.css" in lesson_html
    assert len(lesson_html.splitlines()) > 30
    assert "window.MCF_COURSE" in lesson_html


def test_recompile_removes_stale_files_and_preserves_other_courses(tmp_path: Path) -> None:
    first = compile_course(NODE_REPOSITORY / "examples/minimal", tmp_path)
    stale = first.directory / "stale.txt"
    stale.write_text("stale", encoding="utf-8")
    compile_course(NODE_REPOSITORY / "examples/showcase", tmp_path)
    compile_course(NODE_REPOSITORY / "examples/minimal", tmp_path)
    assert not stale.exists()
    assert (tmp_path / "mcf-showcase/course.json").is_file()
    assert not list(tmp_path.glob(".minimal-course.tmp-*"))
    assert not (tmp_path / ".minimal-course.previous").exists()


def test_internal_asset_symlink_keeps_authored_output_path(
    minimal_course: Path, tmp_path: Path
) -> None:
    assets = minimal_course / "assets"
    assets.mkdir()
    (assets / "real.txt").write_text("safe", encoding="utf-8")
    os.symlink("real.txt", assets / "alias.txt")
    lesson = minimal_course / "chapters/start/lessons/01-welcome.mcf"
    lesson.write_text(
        lesson.read_text(encoding="utf-8").replace(
            "This is", "[asset](../../../assets/alias.txt)\n\nThis is"
        ),
        encoding="utf-8",
    )
    result = compile_course(minimal_course, tmp_path / "output")
    assert (result.directory / "assets/alias.txt").read_text(encoding="utf-8") == "safe"


def test_output_file_conflict_is_reported(minimal_course: Path, tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "minimal-course").write_text("conflict", encoding="utf-8")
    with pytest.raises(OSError, match="not a directory"):
        compile_course(minimal_course, output)


def test_embedded_data_escapes_script_terminators(minimal_course: Path, tmp_path: Path) -> None:
    manifest = minimal_course / "manifest.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "A Minimal MCF Course", "A </script><script>alert(1)</script> Course"
        ),
        encoding="utf-8",
    )
    result = compile_course(minimal_course, tmp_path)
    html = (result.directory / "index.html").read_text(encoding="utf-8")
    assert "\\u003c/script>" in html
    assert html.count("<script>") == 1


def test_python_course_data_matches_node_reference(tmp_path: Path) -> None:
    import shutil
    import subprocess

    if shutil.which("node") is None:
        return
    python_output = tmp_path / "python"
    node_output = tmp_path / "node"
    compile_course(NODE_REPOSITORY / "examples/showcase", python_output)
    subprocess.run(
        [
            "node",
            str(NODE_REPOSITORY / "dist/src/cli.js"),
            "compile",
            str(NODE_REPOSITORY / "examples/showcase"),
            "--output",
            str(node_output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    python_data = json.loads(
        (python_output / "mcf-showcase/course.json").read_text(encoding="utf-8")
    )
    node_data = json.loads((node_output / "mcf-showcase/course.json").read_text(encoding="utf-8"))
    assert python_data == node_data
