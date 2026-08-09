"""Load YAML configuration files and resolve project paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
CONFIG_DIR: Path = PROJECT_ROOT / "configs"


def load_config(name: str) -> dict[str, Any]:
    """Read ``configs/<name>.yaml`` and return it as a dictionary.

    Args:
        name: Config file name without the ``.yaml`` extension.

    Returns:
        The parsed YAML content.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def resolve_path(relative: str | Path) -> Path:
    """Turn a path from a config file (relative to the project root) into an absolute path."""
    path = Path(relative)
    return path if path.is_absolute() else PROJECT_ROOT / path


def get_seed() -> int:
    """Return the single project-wide random seed from ``configs/project.yaml``."""
    return int(load_config("project")["seed"])
