"""Content validity indices from expert ratings (Phase 1).

Each expert returns the rating workbook made by ``src.data.expert_form``. Ratings are
on a 1-4 scale for relevance, clarity and simplicity. A rating of 3 or 4 counts as
agreement. Formulas follow Lynn (1986), Polit & Beck (2006) and Polit, Beck & Owen (2007).

Run after the workbooks come back:

    python -m src.data.cvi docs/returned/expert1.xlsx [docs/returned/expert2.xlsx ...]
"""

from __future__ import annotations

import argparse
import sys
from math import comb
from pathlib import Path

import pandas as pd

from src.utils.config import load_config, resolve_path
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)

DIMENSIONS = ["relevance", "clarity", "simplicity"]
RATINGS_SHEET = "Ratings"


def read_ratings(path: Path) -> pd.DataFrame:
    """Read one expert's workbook and return ``no`` plus the three rating columns.

    Raises:
        ValueError: If a rating is missing or outside 1-4.
    """
    sheet = pd.read_excel(path, sheet_name=RATINGS_SHEET, header=0)
    sheet.columns = [str(c).strip().lower() for c in sheet.columns]
    frame = sheet[["no", *DIMENSIONS]].copy()
    bad = frame[DIMENSIONS].isna() | ~frame[DIMENSIONS].isin([1, 2, 3, 4])
    if bad.to_numpy().any():
        rows = frame.loc[bad.any(axis=1), "no"].tolist()
        raise ValueError(f"{path.name}: missing or invalid ratings for question(s) {rows}")
    return frame.astype(int)


def item_cvi(ratings: list[pd.DataFrame], relevant: list[int]) -> pd.DataFrame:
    """Return I-CVI and modified kappa per question and dimension.

    Args:
        ratings: One DataFrame per expert, as returned by :func:`read_ratings`.
        relevant: Rating values that count as agreement (normally ``[3, 4]``).

    Returns:
        One row per question with ``<dim>_icvi`` and ``<dim>_kappa`` columns.
    """
    n_experts = len(ratings)
    stacked = pd.concat(
        [r.set_index("no")[DIMENSIONS].isin(relevant) for r in ratings],
        axis=1,
        keys=range(n_experts),
    )
    table = pd.DataFrame(index=ratings[0]["no"])
    for dim in DIMENSIONS:
        agree = stacked.xs(dim, axis=1, level=1).sum(axis=1)
        icvi = agree / n_experts
        chance = agree.apply(lambda a: comb(n_experts, int(a)) * 0.5**n_experts)
        table[f"{dim}_agree"] = agree
        table[f"{dim}_icvi"] = icvi
        table[f"{dim}_kappa"] = (icvi - chance) / (1 - chance)
    return table


def scale_cvi(items: pd.DataFrame) -> pd.DataFrame:
    """Return S-CVI/Ave (mean I-CVI) and S-CVI/UA (share of items with I-CVI = 1) per dimension."""
    rows = [
        {
            "dimension": dim,
            "s_cvi_ave": items[f"{dim}_icvi"].mean(),
            "s_cvi_ua": (items[f"{dim}_icvi"] == 1).mean(),
        }
        for dim in DIMENSIONS
    ]
    return pd.DataFrame(rows).set_index("dimension")


def icvi_threshold(n_experts: int, cfg: dict) -> float:
    """Return the minimum acceptable I-CVI for the number of experts (Lynn, 1986)."""
    if n_experts <= 5:
        return cfg["i_cvi_min_up_to_5_experts"]
    return cfg["i_cvi_min_6_plus_experts"]


def main() -> int:
    """Compute CVI tables from returned expert workbooks and save them to ``reports/phase01``."""
    parser = argparse.ArgumentParser(description="Compute content validity indices.")
    parser.add_argument("workbooks", nargs="+", type=Path)
    args = parser.parse_args()
    cfg = load_config("questionnaire")["content_validity"]
    ratings = [read_ratings(p) for p in args.workbooks]
    n = len(ratings)
    if n < cfg["min_recommended_experts"]:
        logger.warning(
            "Only %d expert(s); Lynn (1986) recommends at least %d. With one expert each "
            "I-CVI is either 0 or 1 and modified kappa cannot separate agreement from chance.",
            n,
            cfg["min_recommended_experts"],
        )
    items = item_cvi(ratings, cfg["relevant_ratings"])
    threshold = icvi_threshold(n, cfg)
    items["meets_threshold"] = (items[[f"{d}_icvi" for d in DIMENSIONS]] >= threshold).all(axis=1)
    out_dir = resolve_path(load_config("project")["paths"]["reports"]) / "phase01"
    out_dir.mkdir(parents=True, exist_ok=True)
    items.to_csv(out_dir / "cvi_items.csv")
    scale_cvi(items).to_csv(out_dir / "cvi_scale.csv")
    logger.info("I-CVI threshold for %d expert(s): %.2f", n, threshold)
    logger.info("Saved cvi_items.csv and cvi_scale.csv to %s", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
