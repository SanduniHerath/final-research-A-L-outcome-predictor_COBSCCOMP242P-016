"""Project and dataset statistics for the Statistics page (Phase 10).

Everything is an aggregate: counts per group, histogram bins and saved evaluation results. No
single respondent can be seen. Groups with fewer than ``MIN_COUNT`` people are shown as "fewer than
10" so that small groups cannot point to a person.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.split import modelling_rows
from src.utils.config import load_config, resolve_path

MIN_COUNT = 10
CI = re.compile(r"^\s*(-?[\d.]+)\s*\[(-?[\d.]+),\s*(-?[\d.]+)\]")
ARCHITECTURES = ["MLP", "Wide & Deep", "TabNet", "Multi-task", "Entity-embedding MLP",
                 "Autoencoder + MLP", "ResNet-style", "Regularised DNN"]  # fmt: skip


def _reports() -> Path:
    return resolve_path(load_config("project")["paths"]["reports"])


def parse_ci(text: str) -> dict[str, float]:
    """'0.205 [0.180, 0.232]' -> {'value': 0.205, 'low': 0.18, 'high': 0.232}."""
    match = CI.match(str(text))
    if not match:
        return {"value": float(text), "low": None, "high": None}
    value, low, high = (float(g) for g in match.groups())
    return {"value": value, "low": low, "high": high}


def counts(series: pd.Series, order: list[str] | None = None) -> list[dict[str, Any]]:
    """Counts per group; small groups are hidden."""
    table = series.astype(str).value_counts()
    keys = order or list(table.index)
    out = []
    for key in keys:
        n = int(table.get(key, 0))
        out.append({"label": key, "count": n if n >= MIN_COUNT else None, "small": n < MIN_COUNT})
    return out


def dataset_stats() -> dict[str, Any]:
    """Who is in the survey (modelling rows), as aggregates."""
    rows = modelling_rows()
    # 0.25-wide bins; the top bin is wider so that it never holds only a few people.
    edges = np.array([0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.75])
    hist, _ = np.histogram(rows["zscore"].clip(edges[0], edges[-1] - 1e-9), bins=edges)
    labels = load_config("labels")["targets"]
    split = pd.read_csv(resolve_path(load_config("split")["files"]["split"]))
    reached = rows["goal_status"].dropna()
    return {
        "respondents": int(len(rows)),
        "splits": split["split"].value_counts().to_dict(),
        "zscore": {
            "bins": [
                {"from": round(float(a), 2), "to": round(float(b), 2), "count": int(c)}
                for a, b, c in zip(edges[:-1], edges[1:], hist, strict=True)
            ],  # fmt: skip
            "median": round(float(rows["zscore"].median()), 2),
            "lowest": round(float(rows["zscore"].min()), 2),
            "highest": round(float(rows["zscore"].max()), 2),
        },
        "degree_category": counts(
            rows["degree_category"], list(labels["degree_category"]["groups"])
        ),
        "university_group": counts(
            rows["university_group"], list(labels["university_group"]["groups"])
        ),
        "subject_combination": counts(rows["al_subject_combination"]),
        "exam_year": counts(
            rows["al_exam_year"], sorted(rows["al_exam_year"].astype(str).unique())
        ),
        "reached_target_share": round(float((reached == "reached").mean()), 3),
        "with_target": int(len(reached)),
    }


def questionnaire_stats() -> list[dict[str, Any]]:
    """Cronbach's alpha of the three attitude scales (Phase 1)."""
    table = pd.read_csv(_reports() / "phase01" / "reliability_main.csv")
    return [
        {
            "construct": r["construct"],
            "items": int(r["items"]),
            "alpha": round(float(r["alpha"]), 3),
        }
        for _, r in table.iterrows()
    ]


def model_stats() -> dict[str, Any]:
    """Phase 7 test results of the chosen system against the simple baseline, and all models."""
    p7 = _reports() / "phase07"
    out: dict[str, Any] = {
        "test_students": json.loads((p7 / "summary.json").read_text("utf-8"))["rows"]
    }
    z = pd.read_csv(p7 / "results_zscore.csv").set_index("system")
    out["zscore"] = {
        "chosen": {m: parse_ci(z.loc["Chosen system", m]) for m in ("mae", "r2", "spearman")},
        "baseline": {m: parse_ci(z.loc["Trivial baseline", m]) for m in ("mae", "r2", "spearman")},
        "all_models_mae": [{"model": a, **parse_ci(z.loc[a, "mae"])} for a in ARCHITECTURES],
    }
    p8 = json.loads((_reports() / "phase08" / "summary.json").read_text("utf-8"))
    out["zscore"]["within_0_4"] = round(p8["zscore_residuals_test"]["share_within_0_4"], 3)
    out["zscore"]["within_0_2"] = round(p8["zscore_residuals_test"]["share_within_0_2"], 3)
    for task in ("zscore_band", "degree_category", "university_group"):
        t = pd.read_csv(p7 / f"results_{task}.csv").set_index("system")
        out[task] = {
            "chosen": {
                m: parse_ci(t.loc["Chosen system", m]) for m in ("macro_f1", "accuracy", "ece")
            },
            "baseline": {
                m: parse_ci(t.loc["Trivial baseline", m]) for m in ("macro_f1", "accuracy")
            },
            "all_models_f1": [
                {"model": a, **parse_ci(t.loc[a, "macro_f1"])} for a in ARCHITECTURES
            ],
        }
    return out


def hypotheses() -> list[dict[str, str]]:
    """Status of every hypothesis after Phase 9."""
    p7 = pd.read_csv(_reports() / "phase07" / "hypotheses.csv")
    out = [{"id": r["hypothesis"], "result": r["result"]} for _, r in p7.iterrows()]
    p8 = json.loads((_reports() / "phase08" / "summary.json").read_text("utf-8"))["h7_supported"]
    supported = sorted({g for groups in p8.values() for g in groups})
    out.append({"id": "H7", "result": "Supported for: " + ", ".join(supported)})
    h8 = json.loads((_reports() / "phase09" / "h8_test.json").read_text("utf-8"))
    out.append({"id": "H8", "result": "Supported" if h8["supported"] else "Not supported"})
    out.append({"id": "H9", "result": "Pending (expert and user test)"})
    xai = json.loads((_reports() / "phase09" / "xai_summary_validation.json").read_text("utf-8"))
    out.append({"id": "H10", "result": f"Automated checks: additivity met; stability met for Z-score, "
                f"{round(xai['degree_category']['share_at_least_threshold'] * 100)} % for degree area. "
                "Comprehension pending (user test)"})  # fmt: skip
    chat = json.loads((_reports() / "phase09" / "chatbot_summary_run3.json").read_text("utf-8"))
    main = chat[load_config("app")["chatbot"]["model"]]
    met = main["unsupported_says_unsure"] >= 0.9
    out.append({"id": "H11", "result": "Supported" if met else "Not supported (3 of 4 checks met)"})
    out.append({"id": "H12", "result": "Pending (user test)"})
    order = {f"H{i}": i for i in range(1, 13)}
    return sorted(out, key=lambda h: order[h["id"]])


@lru_cache(maxsize=1)
def project_statistics() -> dict[str, Any]:
    """Everything the Statistics page shows."""
    chat = json.loads((_reports() / "phase09" / "chatbot_summary_run3.json").read_text("utf-8"))
    main = chat[load_config("app")["chatbot"]["model"]]
    rec = json.loads((_reports() / "phase09" / "recommend_summary_test.json").read_text("utf-8"))
    return {
        "dataset": dataset_stats(),
        "questionnaire": questionnaire_stats(),
        "model": model_stats(),
        "hypotheses": hypotheses(),
        "parts": {
            "chatbot": {
                "prompts": main["prompts"],
                "invented_numbers": main["replies_with_invented_numbers"],
                "refusal": main["out_of_scope_refusal"],
                "unsure": main["unsupported_says_unsure"],
                "max_seconds": main["max_seconds_model_replies"],
            },
            "recommendation": {
                "reason_and_evidence": rec["share_recs_with_reason_and_evidence"],
                "similar_closer_than_random": rec["similar_closer_than_random"],
            },
        },
    }


__all__ = ["parse_ci", "project_statistics"]
