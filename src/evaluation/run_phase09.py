"""Phase 9 - checks of the five system parts.

    python -m src.evaluation.run_phase09 cutoffs      # extract + summarise the UGC tables
    python -m src.evaluation.run_phase09 examples     # strong / average / weak profiles, all parts
    python -m src.evaluation.run_phase09 xai          # H10 automated checks (validation)
    python -m src.evaluation.run_phase09 recommend    # recommendation automated checks (validation)
    python -m src.evaluation.run_phase09 h8-dryrun    # H8 on VALIDATION (checks the code only)
    python -m src.evaluation.run_phase09 test-checks  # pre-registered test-set checks, run ONCE
    python -m src.evaluation.run_phase09 chatbot [chatbot_tests_run2] [--no-guard]
                                                      # H11: 30 scripted prompts, both local models

The test-set checks are the ones fixed in Phase 2 (H8 and "similar profiles closer than random").
They read the test answers again, after Phase 7, without changing any model, rule or threshold;
the access is recorded in reports/phase09/test_access.json and the step refuses to run twice.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score

from src.chatbot.bot import Chatbot
from src.chatbot.facts import build_fact_sheet
from src.chatbot.guard import REPLIES, unsupported_numbers
from src.chatbot.llm import OllamaModel
from src.data.split import TEST_UNLOCK_WORD, ids_digest, load_split_rows
from src.evaluation.bootstrap import bootstrap_ci
from src.evaluation.criteria import require_locked
from src.gap.analysis import GapAnalyzer
from src.gap.ugc_cutoffs import main as extract_cutoffs
from src.models import student
from src.system import DecisionSupportSystem
from src.utils.config import get_seed, load_config, resolve_path
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)
PATHS = load_config("project")["paths"]
OUT = resolve_path(PATHS["reports"]) / "phase09"
PROCESSED = resolve_path(PATHS["processed"])
ACCESS_FILE = OUT / "test_access.json"
UNSURE_WORDS = ("not sure", "don't know", "do not know", "cannot tell", "can't tell")


def write_json(name: str, data: object) -> None:
    """Save JSON in reports/phase09."""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str), "utf-8")


# ---- UGC cut-offs ------------------------------------------------------------------------------
def cutoffs_step() -> None:
    """Extract the tables and summarise coverage of the courses used by the gap analysis."""
    extract_cutoffs()
    gap = GapAnalyzer.load()
    table = gap.cutoffs
    summary = (
        table.groupby(["academic_year", "source_file"])
        .agg(
            courses=("column", lambda s: s.groupby(table.loc[s.index, "page"]).nunique().sum()),
            cells=("min_z", "size"),
            nqc_cells=("min_z", lambda s: int(s.isna().sum())),
        )  # fmt: skip
        .reset_index()
    )
    summary.to_csv(OUT / "ugc_cutoffs_summary.csv", index=False)
    rows = []
    for category, names in gap.cfg["category_courses"].items():
        for year in sorted(table["academic_year"].unique()):
            part = table[(table["academic_year"] == year) & table["course_name"].isin(names)]
            rows.append(
                {
                    "category": category,
                    "year": year,
                    "course_columns": int(part.groupby(["page", "column"]).ngroups),
                    "names_found": int(part["course_name"].nunique()),
                    "names_listed": len(names),
                    "median_cutoff": round(float(part["min_z"].median()), 3)
                    if part["min_z"].notna().any()
                    else None,
                }
            )
    pd.DataFrame(rows).to_csv(OUT / "category_course_coverage.csv", index=False)
    logger.info("UGC summary:\n%s", summary.to_string(index=False))


# ---- examples ----------------------------------------------------------------------------------
def examples_step(system: DecisionSupportSystem) -> None:
    """Run the strong / average / weak profiles through all parts and save the outputs."""
    profiles = load_config("example_profiles")
    rows = []
    for name, profile in profiles.items():
        start = time.perf_counter()
        report = system.report(profile)
        seconds = time.perf_counter() - start
        write_json(f"example_{name}.json", {"profile": profile, **report})
        pred, gap, plan = report["prediction"], report["gap"], report["recommendations"]
        rows.append(
            {
                "profile": name,
                "target": profile["al_target_degree"],
                "district": profile["al_district"],
                "predicted_z": pred["zscore"]["predicted"],
                "z_range": f"{pred['zscore']['range_low']:.2f} to {pred['zscore']['range_high']:.2f}",
                "band": pred["zscore_band"]["most_likely"],
                "top_degree": pred["degree_category"]["most_likely"],
                "top_degree_chance": pred["degree_category"]["top_probability"],
                "university_top2": " / ".join(pred["university_group"]["top_k"]),
                "gap_status": gap["status"],
                "gap_points": gap.get("gap_points"),
                "reference_cutoff": round(gap["reference"]["value"], 4)
                if gap.get("reference")
                else None,
                "mode": plan["mode"],
                "n_recommendations": len(plan["recommendations"]),
                "what_if_all": plan["what_if"]["all"],
                "xai_stability": round(report["explanation"]["stability_spearman_top5"], 3),
                "seconds_all_parts": round(seconds, 2),
            }
        )
    pd.DataFrame(rows).to_csv(OUT / "examples_summary.csv", index=False)
    logger.info("Examples:\n%s", pd.DataFrame(rows).to_string(index=False))


# ---- XAI ---------------------------------------------------------------------------------------
def xai_step(system: DecisionSupportSystem, n_rows: int = 40) -> dict[str, Any]:
    """H10 automated part on validation students who were NOT used to choose the setting."""
    val = pd.read_csv(PROCESSED / "features_validation.csv")
    # The first 25 validation rows were used to choose max_evals; check on the next ones.
    rows = val.iloc[25 : 25 + n_rows]
    return stability_table(
        system, rows[system.predictor.system.columns].to_numpy(np.float32), "validation"
    )


def stability_table(system: DecisionSupportSystem, x_all: np.ndarray, label: str) -> dict[str, Any]:
    """Additivity error and top-5 stability for the Z-score and the most likely degree area."""
    explainer = system.explainer
    records = []
    for i, x in enumerate(x_all):
        x = x[None]
        top = int(np.argmax(system.predictor.raw(x)["degree_category"][0]))
        for task, k in (("zscore", None), ("degree_category", top)):
            runs = explainer.shap_runs(x, task, k)
            values = [r.values[0] for r in runs]
            pred = float(explainer.task_function(task, k)(x)[0])
            err = max(abs(r.base_values[0] + r.values[0].sum() - pred) for r in runs)
            records.append(
                {
                    "row": i,
                    "task": task,
                    "stability": explainer.stability(values),
                    "additivity_error": err,
                }
            )
    table = pd.DataFrame(records)
    table.to_csv(OUT / f"xai_stability_{label}.csv", index=False)
    crit = load_config("success_criteria")["xai"]["automated"]
    summary = {}
    for task, part in table.groupby("task"):
        summary[task] = {
            "students": int(len(part)),
            "median_stability": round(float(part["stability"].median()), 3),
            "share_at_least_threshold": round(
                float((part["stability"] >= crit["top5_stability_min_spearman"]).mean()), 3
            ),
            "min_stability": round(float(part["stability"].min()), 3),
            "max_additivity_error": float(part["additivity_error"].max()),
            "additivity_ok": bool(
                part["additivity_error"].max() <= crit["local_additivity_max_abs_error"]
            ),
        }
    write_json(f"xai_summary_{label}.json", summary)
    logger.info("XAI %s: %s", label, summary)
    return summary


# ---- recommendation ----------------------------------------------------------------------------
def profiles_from_rows(rows: pd.DataFrame) -> list[dict[str, Any]]:
    """App answers rebuilt from cleaned survey rows (targets the respondents stated)."""
    return [student.profile_from_survey(r) for _, r in rows.iterrows()]


def recommend_checks(
    system: DecisionSupportSystem, rows: pd.DataFrame, label: str
) -> dict[str, Any]:
    """Reason + evidence on every recommendation, mode follows gap status, closer than random."""
    rng = np.random.default_rng(get_seed())
    records = []
    for profile in profiles_from_rows(rows):
        prediction = system.predict(profile)
        gap = system.gap.analyse(profile, prediction)
        plan = system.recommender.recommend(profile, prediction, gap, None)
        x = system.predictor.features(profile)[0]
        near, rand = system.recommender.distance_check(x, gap.get("target_category"), rng)
        expected = "close_the_gap" if gap["status"] == "gap" else "strengthen"
        records.append(
            {
                "status": gap["status"],
                "mode": plan["mode"],
                "mode_follows_status": plan["mode"] == expected,
                "n_recs": len(plan["recommendations"]),
                "all_have_reason_and_evidence": all(
                    r["reason"] and r["evidence"] for r in plan["recommendations"]
                ),
                "unfilled_placeholder": any(
                    "{" in r["text"] + r["reason"] + r["title"] for r in plan["recommendations"]
                ),
                "distance_similar": near,
                "distance_random": rand,
            }
        )
    table = pd.DataFrame(records)
    table.to_csv(OUT / f"recommend_checks_{label}.csv", index=False)
    diff = (table["distance_random"] - table["distance_similar"]).to_numpy()
    point, low, high = bootstrap_ci(
        diff, diff, lambda a, _b: float(np.mean(a)), n=2000, seed=get_seed()
    )
    summary = {
        "students": int(len(table)),
        "share_recs_with_reason_and_evidence": float(table["all_have_reason_and_evidence"].mean()),
        "share_mode_follows_status": float(table["mode_follows_status"].mean()),
        "any_unfilled_placeholder": bool(table["unfilled_placeholder"].any()),
        "mean_distance_similar": round(float(table["distance_similar"].mean()), 3),
        "mean_distance_random": round(float(table["distance_random"].mean()), 3),
        "mean_difference_ci": [round(point, 3), round(low, 3), round(high, 3)],
        "similar_closer_than_random": bool(low > 0),
        "modes": table["mode"].value_counts().to_dict(),
        "mean_recommendations": round(float(table["n_recs"].mean()), 2),
    }
    write_json(f"recommend_summary_{label}.json", summary)
    logger.info("Recommendation checks %s: %s", label, summary)
    return summary


# ---- H8 ----------------------------------------------------------------------------------------
def h8(system: DecisionSupportSystem, rows: pd.DataFrame, label: str) -> dict[str, Any]:
    """Gap status from the predicted Z-score vs whether the respondent reached their target."""
    pipe, columns = system.predictor.system.pipeline, system.predictor.system.columns
    x = pipe.transform(rows)[columns].to_numpy(np.float32)
    z = system.predictor.raw(x)["zscore"]
    records = []
    for (_, r), zi in zip(rows.iterrows(), z, strict=True):
        status = system.gap.retrospective_status(
            r["al_target_degree"], r["al_district"], r["al_exam_year"], float(zi)
        )
        if status is None or pd.isna(r["goal_status"]):
            continue
        records.append(
            {
                "target": r["target_category"],
                "predicted_z": float(zi),
                "status": status,
                "reached": r["goal_status"] == "reached",
            }
        )
    table = pd.DataFrame(records)
    y = table["reached"].to_numpy(int)
    pred = (table["status"] == "on_track").to_numpy(int)
    point, low, high = bootstrap_ci(y, pred, balanced_accuracy_score, n=2000, seed=get_seed())
    by_target = (
        table.groupby("target")
        .apply(
            lambda g: pd.Series(
                {
                    "n": len(g),
                    "reached": int(g["reached"].sum()),
                    "on_track": int((g["status"] == "on_track").sum()),
                    "on_track_and_reached": int(((g["status"] == "on_track") & g["reached"]).sum()),
                }
            ),
            include_groups=False,
        )  # fmt: skip
        .reset_index()
    )
    by_target.to_csv(OUT / f"h8_by_target_{label}.csv", index=False)
    crosstab = pd.crosstab(table["status"], table["reached"]).to_dict()
    result = {
        "rows_used": int(len(table)),
        "balanced_accuracy": round(point, 3),
        "ci95": [round(low, 3), round(high, 3)],
        "supported": bool(
            low
            > load_config("success_criteria")["gap_analysis"]["retrospective_check"][
                "minimum_ci_lower_above"
            ]
        ),
        "crosstab_status_by_reached": {
            str(k): {str(a): int(b) for a, b in v.items()} for k, v in crosstab.items()
        },
        "share_reached": round(float(y.mean()), 3),
        "share_on_track": round(float(pred.mean()), 3),
    }
    write_json(f"h8_{label}.json", result)
    logger.info("H8 %s: %s", label, result)
    return result


def test_checks(system: DecisionSupportSystem) -> None:
    """The pre-registered test-set checks of Phase 9, run once."""
    if ACCESS_FILE.exists():
        raise RuntimeError(
            f"Phase 9 test checks already ran ({ACCESS_FILE}); results are in reports/phase09."
        )
    rows = load_split_rows("test", unlock_test=TEST_UNLOCK_WORD)
    saved = np.load(PROCESSED / "phase07_test_predictions.npz")
    pipe, columns = system.predictor.system.pipeline, system.predictor.system.columns
    z_now = system.predictor.raw(pipe.transform(rows)[columns].to_numpy(np.float32))["zscore"]
    same = bool(np.allclose(z_now, saved["pred__stage2_zscore_mlp__s0__zscore"], atol=1e-5))
    record = {
        "accessed_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "test_rows": len(rows),
        "test_ids_sha256": ids_digest(rows["respondent_id"]),
        "purpose": "Pre-registered Phase 2 checks of the gap module (H8) and of the recommendation "
        "engine (similar profiles closer than random). No model, rule or threshold was changed.",
        "predictions_identical_to_phase7": same,
    }
    write_json("test_access.json", record)
    h8(system, rows, "test")
    recommend_checks(system, rows, "test")


# ---- chatbot -----------------------------------------------------------------------------------
def score_reply(kind: str, reply: dict[str, Any], facts: str, prompt: str) -> dict[str, Any]:
    """Automatic H11 scores for one reply."""
    text = reply["reply"]
    refused = reply["source"] in ("guard", "out_of_scope") or text in REPLIES.values()
    unsure = any(w in text.lower() for w in UNSURE_WORDS)
    return {
        "invented_numbers": ", ".join(unsupported_numbers(text, facts, prompt)),
        "refused": refused,
        "unsure": unsure,
        "answered": not refused and not unsure,
    }


def chatbot_step(
    system: DecisionSupportSystem, tests_name: str, use_guard: bool = True, label: str | None = None
) -> None:
    """Run the 30 scripted prompts with the main and the fallback model."""
    run = label or tests_name.removeprefix("chatbot_tests").lstrip("_") or "run1"
    tests = load_config(tests_name)
    profile = load_config("example_profiles")[tests["profile"]]
    results = system.report(profile)
    facts = build_fact_sheet(results)
    cfg = load_config("app")["chatbot"]
    prompts = [("supported", p) for p in tests["prompts"]["supported"]]
    prompts += [("unsupported", p) for p in tests["prompts"]["unsupported"]]
    prompts += [
        (f"out_of_scope:{k}", p) for k, v in tests["prompts"]["out_of_scope"].items() for p in v
    ]
    summary = {}
    for name in (cfg["model"], cfg["fallback_model"]):
        model = OllamaModel(
            name, cfg["url"], cfg["temperature"], cfg["max_tokens"], cfg["timeout_seconds"]
        )
        if not model.available():
            logger.warning("Model %s not available; skipped", name)
            continue
        warm = model.warm_up()
        bot = Chatbot(model=model, fallback=None)
        if not use_guard:
            import src.chatbot.bot as bot_module

            bot_module.topic_of = lambda _m: "in_scope"
        rows = []
        for kind, prompt in prompts:
            reply = bot.reply(prompt, results).as_dict()
            rows.append(
                {
                    "model": name,
                    "kind": kind,
                    "prompt": prompt,
                    **reply,
                    **score_reply(kind, reply, facts, prompt),
                }
            )
        table = pd.DataFrame(rows)
        suffix = f"_{run}" + ("" if use_guard else "_no_guard")
        table.to_csv(OUT / f"chatbot_test_{name.replace(':', '_')}{suffix}.csv", index=False)
        oos = table[table["kind"].str.startswith("out_of_scope")]
        uns = table[table["kind"] == "unsupported"]
        sup = table[table["kind"] == "supported"]
        summary[name] = {
            "warm_up_seconds": round(warm, 1),
            "prompts": int(len(table)),
            "replies_with_invented_numbers": int((table["invented_numbers"] != "").sum()),
            "out_of_scope_refusal": round(float(oos["refused"].mean()), 3),
            "out_of_scope_refused_by_guard": int((oos["source"] == "guard").sum()),
            "unsupported_says_unsure": round(float(uns["unsure"].mean()), 3),
            "supported_answered": round(float(sup["answered"].mean()), 3),
            "rewrites_needed": int(table["rewrites"].sum()),
            "number_check_fallbacks": int((table["source"] == "number_check_fallback").sum()),
            "median_seconds": round(float(table["seconds"].median()), 2),
            "max_seconds_model_replies": round(
                float(table.loc[table["source"] != "guard", "seconds"].max()), 2
            ),
            "share_within_10s": round(float((table["seconds"] <= 10).mean()), 3),
        }
        logger.info("Chatbot %s%s: %s", name, suffix, summary[name])
    write_json(f"chatbot_summary_{run}{'' if use_guard else '_no_guard'}.json", summary)


def main(argv: list[str]) -> int:
    """Run one step."""
    require_locked()
    step = argv[0] if argv else "examples"
    OUT.mkdir(parents=True, exist_ok=True)
    if step == "cutoffs":
        cutoffs_step()
        return 0
    system = DecisionSupportSystem.load()
    if step == "examples":
        examples_step(system)
    elif step == "xai":
        xai_step(system)
    elif step == "recommend":
        recommend_checks(system, load_split_rows("validation"), "validation")
    elif step == "h8-dryrun":
        h8(system, load_split_rows("validation"), "validation")
    elif step == "test-checks":
        test_checks(system)
    elif step == "chatbot":
        tests = next((a for a in argv[1:] if a.startswith("chatbot_tests")), "chatbot_tests")
        label = next((a.split("=", 1)[1] for a in argv if a.startswith("--label=")), None)
        chatbot_step(system, tests, use_guard="--no-guard" not in argv, label=label)
    else:
        raise SystemExit(f"Unknown step {step}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
