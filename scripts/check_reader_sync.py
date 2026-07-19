"""Check vendored reader assets against a local mcf-npm checkout."""

from __future__ import annotations

import argparse
import filecmp
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path, nargs="?", default=Path("../mcf-npm"))
    args = parser.parse_args()
    local = Path(__file__).parents[1] / "src/mcf_compiler/assets/reader"
    pairs = [
        (local / "player.js", args.reference / "dist/reader/player.js"),
        (local / "library.js", args.reference / "dist/reader/library.js"),
    ]
    pairs.extend(
        (file, args.reference / "src/reader/styles" / file.name)
        for file in sorted((local / "styles").glob("*.css"))
    )
    different = [str(source) for source, reference in pairs if not filecmp.cmp(source, reference)]
    if different:
        print("Reader assets differ:\n" + "\n".join(different))
        return 1
    print(f"Reader assets match {args.reference.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
