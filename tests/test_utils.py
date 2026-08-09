"""Tests for the shared utilities (config, seeds, checksums)."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pytest

from src.utils.checksum import sha256_file, verify_checksums
from src.utils.config import PROJECT_ROOT, get_seed, load_config, resolve_path
from src.utils.seed import set_global_seed


def test_project_config_has_seed_and_paths() -> None:
    cfg = load_config("project")
    assert isinstance(cfg["seed"], int)
    assert {"raw", "interim", "processed", "raw_checksums"} <= set(cfg["paths"])


def test_missing_config_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_config("does_not_exist")


def test_resolve_path_is_relative_to_project_root() -> None:
    assert resolve_path("data/raw") == PROJECT_ROOT / "data" / "raw"


def test_seed_makes_random_draws_repeatable() -> None:
    set_global_seed()
    first = (random.random(), np.random.rand())
    set_global_seed()
    assert (random.random(), np.random.rand()) == first
    assert set_global_seed() == get_seed()


def test_torch_seed_is_repeatable() -> None:
    torch = pytest.importorskip("torch")
    set_global_seed()
    first = torch.rand(3)
    set_global_seed()
    assert torch.equal(torch.rand(3), first)


def test_sha256_known_value(tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_bytes(b"abc")
    assert sha256_file(file) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_verify_checksums_detects_change_and_missing(tmp_path: Path) -> None:
    file = tmp_path / "a.txt"
    file.write_bytes(b"abc")
    expected = {"a.txt": sha256_file(file), "gone.txt": "0" * 64}
    assert verify_checksums(expected, tmp_path) == ["gone.txt"]
    file.write_bytes(b"abd")
    assert verify_checksums(expected, tmp_path) == ["a.txt", "gone.txt"]
