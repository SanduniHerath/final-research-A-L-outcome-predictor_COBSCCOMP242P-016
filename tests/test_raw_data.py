"""Guard test: the registered raw data must never change."""

from __future__ import annotations

import json
import os

import pytest

from src.utils.checksum import verify_checksums
from src.utils.config import load_config, resolve_path

PATHS = load_config("project")["paths"]
MANIFEST = resolve_path(PATHS["raw_checksums"])
RAW_DIR = resolve_path(PATHS["raw"])

pytestmark = pytest.mark.skipif(not MANIFEST.exists(), reason="raw data not registered yet")


def test_raw_files_match_recorded_checksums() -> None:
    files = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    assert verify_checksums(files, RAW_DIR) == []


def test_raw_files_are_read_only() -> None:
    files = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    writable = [name for name in files if os.access(RAW_DIR / name, os.W_OK)]
    assert writable == []
