"""Compile reference examples with Python and Node and compare stable semantics."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from mcf_compiler.compiler import compile_course


def files(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path, nargs="?", default=Path("../mcf-npm"))
    args = parser.parse_args()
    reference = args.reference.resolve()
    if shutil.which("node") is None:
        parser.error("node is required for the parity check")
    with tempfile.TemporaryDirectory(prefix="mcf-parity-") as temporary:
        root = Path(temporary)
        python_output, node_output = root / "python", root / "node"
        for example in ("minimal", "calculus-i", "showcase"):
            source = reference / "examples" / example
            python_result = compile_course(source, python_output)
            subprocess.run(
                [
                    "node",
                    str(reference / "dist/src/cli.js"),
                    "compile",
                    str(source),
                    "--output",
                    str(node_output),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            course_id = python_result.course.id
            python_course = python_output / course_id
            node_course = node_output / course_id
            python_data = json.loads((python_course / "course.json").read_text(encoding="utf-8"))
            node_data = json.loads((node_course / "course.json").read_text(encoding="utf-8"))
            if python_data != node_data:
                raise SystemExit(f"{example}: course data differs")
            required = {
                "index.html",
                "styles.css",
                "player.js",
                "course.json",
                *(f"lessons/{lesson['id']}.html" for lesson in python_data["lessons"]),
            }
            if not required <= files(python_course):
                raise SystemExit(f"{example}: Python output is missing structural files")
            for lesson in python_data["lessons"]:
                lesson_file = f"lessons/{lesson['id']}.html"
                python_html = (python_course / lesson_file).read_text(encoding="utf-8")
                node_html = (node_course / lesson_file).read_text(encoding="utf-8")
                for marker in (
                    "window.MCF_COURSE",
                    "lesson-link",
                    "lesson-nav",
                    "data-progress",
                    "../player.js",
                    "../katex/katex.min.css",
                ):
                    if marker not in python_html or marker not in node_html:
                        raise SystemExit(f"{example}/{lesson_file}: missing parity marker {marker}")
            print(f"{example}: metadata, ordering, structure, navigation, and hooks match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
