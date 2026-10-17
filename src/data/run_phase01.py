"""Run the Phase 1 questionnaire validation end to end.

    python -m src.data.run_phase01

Order of analysis (as in the Phase 1 document):
1. Pilot file (13 respondents): item statistics, Cronbach's alpha and item-total
   statistics only - too few cases for KMO, Bartlett or factor analysis.
2. Main file (1,015 respondents): item statistics, reliability, KMO and Bartlett,
   parallel analysis, EFA, convergent and discriminant validity estimates, and the
   keep / revise / drop table.
3. SPSS- and SmartPLS-ready exports, and the expert content-validity form.

Only item answers are used. No outcome variable is read, so no information about the
prediction targets enters these decisions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.data import exports
from src.data import questionnaire as q
from src.data.expert_form import main as build_expert_form
from src.data.load import load_raw
from src.utils.config import get_seed, load_config, resolve_path
from src.utils.logging_setup import get_logger
from src.utils.plot_style import CATEGORICAL, INK, LIKERT_5, apply_style, save_figure

logger = get_logger(__name__)


def scored_items(data: pd.DataFrame, cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (raw item scores, scores with negatively worded items reversed)."""
    names = [i for items in cfg["constructs"].values() for i in items]
    raw = data[names].astype(int)
    scale = cfg["likert"]
    return raw, q.reverse_code(raw, cfg["reverse_coded"], scale["scale_min"], scale["scale_max"])


def reliability_tables(
    scored: pd.DataFrame, cfg: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    """Return construct reliability, item-total statistics and alpha per construct."""
    rows, item_rows, alphas = [], [], {}
    t = cfg["thresholds"]
    for construct, items in cfg["constructs"].items():
        block = scored[items]
        alpha = q.cronbach_alpha(block)
        low, high = q.feldt_interval(alpha, len(block), len(items), cfg["feldt_ci_level"])
        alphas[construct] = alpha
        rows.append(
            {
                "construct": construct,
                "items": len(items),
                "n": len(block),
                "alpha": alpha,
                "ci_low": low,
                "ci_high": high,
                "meets_0.70": alpha >= t["cronbach_alpha_min"],
            }
        )
        spearman = q.item_total_table(block, "spearman")
        pearson = q.item_total_table(block, "pearson")["citc"].rename("citc_pearson")
        item_rows.append(spearman.join(pearson).assign(construct=construct))
    return pd.DataFrame(rows).set_index("construct"), pd.concat(item_rows), alphas


def construct_validity(scored: pd.DataFrame, cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.Series]:
    """Return CR and AVE per construct (one-factor loadings) and all item loadings."""
    rows, loadings = [], []
    method = cfg["efa"]["correlation"]
    for construct, items in cfg["constructs"].items():
        corr = q.correlation_matrix(scored[items], method)
        lam = q.one_factor_loadings(corr, len(scored), cfg["efa"]["method"])
        loadings.append(lam)
        rows.append(
            {
                "construct": construct,
                "composite_reliability": q.composite_reliability(lam),
                "ave": q.average_variance_extracted(lam),
                "min_loading": lam.min(),
            }
        )
    return pd.DataFrame(rows).set_index("construct"), pd.concat(loadings)


def plot_likert(raw: pd.DataFrame, labels: dict[str, str], path: Path, n: int) -> None:
    """Diverging stacked bars: disagree to the left of zero, agree to the right, neutral centred."""
    shares = raw.apply(lambda s: s.value_counts(normalize=True).reindex(range(1, 6), fill_value=0))
    shares = shares.T.iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 6.2))
    left = -(shares[1] + shares[2] + shares[3] / 2)
    widest = max(-left.min(), (left + 1).max())
    reach = 25 * int(np.ceil(widest * 100 / 25))
    names = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"]
    for point, colour, name in zip(range(1, 6), LIKERT_5, names, strict=True):
        ax.barh(
            range(len(shares)),
            shares[point] * 100,
            left=left * 100,
            color=colour,
            edgecolor="white",
            linewidth=1.5,
            height=0.7,
            label=name,
        )
        left = left + shares[point]
    ax.set_yticks(range(len(shares)))
    ax.set_yticklabels([f"{i}  {labels[i]}" for i in shares.index], fontsize=8.5)
    ax.axvline(0, color=INK["muted"], linewidth=0.8)
    ax.set_xlabel("Share of respondents (%), centred on the neutral answer")
    ticks = range(-reach, reach + 1, 25)
    ax.set_xlim(-reach, reach)
    ax.set_xticks(list(ticks))
    ax.set_xticklabels([f"{abs(x)}" for x in ticks])
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Answers to the 12 Likert items (main survey, n = {n})", loc="left")
    ax.legend(ncol=5, loc="upper left", bbox_to_anchor=(0, -0.09), handlelength=1.2)
    ax.text(
        0,
        -0.2,
        "er4 is shown as answered (negatively worded: agreeing means weaker effort regulation).",
        transform=ax.transAxes,
        fontsize=8,
        color=INK["secondary"],
    )
    save_figure(fig, path)


def plot_parallel(parallel: pd.DataFrame, path: Path) -> None:
    """Scree plot of observed eigenvalues against the 95th percentile of random eigenvalues."""
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(
        parallel["factor"],
        parallel["observed_eigenvalue"],
        color=CATEGORICAL[0],
        linewidth=2,
        marker="o",
        markersize=6,
        label="Observed data",
    )
    ax.plot(
        parallel["factor"],
        parallel["random_eigenvalue"],
        color=CATEGORICAL[1],
        linewidth=2,
        linestyle="--",
        marker="s",
        markersize=5,
        label="Random data (95th percentile)",
    )
    ax.axhline(1, color=INK["muted"], linewidth=0.8, linestyle=":")
    ax.text(
        parallel["factor"].max(),
        1.03,
        "eigenvalue = 1",
        ha="right",
        fontsize=8,
        color=INK["muted"],
    )
    ax.set_xticks(parallel["factor"])
    ax.set_xlabel("Factor number")
    ax.set_ylabel("Eigenvalue")
    ax.set_title("Scree plot with parallel analysis (main survey)", loc="left")
    ax.legend(loc="upper right")
    save_figure(fig, path)


def plot_correlations(corr: pd.DataFrame, path: Path) -> None:
    """Heatmap of Spearman correlations between the (reverse-coded) items."""
    fig, ax = plt.subplots(figsize=(7.2, 6.2))
    image = ax.imshow(corr.to_numpy(), cmap="RdBu", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr)))
    ax.set_yticklabels(corr.index)
    ax.grid(False)
    for i in range(len(corr)):
        for j in range(len(corr)):
            value = corr.iat[i, j]
            ax.text(
                j,
                i,
                f"{value:.2f}",
                ha="center",
                va="center",
                fontsize=7,
                color="white" if abs(value) > 0.6 else INK["primary"],
            )
    for edge in (3.5, 7.5):
        ax.axhline(edge, color=INK["primary"], linewidth=1)
        ax.axvline(edge, color=INK["primary"], linewidth=1)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04, label="Spearman correlation")
    ax.set_title("Item correlations (main survey, er4 reverse-coded)", loc="left")
    save_figure(fig, path)


def analyse_pilot(cfg: dict[str, Any], out: Path) -> dict[str, Any]:
    """Pilot: descriptive item statistics and reliability only."""
    data = load_raw("pilot")
    raw, scored = scored_items(data, cfg)
    scale = cfg["likert"]
    q.item_statistics(raw, scale["scale_min"], scale["scale_max"]).to_csv(
        out / "item_stats_pilot.csv"
    )
    reliability, item_total, _ = reliability_tables(scored, cfg)
    reliability.to_csv(out / "reliability_pilot.csv")
    item_total.to_csv(out / "item_total_pilot.csv")
    logger.info("Pilot reliability:\n%s", reliability.round(3))
    return {"n": len(data), "reliability": reliability.round(4).reset_index().to_dict("records")}


def analyse_main(cfg: dict[str, Any], out: Path, figures: Path) -> dict[str, Any]:
    """Main survey: full item analysis, factor analysis and validity estimates."""
    data = load_raw("survey")
    raw, scored = scored_items(data, cfg)
    scale, t, efa_cfg = cfg["likert"], cfg["thresholds"], cfg["efa"]
    n = len(scored)
    stats = q.item_statistics(raw, scale["scale_min"], scale["scale_max"])
    stats.to_csv(out / "item_stats_main.csv")
    reliability, item_total, alphas = reliability_tables(scored, cfg)
    reliability.to_csv(out / "reliability_main.csv")
    item_total.to_csv(out / "item_total_main.csv")

    corr = q.correlation_matrix(scored, efa_cfg["correlation"])
    corr.to_csv(out / "item_correlations_spearman_main.csv")
    kmo, msa = q.kmo_from_corr(corr)
    chi2, df, p = q.bartlett_from_corr(corr, n)
    msa.to_csv(out / "kmo_msa_per_item_main.csv")
    parallel = q.parallel_analysis(
        scored,
        efa_cfg["correlation"],
        efa_cfg["parallel_analysis_iterations"],
        efa_cfg["parallel_analysis_percentile"],
        get_seed(),
    )
    parallel.to_csv(out / "parallel_analysis_main.csv", index=False)
    suggested = q.suggested_factor_count(parallel)
    theory = len(cfg["constructs"])

    efa = q.run_efa(corr, n, theory, efa_cfg["method"], efa_cfg["rotation"])
    efa.loadings.join(efa.communalities).to_csv(out / f"efa_loadings_{theory}factor_main.csv")
    efa.variance_explained.to_csv(out / f"efa_variance_{theory}factor_main.csv")
    if efa.factor_correlations is not None:
        efa.factor_correlations.to_csv(out / f"efa_factor_correlations_{theory}factor_main.csv")
    factor_of = q.align_factors(efa.loadings, cfg["constructs"])
    if suggested not in (0, theory):
        alt = q.run_efa(corr, n, suggested, efa_cfg["method"], efa_cfg["rotation"])
        alt.loadings.join(alt.communalities).to_csv(
            out / f"efa_loadings_{suggested}factor_main.csv"
        )

    validity, loadings = construct_validity(scored, cfg)
    validity.to_csv(out / "convergent_validity_main.csv")
    htmt_s = q.htmt(corr, cfg["constructs"])
    htmt_p = q.htmt(q.correlation_matrix(scored, "pearson"), cfg["constructs"])
    htmt_s.to_csv(out / "htmt_spearman_main.csv")
    htmt_p.to_csv(out / "htmt_pearson_main.csv")

    item_construct = {i: c for c, items in cfg["constructs"].items() for i in items}
    decisions = q.item_decisions(
        item_total, alphas, item_construct, efa.loadings, factor_of, loadings, stats, t
    )
    decisions.to_csv(out / "item_decisions_main.csv")

    singles = q.item_statistics(
        data[cfg["single_item_ratings"]].astype(int), scale["scale_min"], scale["scale_max"]
    )
    singles.to_csv(out / "single_item_ratings_main.csv")

    labels = {
        c["name"]: c["label"]
        for c in load_config("columns")["columns"]
        if c["name"] in item_construct
    }
    short = {k: (v if len(v) <= 62 else v[:59] + "...") for k, v in labels.items()}
    plot_likert(raw, short, figures / "phase01_likert_distribution.png", n)
    plot_parallel(parallel, figures / "phase01_scree_parallel.png")
    plot_correlations(corr, figures / "phase01_item_correlations.png")

    return {
        "n": n,
        "kmo": kmo,
        "msa_min": float(msa.min()),
        "bartlett": {"chi2": chi2, "df": df, "p": p},
        "parallel_suggested_factors": suggested,
        "theory_factors": theory,
        "factor_of_construct": factor_of,
        "variance_explained_cumulative": float(efa.variance_explained.loc["cumulative"].iloc[-1]),
        "decisions": decisions["decision"].value_counts().to_dict(),
    }


def write_exports(cfg: dict[str, Any]) -> list[str]:
    """Write SPSS and SmartPLS files for the main and pilot data."""
    out = resolve_path(load_config("project")["paths"]["processed"]) / "phase01_exports"
    likert = [i for items in cfg["constructs"].values() for i in items]
    ratings = cfg["single_item_ratings"]
    reverse = cfg["reverse_coded"]
    written = []
    dictionary = exports.spss_dictionary(likert, ratings)
    written.append(exports.write_csv(dictionary, out / "spss_data_dictionary.csv"))
    smartpls_constructs = {
        c: [f"{i}_r" if i in reverse else i for i in items]
        for c, items in cfg["constructs"].items()
    }
    for key, suffix in (("survey", "main"), ("pilot", "pilot")):
        data = load_raw(key)
        csv_name = f"spss_{suffix}.csv"
        written.append(exports.write_csv(exports.spss_frame(data, likert, ratings), out / csv_name))
        syntax = exports.spss_syntax(
            csv_name, dictionary, cfg["constructs"], reverse, len(cfg["constructs"])
        )
        syntax_path = out / f"spss_syntax_{suffix}.sps"
        syntax_path.write_text(syntax, encoding="utf-8")
        written.append(syntax_path)
        _, scored = scored_items(data, cfg)
        scored = scored.rename(columns={i: f"{i}_r" for i in reverse})
        written.append(
            exports.write_csv(
                exports.smartpls_frame(scored, smartpls_constructs), out / f"smartpls_{suffix}.csv"
            )
        )
    return [Path(p).name for p in written]


def main() -> int:
    """Run all Phase 1 analyses and write tables, figures, exports and the expert form."""
    cfg = load_config("questionnaire")
    cfg["construct_info"] = cfg["constructs"]
    cfg["constructs"] = {name: info["items"] for name, info in cfg["construct_info"].items()}
    paths = load_config("project")["paths"]
    out = resolve_path(paths["reports"]) / "phase01"
    figures = resolve_path(paths["figures"])
    out.mkdir(parents=True, exist_ok=True)
    apply_style()
    np.set_printoptions(precision=3)
    summary = {"pilot": analyse_pilot(cfg, out), "main": analyse_main(cfg, out, figures)}
    summary["exports"] = write_exports(cfg)
    build_expert_form()
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, default=float), encoding="utf-8"
    )
    logger.info("Phase 1 complete. Tables in %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
