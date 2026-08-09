"""Configure logging to the console and to the project log file."""

from __future__ import annotations

import logging

from src.utils.config import load_config, resolve_path

_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    """Return a logger, configuring the root logger once from ``configs/project.yaml``.

    Args:
        name: Logger name, normally ``__name__`` of the calling module.
    """
    global _CONFIGURED
    if not _CONFIGURED:
        settings = load_config("project")["logging"]
        log_file = resolve_path(settings["file"])
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            level=settings["level"],
            format=settings["format"],
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_file, encoding="utf-8"),
            ],
        )
        _CONFIGURED = True
    return logging.getLogger(name)
