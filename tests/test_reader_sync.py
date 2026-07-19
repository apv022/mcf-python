from __future__ import annotations

import filecmp
from pathlib import Path

from .conftest import NODE_REPOSITORY


def test_vendored_reader_assets_match_reference() -> None:
    local = Path("src/mcf_compiler/assets/reader")
    assert filecmp.cmp(local / "player.js", NODE_REPOSITORY / "dist/reader/player.js")
    assert filecmp.cmp(local / "library.js", NODE_REPOSITORY / "dist/reader/library.js")
    for stylesheet in (local / "styles").glob("*.css"):
        assert filecmp.cmp(stylesheet, NODE_REPOSITORY / "src/reader/styles" / stylesheet.name)
