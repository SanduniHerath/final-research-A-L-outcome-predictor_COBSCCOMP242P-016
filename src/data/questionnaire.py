"""Psychometric analysis of the Likert items (Phase 1).

Every function takes a DataFrame of numeric item scores (rows = respondents,
columns = items) and returns plain tables, so each step can be tested on its own.
No outcome variable (Z-score, degree) is used anywhere in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from factor_analyzer import FactorAnalyzer, Rotator
from scipy import stats


def reverse_code(items: pd.DataFrame, columns: list[str], low: int, high: int) -> pd.DataFrame:
    """Return a copy with ``columns`` reversed on a ``low``..``high`` scale: x -> low + high - x."""
    result = items.copy()
    for column in columns:
        result[column] = low + high - result[column]
    return result


def correlation_matrix(items: pd.DataFrame, method: str) -> pd.DataFrame:
    """Return the item correlation matrix (``"spearman"`` or ``"pearson"``)."""
    return items.corr(method=method)


def item_statistics(items: pd.DataFrame, low: int, high: int) -> pd.DataFrame:
    """Describe each item: n, missing, mean, SD, median, skew, kurtosis and answer shares.

    Args:
        items: Numeric item scores.
        low: Lowest scale point.
        high: Highest scale point.

    Returns:
        One row per item. ``pct_<k>`` columns hold the share of answers at each point,
        ``max_category_share`` the largest of these.
    """
    rows = []
    for column in items.columns:
        values = items[column].dropna()
        shares = values.value_counts(normalize=True).reindex(range(low, high + 1), fill_value=0)
        rows.append(
            {
                "item": column,
                "n": int(values.size),
                "missing": int(items[column].isna().sum()),
                "mean": values.mean(),
                "sd": values.std(ddof=1),
                "median": values.median(),
                "skew": stats.skew(values, bias=False),
                "kurtosis": stats.kurtosis(values, bias=False),
                **{f"pct_{k}": shares[k] for k in shares.index},
                "max_category_share": shares.max(),
            }
        )
    return pd.DataFrame(rows).set_index("item")


def cronbach_alpha(items: pd.DataFrame) -> float:
    """Return Cronbach's alpha from item variances and the variance of the total score."""
    complete = items.dropna()
    k = complete.shape[1]
    item_var = complete.var(axis=0, ddof=1).sum()
    total_var = complete.sum(axis=1).var(ddof=1)
    return float(k / (k - 1) * (1 - item_var / total_var))


def feldt_interval(alpha: float, n: int, k: int, level: float) -> tuple[float, float]:
    """Return the Feldt (1965) confidence interval for Cronbach's alpha.

    Args:
        alpha: Sample alpha.
        n: Number of respondents.
        k: Number of items.
        level: Confidence level, e.g. 0.95.
    """
    df1, df2 = n - 1, (n - 1) * (k - 1)
    tail = (1 - level) / 2
    lower = 1 - (1 - alpha) * stats.f.ppf(1 - tail, df1, df2)
    upper = 1 - (1 - alpha) * stats.f.ppf(tail, df1, df2)
    return float(lower), float(upper)


def item_total_table(items: pd.DataFrame, method: str) -> pd.DataFrame:
    """Return corrected item-total correlation and alpha-if-item-deleted for each item.

    The corrected item-total correlation correlates an item with the sum of the
    *other* items in the construct, so the item is not correlated with itself.

    Args:
        items: Numeric scores for the items of one construct.
        method: Correlation method for the item-total correlation.
    """
    complete = items.dropna()
    rows = []
    for column in complete.columns:
        rest = complete.drop(columns=column)
        rows.append(
            {
                "item": column,
                "citc": complete[column].corr(rest.sum(axis=1), method=method),
                "alpha_if_deleted": cronbach_alpha(rest),
            }
        )
    return pd.DataFrame(rows).set_index("item")


def kmo_from_corr(corr: pd.DataFrame) -> tuple[float, pd.Series]:
    """Return overall KMO and per-item MSA computed from a correlation matrix (Kaiser, 1974)."""
    r = corr.to_numpy()
    inv = np.linalg.inv(r)
    scale = np.sqrt(np.outer(np.diag(inv), np.diag(inv)))
    partial = -inv / scale
    np.fill_diagonal(partial, 0.0)
    r_off = r.copy()
    np.fill_diagonal(r_off, 0.0)
    r2, p2 = r_off**2, partial**2
    overall = r2.sum() / (r2.sum() + p2.sum())
    per_item = r2.sum(axis=0) / (r2.sum(axis=0) + p2.sum(axis=0))
    return float(overall), pd.Series(per_item, index=corr.columns, name="msa")


def bartlett_from_corr(corr: pd.DataFrame, n: int) -> tuple[float, int, float]:
    """Return Bartlett's test of sphericity (chi-square, df, p) for a correlation matrix."""
    p = corr.shape[0]
    _, logdet = np.linalg.slogdet(corr.to_numpy())
    chi2 = -(n - 1 - (2 * p + 5) / 6) * logdet
    df = p * (p - 1) // 2
    return float(chi2), int(df), float(stats.chi2.sf(chi2, df))


def parallel_analysis(
    items: pd.DataFrame, method: str, iterations: int, percentile: float, seed: int
) -> pd.DataFrame:
    """Compare observed eigenvalues with eigenvalues of random data (Horn, 1965).

    Random data are drawn by shuffling each item column independently, which keeps
    each item's answer distribution but removes the correlations between items.

    Returns:
        One row per factor number with observed and random-percentile eigenvalues and
        ``retain`` = observed > random.
    """
    rng = np.random.default_rng(seed)
    complete = items.dropna().to_numpy()
    observed = np.sort(np.linalg.eigvalsh(correlation_matrix(items.dropna(), method)))[::-1]
    random_eigs = np.empty((iterations, complete.shape[1]))
    for i in range(iterations):
        shuffled = np.column_stack([rng.permutation(col) for col in complete.T])
        corr = pd.DataFrame(shuffled).corr(method=method)
        random_eigs[i] = np.sort(np.linalg.eigvalsh(corr.to_numpy()))[::-1]
    threshold = np.percentile(random_eigs, percentile, axis=0)
    table = pd.DataFrame(
        {
            "factor": np.arange(1, complete.shape[1] + 1),
            "observed_eigenvalue": observed,
            "random_eigenvalue": threshold,
        }
    )
    table["retain"] = table["observed_eigenvalue"] > table["random_eigenvalue"]
    return table


def suggested_factor_count(parallel: pd.DataFrame) -> int:
    """Number of leading factors whose observed eigenvalue beats the random one."""
    count = 0
    for retain in parallel["retain"]:
        if not retain:
            break
        count += 1
    return count


@dataclass
class EfaResult:
    """Pattern loadings, communalities and factor correlations of one EFA solution."""

    loadings: pd.DataFrame
    communalities: pd.Series
    factor_correlations: pd.DataFrame | None
    variance_explained: pd.DataFrame


def principal_axis_factoring(
    corr: np.ndarray, n_factors: int, max_iter: int = 200, tol: float = 1e-6
) -> np.ndarray:
    """Return unrotated loadings from iterated principal axis factoring.

    Starts from squared multiple correlations as communalities (as SPSS does) and
    repeats the eigen-decomposition of the reduced correlation matrix until the
    communalities stop changing.
    """
    communalities = 1 - 1 / np.diag(np.linalg.inv(corr))
    loadings = np.zeros((corr.shape[0], n_factors))
    for _ in range(max_iter):
        reduced = corr.copy()
        np.fill_diagonal(reduced, communalities)
        values, vectors = np.linalg.eigh(reduced)
        order = np.argsort(values)[::-1][:n_factors]
        loadings = vectors[:, order] * np.sqrt(np.clip(values[order], 0, None))
        updated = (loadings**2).sum(axis=1)
        if np.max(np.abs(updated - communalities)) < tol:
            break
        communalities = updated
    signs = np.sign(loadings.sum(axis=0))
    return loadings * np.where(signs == 0, 1, signs)


def run_efa(corr: pd.DataFrame, n: int, n_factors: int, method: str, rotation: str) -> EfaResult:
    """Fit an exploratory factor analysis on a correlation matrix.

    Args:
        corr: Item correlation matrix.
        n: Number of respondents (needed by ``factor_analyzer`` methods).
        n_factors: Number of factors to extract.
        method: ``"principal"`` for iterated principal axis factoring (implemented here,
            so it works on a Spearman matrix), otherwise a ``factor_analyzer`` method
            such as ``"minres"``.
        rotation: Rotation name (e.g. ``"oblimin"``); ignored for a one-factor solution.
    """
    names = [f"F{i + 1}" for i in range(n_factors)]
    if method == "principal":
        unrotated = principal_axis_factoring(corr.to_numpy(), n_factors)
    else:
        fa = FactorAnalyzer(n_factors=n_factors, method=method, rotation=None, is_corr_matrix=True)
        fa.fit(corr.to_numpy())
        unrotated = fa.loadings_
    phi = None
    if n_factors > 1 and rotation not in (None, "none"):
        rotator = Rotator(method=rotation)
        rotated = rotator.fit_transform(unrotated)
        phi = getattr(rotator, "phi_", None)
    else:
        rotated = unrotated
    flip = np.where(rotated.sum(axis=0) < 0, -1, 1)
    rotated = rotated * flip
    loadings = pd.DataFrame(rotated, index=corr.columns, columns=names)
    factor_corr = None
    if phi is not None:
        factor_corr = pd.DataFrame(phi * np.outer(flip, flip), index=names, columns=names)
    ss = (unrotated**2).sum(axis=0)
    proportion = ss / corr.shape[0]
    variance = pd.DataFrame(
        [ss, proportion, np.cumsum(proportion)],
        index=["ss_loadings_extracted", "proportion", "cumulative"],
        columns=names,
    )
    return EfaResult(
        loadings=loadings,
        communalities=pd.Series((unrotated**2).sum(axis=1), index=corr.columns, name="communality"),
        factor_correlations=factor_corr,
        variance_explained=variance,
    )


def align_factors(loadings: pd.DataFrame, constructs: dict[str, list[str]]) -> dict[str, str]:
    """Map each construct to the factor on which its items load most strongly on average.

    Returns:
        ``{construct: factor_name}``. Two constructs may map to the same factor, which
        itself is a finding (the items do not separate).
    """
    return {
        construct: loadings.loc[items].abs().mean().idxmax()
        for construct, items in constructs.items()
    }


def one_factor_loadings(corr: pd.DataFrame, n: int, method: str) -> pd.Series:
    """Return standardised loadings of a one-factor model for one construct's items."""
    result = run_efa(corr, n, 1, method, rotation="none")
    loadings = result.loadings["F1"]
    return loadings if loadings.sum() >= 0 else -loadings


def composite_reliability(loadings: pd.Series) -> float:
    """Return composite reliability (rho_c) from standardised loadings."""
    total = loadings.sum() ** 2
    return float(total / (total + (1 - loadings**2).sum()))


def average_variance_extracted(loadings: pd.Series) -> float:
    """Return AVE, the mean squared standardised loading (Fornell & Larcker, 1981)."""
    return float((loadings**2).mean())


def htmt(corr: pd.DataFrame, constructs: dict[str, list[str]]) -> pd.DataFrame:
    """Return the heterotrait-monotrait ratio matrix (Henseler et al., 2015).

    HTMT = mean between-construct item correlation divided by the geometric mean of
    the two mean within-construct item correlations.
    """
    abs_corr = corr.abs()

    def mono(items: list[str]) -> float:
        block = abs_corr.loc[items, items].to_numpy()
        return float(block[np.triu_indices(len(items), k=1)].mean())

    names = list(constructs)
    table = pd.DataFrame(np.nan, index=names, columns=names)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            hetero = float(abs_corr.loc[constructs[a], constructs[b]].to_numpy().mean())
            value = hetero / np.sqrt(mono(constructs[a]) * mono(constructs[b]))
            table.loc[b, a] = value
    return table


def item_decisions(
    item_total: pd.DataFrame,
    construct_alpha: dict[str, float],
    item_construct: dict[str, str],
    efa_loadings: pd.DataFrame | None,
    factor_of: dict[str, str] | None,
    single_loadings: pd.Series,
    item_stats: pd.DataFrame,
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    """Apply the pre-set rules and recommend keep, revise or drop for every item.

    Rules (thresholds from ``configs/questionnaire.yaml``):

    * **Drop** if any serious problem: corrected item-total correlation below
      ``citc_drop_below``; one-factor loading below ``outer_loading_remove_below``;
      or, in the EFA, the item loads more strongly on another construct's factor.
    * **Revise** if any lesser problem: corrected item-total correlation below
      ``citc_min``; deleting the item raises alpha by more than the tolerance;
      one-factor loading below ``outer_loading_min``; EFA loading on its own factor below
      ``efa_loading_min``; a cross-loading; or more than ``single_category_share_max``
      of answers in one option.
    * **Keep** otherwise.

    Returns:
        One row per item with the measured values, the list of reasons and the decision.
    """
    t = thresholds
    rows = []
    for item, construct in item_construct.items():
        citc = item_total.loc[item, "citc"]
        aid = item_total.loc[item, "alpha_if_deleted"]
        lam = single_loadings[item]
        share = item_stats.loc[item, "max_category_share"]
        serious: list[str] = []
        minor: list[str] = []
        if citc < t["citc_drop_below"]:
            serious.append(f"item-total r = {citc:.2f} < {t['citc_drop_below']}")
        elif citc < t["citc_min"]:
            minor.append(f"item-total r = {citc:.2f} < {t['citc_min']}")
        if aid > construct_alpha[construct] + t["alpha_if_deleted_tolerance"]:
            minor.append(f"alpha rises to {aid:.2f} if deleted")
        if lam < t["outer_loading_remove_below"]:
            serious.append(f"loading = {lam:.2f} < {t['outer_loading_remove_below']}")
        elif lam < t["outer_loading_min"]:
            minor.append(f"loading = {lam:.2f} < {t['outer_loading_min']}")
        own, second = np.nan, np.nan
        if efa_loadings is not None and factor_of is not None:
            row = efa_loadings.loc[item].abs()
            own = row[factor_of[construct]]
            others = row.drop(factor_of[construct])
            second = others.max() if not others.empty else 0.0
            if second > own:
                serious.append(
                    f"loads more on {others.idxmax()} ({second:.2f}) than own ({own:.2f})"
                )
            else:
                if own < t["efa_loading_min"]:
                    minor.append(f"EFA loading = {own:.2f} < {t['efa_loading_min']}")
                if (
                    second >= t["efa_cross_loading_max"]
                    and own - second < t["efa_cross_loading_gap_min"]
                ):
                    minor.append(f"cross-loading {second:.2f}")
        if share > t["single_category_share_max"]:
            minor.append(f"{share:.0%} of answers in one option")
        decision = "Drop" if serious else "Revise" if minor else "Keep"
        rows.append(
            {
                "item": item,
                "construct": construct,
                "citc": citc,
                "alpha_if_deleted": aid,
                "one_factor_loading": lam,
                "efa_own_loading": own,
                "efa_highest_other": second,
                "max_category_share": share,
                "decision": decision,
                "reasons": "; ".join(serious + minor) or "meets all criteria",
            }
        )
    return pd.DataFrame(rows).set_index("item")
