"""Fix random seeds for Python, NumPy and PyTorch from one place."""

from __future__ import annotations

import os
import random

import numpy as np

from src.utils.config import get_seed


def set_global_seed(seed: int | None = None) -> int:
    """Seed every random number generator the project uses.

    Args:
        seed: Seed to use. If ``None``, the seed from ``configs/project.yaml`` is used.

    Returns:
        The seed that was applied.
    """
    seed = get_seed() if seed is None else seed
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
    except ImportError:
        return seed
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    return seed
