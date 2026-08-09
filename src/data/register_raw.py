"""Register the raw data files: record checksums and basic shape, then make them read-only.

Run once after placing files in ``data/raw``:

    python -m src.data.register_raw          # register (refuses to overwrite an existing record)
    python -m src.data.register_raw --verify # check nothing in data/raw has changed
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils.checksum import sha256_file, verify_checksums
from src.utils.config import PROJECT_ROOT, load_config, resolve_path
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)


def list_raw_files(raw_dir: Path) -> list[Path]:
    """Return every file under ``raw_dir``, sorted, ignoring placeholder files."""
    return sorted(p for p in raw_dir.rglob("*") if p.is_file() and p.name != ".gitkeep")


def make_read_only(path: Path) -> None:
    """Remove write permission from a file (sets the Windows read-only attribute)."""
    os.chmod(path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)


def describe_spreadsheet(path: Path, sheet: str | None) -> dict[str, Any]:
    """Return row and column counts of a spreadsheet sheet."""
    frame = pd.read_excel(path, sheet_name=sheet or 0)
    return {"sheet": sheet or "first", "rows": int(frame.shape[0]), "columns": int(frame.shape[1])}


def check_expected_shapes(data_cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Read each configured spreadsheet and compare its shape with the configured expectation."""
    shapes: dict[str, dict[str, Any]] = {}
    for key in ("survey", "pilot"):
        spec = data_cfg["raw_files"][key]
        shape = describe_spreadsheet(resolve_path(spec["path"]), spec["sheet"])
        expected = (spec["expected_rows"], spec["expected_columns"])
        if (shape["rows"], shape["columns"]) != expected:
            logger.warning("%s: shape %s differs from expected %s", key, shape, expected)
        else:
            logger.info(
                "%s: %d rows x %d columns as expected", key, shape["rows"], shape["columns"]
            )
        shapes[spec["path"]] = shape
    return shapes


def register(raw_dir: Path, manifest_path: Path) -> dict[str, Any]:
    """Record checksums and shapes for all raw files and make them read-only."""
    if manifest_path.exists():
        raise FileExistsError(
            f"{manifest_path} already exists. Raw data is registered once; delete it only "
            "if a new raw file was deliberately added, and record why in the phase document."
        )
    files = list_raw_files(raw_dir)
    checksums = {p.relative_to(raw_dir).as_posix(): sha256_file(p) for p in files}
    manifest = {
        "registered_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "algorithm": "sha256",
        "files": checksums,
        "spreadsheet_shapes": check_expected_shapes(load_config("data")),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for path in files:
        make_read_only(path)
        logger.info("Registered and set read-only: %s", path.relative_to(PROJECT_ROOT).as_posix())
    return manifest


def verify(raw_dir: Path, manifest_path: Path) -> bool:
    """Return True if every registered raw file still matches its checksum."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = verify_checksums(manifest["files"], raw_dir)
    present = {p.relative_to(raw_dir).as_posix() for p in list_raw_files(raw_dir)}
    unregistered = sorted(present - set(manifest["files"]))
    for name in problems:
        logger.error("Missing or changed raw file: %s", name)
    for name in unregistered:
        logger.error("Unregistered file in data/raw: %s", name)
    ok = not problems and not unregistered
    if ok:
        logger.info("All %d raw files match their recorded checksums", len(manifest["files"]))
    return ok


def main() -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Register or verify raw data files.")
    parser.add_argument("--verify", action="store_true", help="only verify recorded checksums")
    args = parser.parse_args()
    paths = load_config("project")["paths"]
    raw_dir, manifest_path = resolve_path(paths["raw"]), resolve_path(paths["raw_checksums"])
    if args.verify:
        return 0 if verify(raw_dir, manifest_path) else 1
    register(raw_dir, manifest_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
