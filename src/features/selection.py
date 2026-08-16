"""Training-only association and redundancy checks for feature selection (Phase 4).

The measure follows the data types (project correlation rules):

* ordinal / numeric feature vs Z-score: Spearman rho
* 0/1 feature vs Z-score: point-biserial r
* nominal feature vs Z-score, or numeric / ordinal feature vs a class target:
  Kruskal-Wallis H with epsilon-squared effect size
* 0/1 or nominal feature vs a class target: Cramer's V (chi-square test)

P-values are corrected for multiple testing with Benjamini-Hochberg. These are
associations in the training sample only; they say nothing about cause.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests


def cramers_v(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    """Return Cramer's V and the chi-square p-value for two categorical variables."""
    table = pd.crosstab(x, y)
    if min(table.shape) < 2:
        return 0.0, 1.0
    chi2, p, _, _ = stats.chi2_contingency(table, correction=False)
    n = table.to_numpy().sum()
    v = np.sqrt(chi2 / (n * (min(table.shape) - 1)))
    return float(v), float(p)


def epsilon_squared(values: pd.Series, groups: pd.Series) -> tuple[float, float]:
    """Return Kruskal-Wallis epsilon-squared and p-value (values compared across groups)."""
    samples = [values[groups == g].dropna() for g in groups.dropna().unique()]
    samples = [s for s in samples if len(s) > 0]
    if len(samples) < 2:
        return 0.0, 1.0
    h, p = stats.kruskal(*samples)
    n, k = sum(len(s) for s in samples), len(samples)
    return float(max((h - k + 1) / (n - k), 0.0)), float(p)


def association(
    feature: pd.Series, target: pd.Series, feature_kind: str, target_kind: str
) -> tuple[str, float, float]:
    """Return (measure name, effect size, p-value) for one feature-target pair."""
    if target_kind == "numeric":
        if feature_kind == "binary":
            r, p = stats.pointbiserialr(feature, target)
            return "point_biserial", float(r), float(p)
        if feature_kind == "nominal":
            e, p = epsilon_squared(target, feature)
            return "epsilon_squared", e, p
        rho, p = stats.spearmanr(feature, target)
        return "spearman", float(rho), float(p)
    if feature_kind in ("binary", "nominal"):
        v, p = cramers_v(feature, target)
        return "cramers_v", v, p
    e, p = epsilon_squared(feature, target)
    return "epsilon_squared", e, p


def relevance_table(
    features: pd.DataFrame,
    kinds: dict[str, str],
    targets: pd.DataFrame,
    target_kinds: dict[str, str],
    alpha: float,
) -> pd.DataFrame:
    """Return every feature-target association with BH-adjusted p-values (training data)."""
    rows = []
    for target, t_kind in target_kinds.items():
        for feature, f_kind in kinds.items():
            measure, effect, p = association(features[feature], targets[target], f_kind, t_kind)
            rows.append(
                {
                    "feature": feature,
                    "kind": f_kind,
                    "target": target,
                    "measure": measure,
                    "effect": effect,
                    "abs_effect": abs(effect),
                    "p": p,
                }
            )
    table = pd.DataFrame(rows)
    table["p_bh"] = multipletests(table["p"].fillna(1.0), method="fdr_bh")[1]
    table["significant"] = table["p_bh"] < alpha
    return table


def redundancy_table(numeric: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """Return pairs of numeric / ordinal features whose |Spearman rho| exceeds the threshold."""
    corr = numeric.corr(method="spearman")
    rows = [
        {"feature_a": a, "feature_b": b, "spearman": corr.loc[a, b]}
        for a, b in combinations(corr.columns, 2)
        if abs(corr.loc[a, b]) > threshold
    ]
    return pd.DataFrame(rows, columns=["feature_a", "feature_b", "spearman"])


def redundant_to_drop(pairs: pd.DataFrame, order: list[str]) -> list[str]:
    """For each redundant pair, drop the feature that comes later in ``order``.

    ``order`` lists preferred features first (e.g. composites before their items), so
    the more interpretable summary is kept. Pairs are settled starting with the most
    preferred feature, so a feature is only dropped in favour of one that is kept: if
    the would-be keeper has already been dropped, the pair is skipped.
    """
    rank = {name: i for i, name in enumerate(order)}

    def ordered(row: tuple[str, str]) -> tuple[str, str]:
        a, b = row
        return (a, b) if rank.get(a, 1e9) <= rank.get(b, 1e9) else (b, a)

    settled = sorted(
        (ordered((r.feature_a, r.feature_b)) for r in pairs.itertuples()),
        key=lambda kb: (rank.get(kb[0], 1e9), rank.get(kb[1], 1e9)),
    )
    drop: set[str] = set()
    for keep, other in settled:
        if keep in drop or other in drop:
            continue
        drop.add(other)
    return sorted(drop)
