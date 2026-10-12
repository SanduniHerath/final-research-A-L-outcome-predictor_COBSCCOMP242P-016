"""Build and run the appendix notebooks (notebooks/01-06).

    python notebooks/build_notebooks.py            # write, run, and export HTML + PDF
    python notebooks/build_notebooks.py --no-run   # only write the .ipynb files

The notebooks call the project code in src/ (they do not copy it) and re-run the key steps, so
every output in them comes from a real run. They print only totals, averages and model results:
no respondent's individual answers (respondents are young). The test set is NOT re-opened:
notebook 04 reads the results saved when it was opened once in Phase 7.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

HERE = Path(__file__).resolve().parent
EXPORTS = HERE / "exports"
CHROME = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")

SETUP = """# Setup: work from the project root so the project code and configs are found
import os, sys, json, platform, warnings
from pathlib import Path
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
os.chdir(ROOT); sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from IPython.display import Image, Markdown, display
pd.set_option("display.precision", 3); pd.set_option("display.width", 160); pd.set_option("display.max_columns", 20)
from src.utils.config import load_config, resolve_path
REPORTS = resolve_path(load_config("project")["paths"]["reports"])
FIG = resolve_path(load_config("project")["paths"]["figures"])
print("Project folder:", ROOT)
print("Python", platform.python_version(), "| numpy", np.__version__, "| pandas", pd.__version__)"""


def md(text: str) -> nbformat.NotebookNode:
    return new_markdown_cell(text.strip())


def code(text: str) -> nbformat.NotebookNode:
    return new_code_cell(text.strip())


def header(title: str, purpose: str) -> list[nbformat.NotebookNode]:
    return [
        md(f"# {title}\n\n{purpose}"),
        code(SETUP),
    ]


# ---- 01 data ---------------------------------------------------------------------------------
NB01 = header(
    "01 – Data preparation and the train / validation / test split",
    "Phases 0, 3 and 5: the raw survey file is checked against its recorded checksum, cleaned, "
    "labelled and split once into training, validation and test rows.",
) + [
    md(
        "## 1. The raw file is unchanged\nThe raw files are read-only and their SHA-256 checksums were recorded in Phase 0. "
        "This re-computes them now."
    ),
    code("""from src.data.register_raw import verify
raw_dir = resolve_path(load_config("project")["paths"]["raw"])
manifest = resolve_path("data/raw_checksums.json")
ok = verify(raw_dir, manifest)
print("All raw files match their recorded checksums:", ok)"""),
    md(
        "## 2. Cleaning log (Phase 3)\nEvery change made by the cleaning script is logged. Only the step, the column and the number of rows are shown here."
    ),
    code("""log = pd.read_csv(REPORTS / "phase03" / "cleaning_log.csv")
log[["step", "column", "rows_affected"]]"""),
    md("## 3. Rows used for modelling and the class counts of each target"),
    code("""from src.data.split import modelling_rows
rows = modelling_rows()
print("Modelling rows:", len(rows), "| columns:", rows.shape[1])
counts = pd.read_csv(REPORTS / "phase03" / "class_counts.csv")
counts"""),
    md(
        "## 4. The split (Phase 4/5)\nThe split was made once with the project seed, stratified, and locked with a checksum. "
        "`verify_split` checks the split file against that lock."
    ),
    code("""from src.data.split import verify_split
split = pd.read_csv(resolve_path(load_config("split")["files"]["split"]))
verify_split(split)
print("Split file matches its lock record.")
print(split["split"].value_counts().rename("rows").to_frame())
pd.read_csv(REPORTS / "phase05" / "zscore_by_split.csv").set_index("split")"""),
    md(
        "## 5. The test set is locked\nUntil Phase 7 the code refused to read the test rows without an unlock word. "
        "This shows the lock still works (the test rows are not read here)."
    ),
    code("""from src.data.split import load_split_rows
try:
    load_split_rows("test")
except Exception as error:
    print(type(error).__name__, "->", error)"""),
    md("## 6. Z-score band edges, learned from the training rows only"),
    code("""print(json.loads(resolve_path("data/processed/zscore_band_edges.json").read_text("utf-8")))
display(Image(str(FIG / "phase05_class_balance.png"), width=760))"""),
]

# ---- 02 features -----------------------------------------------------------------------------
NB02 = header(
    "02 – Feature engineering",
    "Phase 4: the feature pipeline is fitted on the training rows only and applied to the validation rows. "
    "This notebook re-fits it and checks that it gives exactly the saved features.",
) + [
    md("## 1. Re-fit the pipeline on the training rows"),
    code("""from src.data.split import load_split_rows
from src.features.build import FeaturePipeline
train, validation = load_split_rows("train"), load_split_rows("validation")
pipe = FeaturePipeline(load_config("features")).fit(train)
x_train, x_val = pipe.transform(train), pipe.transform(validation)
print("Training rows:", x_train.shape, "| validation rows:", x_val.shape)"""),
    md("## 2. Same result as the saved features (used for training)"),
    code("""processed = resolve_path(load_config("project")["paths"]["processed"])
for name, fresh in (("train", x_train), ("validation", x_val)):
    saved = pd.read_csv(processed / f"features_{name}.csv")[fresh.columns]
    diff = np.abs(saved.to_numpy(float) - fresh.to_numpy(float)).max()
    print(f"{name}: largest difference from the saved features = {diff:.2e}")"""),
    md("## 3. Feature sets compared in Phase 6, and the 34 columns finally used"),
    code("""sets = json.loads((REPORTS / "phase04" / "feature_sets.json").read_text("utf-8"))
print("Feature set sizes:", sets["sizes"])
final = json.loads((REPORTS / "phase06" / "final_columns.json").read_text("utf-8"))
print(len(final), "columns used by the final models:")
pd.DataFrame({"column": final})"""),
    md("## 4. How each feature is made (catalogue, first rows)"),
    code("""cat = pd.read_csv(REPORTS / "phase04" / "feature_catalogue.csv")
cat[cat["feature"].isin(final)][["feature", "type", "formula"]].head(15)"""),
    code("""display(Image(str(FIG / "phase04_relevance.png"), width=760))"""),
]

# ---- 03 training -----------------------------------------------------------------------------
NB03 = header(
    "03 – Model training (Phase 6)",
    "Eight neural-network architectures were tuned with the same random search and compared with "
    "cross-validation inside the training rows. This notebook summarises every logged training run and "
    "**re-trains the chosen networks live** to show that the saved results are reproduced exactly.",
) + [
    md("## 1. Training settings"),
    code("""mc = load_config("models")
print("Architectures:", ", ".join(mc["models"]))
print("Budget:", json.dumps(mc["budget"], indent=1))
print("Training:", mc["training"])"""),
    md(
        "## 2. Every training run is logged\n`reports/phase06/runs.jsonl` holds one record per training run (model, settings, fold, seed and scores)."
    ),
    code("""from src.models import cv
log = cv.read_log()
steps = pd.Series([r["step"] for r in log]).value_counts().rename("runs").to_frame()
print("Logged training runs:", len(log))
steps"""),
    md(
        "## 3. Re-run one cross-validation run from the random search\nOne logged search run (first configuration of the MLP, fold `r0f0`) is trained again from scratch and its scores are compared with the log."
    ),
    code("""cache = cv.build_fold_cache()
logged = next(r for r in log if r["step"] == "search" and r["model"] == "mlp" and r["config_id"] == "c00" and r["split"] == "r0f0")
columns = json.loads((REPORTS / "phase06" / "final_columns.json").read_text("utf-8"))
job = cv.make_job("search", "mlp", logged["cfg"], columns, "r0f0", logged["seed"], config_id="c00")
again = cv.evaluate_run(job, cache["r0f0"])
pd.DataFrame({"logged in Phase 6": {t: logged["metrics"][t]["mae" if t == "zscore" else "macro_f1"] for t in logged["metrics"]},
              "re-run now": {t: again["metrics"][t]["mae" if t == "zscore" else "macro_f1"] for t in again["metrics"]}})"""),
    md(
        "## 4. Comparing the eight architectures (cross-validation, after tuning)\nLower mean rank is better. "
        "The locked rule picks the simplest network whose rank is within one standard deviation of the best; this chose the plain MLP."
    ),
    code("""ranks = pd.read_csv(REPORTS / "phase06" / "step3_architecture_ranks.csv")
display(ranks)
decisions = json.loads((REPORTS / "phase06" / "decisions.json").read_text("utf-8"))
print("Selected architecture:", decisions["architecture"]["selected"])
print("Its configuration:", decisions["configs"][decisions["architecture"]["selected"]])
display(Image(str(FIG / "phase06_cv_comparison.png"), width=760))"""),
    md(
        "## 5. Train the chosen multi-output MLP live (seed 0)\nThis is the training call used by the project (`src/models/train.py: fit`), on the training rows, with early stopping on a part of them. Nothing is saved."
    ),
    code("""import torch
from src.models.data import make_model_data, dims_for
from src.models.train import fit, predict
from src.models.run_phase06_final import context, records, load_model
configs, columns, selected, seeds = context()
entry = cache["trainval"]
crosses = mc["wide_crosses"]
train_data = make_model_data(entry["train_x"], entry["train_y"], selected, columns, crosses)
val_data = make_model_data(entry["held_x"], entry["held_y"], selected, columns, crosses)
model = fit(selected, configs[selected]["cfg"], train_data, ["zscore", "zscore_band", "university_group", "degree_category"],
            0, dims_for(train_data, cv.N_DISTRICTS), mc["training"]["max_epochs"], mc["training"]["early_stopping_fraction"])
print(model.network)
print(f"Parameters: {model.n_params} | epochs run: {model.epochs_run} | best epoch: {model.best_epoch} | {model.seconds:.1f} s")"""),
    md("### Training curve of this run"),
    code("""import matplotlib.pyplot as plt
h = pd.DataFrame(model.history)
fig, ax = plt.subplots(figsize=(7, 3.5))
ax.plot(h["epoch"], h["train_loss"], label="training rows")
ax.plot(h["epoch"], h["es_loss"], label="early-stopping rows")
ax.set_xlabel("epoch"); ax.set_ylabel("loss (sum of the four tasks)"); ax.legend(); ax.set_title("Multi-output MLP, seed 0")
plt.tight_layout()
import io; buffer = io.BytesIO(); fig.savefig(buffer, format="png", dpi=110); plt.close(fig)
display(Image(data=buffer.getvalue()))"""),
    md("### The live model gives the same predictions as the saved model used by the app"),
    code("""saved = load_model("final", selected, "-", 0)
fresh_pred, saved_pred = predict(model, val_data), predict(saved, val_data)
for task in fresh_pred:
    print(f"{task:17s} largest difference on the 152 validation rows: {np.abs(fresh_pred[task] - saved_pred[task]).max():.2e}")"""),
    md("## 6. All five seeds re-trained, compared with the log (validation scores)"),
    code("""rows = []
for seed in seeds:
    job = cv.make_job("final", selected, configs[selected]["cfg"], columns, "trainval", seed, config_id=configs[selected]["config_id"])
    new = cv.evaluate_run(job, entry)
    old = next(r for r in records("final", selected) if r["seed"] == seed)
    for task, metric in (("zscore", "mae"), ("zscore_band", "macro_f1"), ("university_group", "macro_f1"), ("degree_category", "macro_f1")):
        rows.append({"seed": seed, "task": task, "metric": metric, "logged": old["metrics"][task][metric], "re-trained now": new["metrics"][task][metric]})
seeds_table = pd.DataFrame(rows)
seeds_table["same"] = np.isclose(seeds_table["logged"], seeds_table["re-trained now"], atol=1e-9)
display(seeds_table)
print("All re-trained scores equal the logged scores:", bool(seeds_table["same"].all()))"""),
    md(
        "## 7. Stage 2: the single-task Z-score MLP\nThe Z-score was predicted better by its own network (negative transfer in the multi-output model), as allowed by the locked rule. It is re-trained here in the same way."
    ),
    code("""s2 = decisions["stage2"]["zscore"]
print("Stage 2 network:", s2["selected"], s2["config_id"], s2["cfg"])
rows = []
for seed in seeds:
    job = cv.make_job("stage2_final", s2["selected"], s2["cfg"], columns, "trainval", seed, config_id=s2["config_id"], variant="zscore", tasks=["zscore"])
    new = cv.evaluate_run(job, entry)
    old = next(r for r in log if r["step"] == "stage2_final" and r["seed"] == seed)
    rows.append({"seed": seed, "logged MAE": old["metrics"]["zscore"]["mae"], "re-trained MAE": new["metrics"]["zscore"]["mae"]})
display(pd.DataFrame(rows))
pd.read_csv(REPORTS / "phase06" / "stage2_validation.csv")[["task", "stage2_model", "stage2_validation", "multi_output_validation", "ci_low", "ci_high"]]"""),
    md(
        "## 8. Validation results of all eight networks (mean ± SD over 5 seeds)\nAll models are reported, including the ones not chosen. Baseline = always predicting the training average / most common class."
    ),
    code("""pd.read_csv(REPORTS / "phase06" / "validation_primary.csv")"""),
    code("""display(Image(str(FIG / "phase06_learning_curves.png"), width=760))"""),
]

# ---- 04 test ---------------------------------------------------------------------------------
NB04 = header(
    "04 – Final evaluation on the test set (Phase 7)",
    "The test rows were opened **once**, in Phase 7, after every model choice had been fixed. "
    "This notebook does **not** open them again: it reads the results saved at that moment.",
) + [
    md("## 1. Record of the single test-set opening"),
    code("""access = json.loads((REPORTS / "phase07" / "test_access.json").read_text("utf-8"))
print("Opened at (UTC):", access["opened_at_utc"])
print("Test rows:", access["test_rows"])
print("Networks evaluated:", len(access["networks_evaluated"]))"""),
    md("## 2. Results for each target (value with 95 % bootstrap interval), all systems"),
    code("""for target in ("zscore", "zscore_band", "university_group", "degree_category"):
    display(Markdown(f"### {target}"))
    display(pd.read_csv(REPORTS / "phase07" / f"results_{target}.csv"))"""),
    md("## 3. Hypotheses H1–H6 against the success criteria locked in Phase 2"),
    code("""pd.read_csv(REPORTS / "phase07" / "hypotheses.csv")"""),
    code("""for name in ("comparison.png", "confusion_matrices.png", "reliability.png"):
    display(Image(str(REPORTS / "phase07" / name), width=760))"""),
]

# ---- 05 xai ----------------------------------------------------------------------------------
NB05 = header(
    "05 – Explainable AI (Phase 8 and the app's explanations)",
    "SHAP explanations of the chosen networks, grouped by question group (H7), and a live explanation "
    "of one made-up example student exactly as the app produces it.",
) + [
    md("## 1. Which question groups matter (H7, permutation importance on validation rows)"),
    code("""pd.read_csv(REPORTS / "phase08" / "h7_group_importance.csv")"""),
    code("""for name in ("phase08_h7_group_importance.png", "phase08_shap_importance.png", "phase08_shap_zscore_beeswarm.png"):
    display(Image(str(FIG / name), width=760))"""),
    md(
        '## 2. Live explanation for the made-up "average" example student\nThe example students are written by hand (`configs/example_profiles.yaml`); they are not survey respondents.'
    ),
    code("""import yaml
from src.models.service import Predictor
from src.explain.student import StudentExplainer
profile = yaml.safe_load(resolve_path("configs/example_profiles.yaml").read_text("utf-8"))["average"]
predictor = Predictor.load()
explainer = StudentExplainer.load(predictor)
z = explainer.explain(profile, "zscore")
print(f"Typical student: {z['typical_student_value']:.3f} | this student: {z['prediction']:.3f}")
print(pd.Series(z["groups"]).round(3).rename("change in Z-score by group").to_string())
print(f"Typical + groups = {z['typical_student_value'] + sum(z['groups'].values()):.3f} (additivity error {z['additivity_error']:.1e})")
print("Stable over 3 runs:", z["stable"], "| top-5 Spearman:", z["stability_spearman_top5"])
for sentence in z["sentences"]:
    print("-", sentence)"""),
]

# ---- 06 system -------------------------------------------------------------------------------
NB06 = header(
    "06 – The decision-support system end to end",
    "The five parts (prediction, target gap, explanation, recommendations, chatbot safety and university "
    "lookup) run for the three made-up example students. The chatbot's language model is not called here "
    "(it needs Ollama); its fixed safety and university answers are shown.",
) + [
    code("""import yaml
from src.system import DecisionSupportSystem
examples = yaml.safe_load(resolve_path("configs/example_profiles.yaml").read_text("utf-8"))
system = DecisionSupportSystem.load()
rows = []
reports = {}
for name, profile in examples.items():
    r = system.report(profile); reports[name] = r
    p, g, plan = r["prediction"], r["gap"], r["recommendations"]
    rows.append({"student": name, "target": profile["al_target_degree"], "district": profile["al_district"],
                 "Z best guess": p["zscore"]["predicted"], "Z range": f"{p['zscore']['range_low']}–{p['zscore']['range_high']}",
                 "band": p["zscore_band"]["most_likely"], "top degree area": p["degree_category"]["most_likely"],
                 "gap status": g["status"], "gap": g.get("gap_points"), "plan mode": plan["mode"], "suggestions": len(plan["recommendations"])})
pd.DataFrame(rows).set_index("student")"""),
    md("## Target gap messages"),
    code("""for name, r in reports.items():
    print(f"{name}: {r['gap']['message']}")"""),
    md("## First three study suggestions per student"),
    code("""for name, r in reports.items():
    print(name + ":", " | ".join(x["title"] for x in r["recommendations"]["recommendations"][:3]))"""),
    md("## Chatbot: safety guard and exact university lookup (no language model needed)"),
    code("""from src.chatbot.guard import topic_of
from src.chatbot.lookup import university_answer
for message in ("Which tablets help me study longer?", "Who won the cricket match yesterday?", "What should I do first?"):
    print(f"{message!r:45} -> topic: {topic_of(message)}")
print()
print(university_answer("Am I close to University of Peradeniya?", reports["average"]))"""),
]

NOTEBOOKS = {
    "01_data_preparation.ipynb": NB01,
    "02_feature_engineering.ipynb": NB02,
    "03_model_training.ipynb": NB03,
    "04_test_evaluation.ipynb": NB04,
    "05_explainable_ai.ipynb": NB05,
    "06_decision_support_system.ipynb": NB06,
}


def run(path: Path) -> None:
    from nbclient import NotebookClient

    nb = nbformat.read(path, as_version=4)
    NotebookClient(
        nb, timeout=3600, kernel_name="python3", resources={"metadata": {"path": str(HERE)}}
    ).execute()
    nbformat.write(nb, path)


WRAP_CSS = """<style>
pre, .highlight pre, .jp-OutputArea-output pre { white-space: pre-wrap !important; word-break: break-word; }
.jp-RenderedHTMLCommon table { font-size: 11px; }
@page { size: A4; margin: 14mm 12mm; }
</style>"""


def export(path: Path) -> None:
    from nbconvert import HTMLExporter

    EXPORTS.mkdir(exist_ok=True)
    html, _ = HTMLExporter().from_filename(str(path))
    html = html.replace(
        "</head>", WRAP_CSS + "</head>", 1
    )  # long lines wrap instead of being cut off
    html_path = EXPORTS / f"{path.stem}.html"
    html_path.write_text(html, "utf-8")
    if CHROME.exists():
        subprocess.run([str(CHROME), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={EXPORTS / (path.stem + '.pdf')}", html_path.as_uri()],
                       check=True, capture_output=True, timeout=300)  # fmt: skip


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-run", action="store_true")
    parser.add_argument(
        "--export-only", action="store_true", help="re-export the saved notebooks only"
    )
    parser.add_argument("only", nargs="*")
    args = parser.parse_args()
    for name, cells in NOTEBOOKS.items():
        if args.only and not any(o in name for o in args.only):
            continue
        path = HERE / name
        if args.export_only:
            export(path)
            continue
        nb = new_notebook(cells=cells)
        nb.metadata["kernelspec"] = {
            "name": "python3",
            "display_name": "Python 3 (.venv)",
            "language": "python",
        }
        nbformat.write(nb, path)
        if not args.no_run:
            print("running", name, flush=True)
            run(path)
            export(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
