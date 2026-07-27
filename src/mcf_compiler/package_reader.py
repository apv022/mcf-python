"""Secure directory and ``.mcf.zip`` package opening."""

from __future__ import annotations

import atexit
import shutil
import stat
import tempfile
import warnings
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from .model import ValidationIssue
from .yaml_profile import diagnostic

ARCHIVE_ENTRY_LIMIT = 4096
ARCHIVE_ENTRY_BYTES = 64 * 1024 * 1024
ARCHIVE_TOTAL_BYTES = 512 * 1024 * 1024
ARCHIVE_COMPRESSION_RATIO = 200


@dataclass(slots=True)
class PackageSource:
    root: Path
    source_type: Literal["directory", "archive"]
    temporary: Path | None = None

    def close(self) -> None:
        if self.temporary is not None:
            shutil.rmtree(self.temporary, ignore_errors=True)
            self.temporary = None


def valid_package_path(value: str) -> bool:
    if (
        not value
        or "\\" in value
        or "\0" in value
        or value.startswith("/")
        or "//" in value
        or (len(value) > 1 and value[1] == ":")
    ):
        return False
    return all(part not in {"", ".", ".."} for part in PurePosixPath(value).parts)


def open_package_source(
    input_path: str | Path, issues: list[ValidationIssue]
) -> PackageSource | None:
    source = Path(input_path).expanduser().resolve()
    if source.is_dir():
        return PackageSource(source, "directory")
    if not source.is_file():
        issues.append(
            diagnostic("MCF_PACKAGE_ENTRY_MISSING", str(input_path), "Package does not exist.")
        )
        return None
    if not str(input_path).endswith(".mcf.zip"):
        issues.append(
            diagnostic(
                "MCF_ARCHIVE_INVALID",
                str(input_path),
                "Archive packages must use the .mcf.zip suffix.",
            )
        )
        return None

    temporary = Path(tempfile.mkdtemp(prefix="mcf-package-"))
    atexit.register(shutil.rmtree, temporary, ignore_errors=True)
    try:
        with zipfile.ZipFile(source) as archive:
            names: set[str] = set()
            total = 0
            for index, entry in enumerate(archive.infolist(), start=1):
                name = entry.filename
                normalized = name[:-1] if name.endswith("/") else name
                if not valid_package_path(normalized):
                    issues.append(
                        diagnostic(
                            "MCF_PATH_TRAVERSAL", str(input_path), f"Unsafe archive entry: {name}"
                        )
                    )
                    raise ValueError
                if name in names:
                    issues.append(
                        diagnostic(
                            "MCF_ARCHIVE_INVALID",
                            str(input_path),
                            f"Duplicate archive entry: {name}",
                        )
                    )
                    raise ValueError
                names.add(name)
                mode = (entry.external_attr >> 16) & 0xFFFF
                kind = stat.S_IFMT(mode)
                if kind not in {0, stat.S_IFREG, stat.S_IFDIR}:
                    issues.append(
                        diagnostic(
                            "MCF_ARCHIVE_INVALID", str(input_path), f"Special archive entry: {name}"
                        )
                    )
                    raise ValueError
                if entry.flag_bits & 1:
                    issues.append(
                        diagnostic(
                            "MCF_ARCHIVE_INVALID",
                            str(input_path),
                            f"Encrypted archive entry: {name}",
                        )
                    )
                    raise ValueError
                total += entry.file_size
                ratio = (
                    float("inf")
                    if entry.compress_size == 0 and entry.file_size
                    else entry.file_size / max(entry.compress_size, 1)
                )
                if (
                    index > ARCHIVE_ENTRY_LIMIT
                    or entry.file_size > ARCHIVE_ENTRY_BYTES
                    or total > ARCHIVE_TOTAL_BYTES
                    or ratio > ARCHIVE_COMPRESSION_RATIO
                ):
                    issues.append(
                        diagnostic(
                            "MCF_ARCHIVE_LIMIT_EXCEEDED",
                            str(input_path),
                            f"Archive resource limit exceeded by {name}.",
                        )
                    )
                    raise ValueError
                destination = temporary.joinpath(*PurePosixPath(name).parts)
                if name.endswith("/"):
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with warnings.catch_warnings():
                        warnings.filterwarnings(
                            "ignore", message="Overlapped entries", category=UserWarning
                        )
                        with archive.open(entry) as reader, destination.open("wb") as writer:
                            shutil.copyfileobj(reader, writer)
                    if destination.stat().st_size != entry.file_size:
                        issues.append(
                            diagnostic(
                                "MCF_ARCHIVE_INVALID",
                                str(input_path),
                                f"Expanded size mismatch for {name}.",
                            )
                        )
                        raise ValueError
            if "manifest.yaml" not in names:
                issues.append(
                    diagnostic(
                        "MCF_PACKAGE_ENTRY_MISSING",
                        str(input_path),
                        "Archive root has no manifest.yaml.",
                    )
                )
                raise ValueError
    except ValueError:
        shutil.rmtree(temporary, ignore_errors=True)
        return None
    except (OSError, zipfile.BadZipFile, RuntimeError) as error:
        shutil.rmtree(temporary, ignore_errors=True)
        issues.append(diagnostic("MCF_ARCHIVE_INVALID", str(input_path), str(error)))
        return None
    return PackageSource(temporary, "archive", temporary)
