"""Load, lock and verify the success criteria fixed in Phase 2.

The criteria in ``configs/success_criteria.yaml`` must be fixed before any model is
trained. Locking records the file's checksum; later phases call :func:`require_locked`
and stop if the file was changed afterwards.

    python -m src.evaluation.criteria --lock     # after the researcher confirms
    python -m src.evaluation.criteria --verify
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.utils.checksum import sha256_file
from src.utils.config import CONFIG_DIR, load_config
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)

CRITERIA_FILE = CONFIG_DIR / "success_criteria.yaml"
LOCK_FILE = CONFIG_DIR / "success_criteria.lock.json"


class CriteriaNotLockedError(RuntimeError):
    """Raised when the success criteria are not locked or were changed after locking."""


def load_criteria() -> dict[str, Any]:
    """Return the success criteria as a dictionary."""
    return load_config("success_criteria")


def lock(criteria_file: Path = CRITERIA_FILE, lock_file: Path = LOCK_FILE) -> dict[str, str]:
    """Record the checksum of the confirmed criteria file.

    Raises:
        ValueError: If the file's ``status`` is not ``confirmed``.
        FileExistsError: If the criteria are already locked.
    """
    if lock_file.exists():
        raise FileExistsError(f"Criteria already locked in {lock_file}")
    text = criteria_file.read_text(encoding="utf-8")
    if "\nstatus: confirmed" not in f"\n{text}":
        raise ValueError("Set 'status: confirmed' in the criteria file before locking")
    record = {
        "file": criteria_file.name,
        "sha256": sha256_file(criteria_file),
        "locked_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    lock_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def is_locked(criteria_file: Path = CRITERIA_FILE, lock_file: Path = LOCK_FILE) -> bool:
    """Return True if the criteria are locked and unchanged since locking."""
    if not lock_file.exists():
        return False
    record = json.loads(lock_file.read_text(encoding="utf-8"))
    return record["sha256"] == sha256_file(criteria_file)


def require_locked(criteria_file: Path = CRITERIA_FILE, lock_file: Path = LOCK_FILE) -> None:
    """Stop with an error unless the criteria are locked and unchanged."""
    if not is_locked(criteria_file, lock_file):
        raise CriteriaNotLockedError(
            "Success criteria are not locked or were changed after locking. "
            "Modelling and evaluation may not start."
        )


def main() -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description="Lock or verify the success criteria.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--lock", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.lock:
        record = lock()
        logger.info("Criteria locked: %s", record)
        return 0
    if is_locked():
        logger.info("Criteria are locked and unchanged")
        return 0
    logger.error("Criteria are NOT locked, or were changed after locking")
    return 1


if __name__ == "__main__":
    sys.exit(main())
