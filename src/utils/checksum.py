"""Compute and verify SHA-256 checksums of files."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK_SIZE = 1 << 20


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file, read in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksums(expected: dict[str, str], root: Path) -> list[str]:
    """Compare files against recorded checksums.

    Args:
        expected: Mapping of path (relative to ``root``, forward slashes) to SHA-256 digest.
        root: Directory the relative paths are resolved against.

    Returns:
        Relative paths that are missing or whose content changed. Empty if all match.
    """
    problems: list[str] = []
    for relative, digest in expected.items():
        path = root / relative
        if not path.is_file() or sha256_file(path) != digest:
            problems.append(relative)
    return problems
