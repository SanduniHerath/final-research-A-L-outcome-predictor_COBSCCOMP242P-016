"""Shared test settings."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# The API tests must never write into the real app database (data/app/alora.db).
os.environ["ALORA_DB"] = str(Path(tempfile.mkdtemp(prefix="alora_test_")) / "alora_test.db")
