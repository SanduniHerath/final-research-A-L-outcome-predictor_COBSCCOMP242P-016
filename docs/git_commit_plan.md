# Git branches and commit plan

This plan puts every project file into Git in the order of the thesis phases. It was checked against the project on 2026-10-17: the `git add` commands below cover all files exactly once, including this file.

## How it works

Git has no commits yet, so the history is built in phase order:

1. Make one first commit on `main`.
2. For each branch below, in order:
   - create it from `main`;
   - make its commits;
   - merge it back into `main` with `--no-ff`;
   - then start the next branch.

The history will then read like the thesis phases, and each branch shows up as a block of work.

**Do not change the commit dates.** Git will show the real date, which is honest: these files are being committed now. Backdating commits to look like they were made during each phase would misrepresent the work.

## Branches and commit messages

| # | Branch | Commit messages (in order) |
|---|---|---|
| 0 | `main` | `chore: project setup, configs and raw-data checksums (Phase 0)` |
| 1 | `feature/questionnaire-validation` | `feat(data): questionnaire reliability and validity analysis (Phase 1)`<br>`docs: Phase 1 results, expert validation form and figures` |
| 2 | `feature/success-criteria` | `feat(evaluation): lock hypotheses and success criteria before training (Phase 2)` |
| 3 | `feature/data-pipeline` | `feat(data): data cleaning and target labels with a cleaning log (Phase 3)`<br>`feat(features): feature pipeline and locked data split (Phase 4)`<br>`feat(data): class balance and cross-validation folds (Phase 5)` |
| 4 | `feature/model-training` | `feat(models): eight neural-network architectures and training loop`<br>`feat(models): cross-validation, random search and final training (Phase 6)`<br>`docs: Phase 6 results for all models` |
| 5 | `feature/evaluation-and-xai` | `feat(evaluation): single test-set evaluation with bootstrap CIs (Phase 7)`<br>`feat(explain): SHAP and grouped permutation importance (Phase 8)` |
| 6 | `feature/decision-support` | `feat(gap): UGC cut-off extraction and target-gap analysis`<br>`feat(recommend): rule-based study recommendations with evidence labels`<br>`feat(explain): per-student explanations and prediction service`<br>`feat(chatbot): local LLM chatbot with safety guard and number check`<br>`feat(backend): FastAPI service joining the five parts (Phase 9)` |
| 7 | `feature/web-app` | `feat(frontend): Alora web app in English, Sinhala and Tamil with light and dark mode`<br>`test(frontend): translation check and screenshot tools`<br>`docs: Phase 10 interface design, UI theories and screenshots` |
| 8 | `feature/integration-testing` | `test: end-to-end API and browser tests (Phase 11)`<br>`feat(evaluation): user-test materials, Google Form script and scoring`<br>`docs: manual check sheets (students A-J) and labelled simulated scoring dry run`<br>`feat(evaluation): user evaluation results (SUS and Parts B-D)`, **only after the check in step 8b** |
| 9 | `docs/notebooks-and-design` | `docs: appendix notebooks that reproduce training and evaluation`<br>`docs: wireframes, user flow and style guide`<br>`docs: final project README and Git plan` |

Dark mode is in the web-app commit. It is already part of the same files, so it cannot sensibly be a separate commit.

## The exact commands

Run these from `C:\AL_outcome_predictor` in Git Bash. The quotes around patterns such as `"reports/figures/phase01_*"` matter: they let Git match those files itself.

```bash
# 0 - main
git add .gitignore pyproject.toml requirements.in requirements.txt configs/project.yaml configs/data.yaml configs/columns.yaml \
  data/raw_checksums.json data/interim/.gitkeep data/processed/.gitkeep logs/.gitkeep models/.gitkeep notebooks/.gitkeep \
  backend/.gitkeep frontend/.gitkeep reports/figures/.gitkeep src/__init__.py src/utils src/data/__init__.py \
  src/data/register_raw.py src/data/load.py tests/test_utils.py tests/test_raw_data.py docs/phase00_project_setup.md
git commit -m "chore: project setup, configs and raw-data checksums (Phase 0)"

# 1
git switch -c feature/questionnaire-validation
git add configs/questionnaire.yaml configs/expert_items.yaml src/data/questionnaire.py src/data/cvi.py src/data/expert_form.py \
  src/data/exports.py src/data/run_phase01.py tests/test_questionnaire.py tests/test_phase01_outputs.py
git commit -m "feat(data): questionnaire reliability and validity analysis (Phase 1)"
git add docs/phase01_questionnaire_validation.md docs/phase01_expert_form reports/phase01 "reports/figures/phase01_*"
git commit -m "docs: Phase 1 results, expert validation form and figures"
git switch main && git merge --no-ff feature/questionnaire-validation -m "Merge Phase 1: questionnaire validation"

# 2
git switch -c feature/success-criteria
git add configs/success_criteria.yaml configs/success_criteria.lock.json src/evaluation/__init__.py src/evaluation/criteria.py \
  tests/test_criteria.py docs/phase02_hypotheses_and_success_criteria.md
git commit -m "feat(evaluation): lock hypotheses and success criteria before training (Phase 2)"
git switch main && git merge --no-ff feature/success-criteria -m "Merge Phase 2: hypotheses and success criteria"

# 3
git switch -c feature/data-pipeline
git add configs/cleaning.yaml configs/labels.yaml configs/roles.yaml configs/geography.yaml src/data/clean.py src/data/labels.py \
  src/data/run_phase03.py tests/test_clean_labels.py "docs/phase03_*" docs/data_dictionary.md docs/datasheet.md reports/phase03
git commit -m "feat(data): data cleaning and target labels with a cleaning log (Phase 3)"
git add configs/features.yaml configs/split.yaml configs/split.lock.json src/features src/data/split.py tests/test_features_split.py \
  docs/phase04_feature_engineering.md reports/phase04 "reports/figures/phase04_*"
git commit -m "feat(features): feature pipeline and locked data split (Phase 4)"
git add src/data/imbalance.py src/data/run_phase05.py tests/test_phase05.py docs/phase05_data_splitting.md reports/phase05 "reports/figures/phase05_*"
git commit -m "feat(data): class balance and cross-validation folds (Phase 5)"
git switch main && git merge --no-ff feature/data-pipeline -m "Merge Phases 3-5: data pipeline"

# 4
git switch -c feature/model-training
git add configs/models.yaml src/models/__init__.py src/models/data.py src/models/networks.py src/models/train.py
git commit -m "feat(models): eight neural-network architectures and training loop"
git add src/models/cv.py src/models/run_phase06.py src/models/run_phase06_final.py src/models/phase06_analysis.py \
  src/evaluation/metrics.py src/evaluation/bootstrap.py tests/test_phase06.py
git commit -m "feat(models): cross-validation, random search and final training (Phase 6)"
git add docs/phase06_train_and_tune.md reports/phase06 "reports/figures/phase06_*"
git commit -m "docs: Phase 6 results for all models"
git switch main && git merge --no-ff feature/model-training -m "Merge Phase 6: model training"

# 5
git switch -c feature/evaluation-and-xai
git add src/evaluation/run_phase07.py src/evaluation/phase07_analysis.py tests/test_phase07.py docs/phase07_test_and_evaluate.md \
  reports/phase07 reports/phase07_dryrun_validation
git commit -m "feat(evaluation): single test-set evaluation with bootstrap CIs (Phase 7)"
git add configs/explain.yaml src/explain/__init__.py src/explain/core.py src/explain/run_phase08.py tests/test_explain.py \
  docs/phase08_interpretation.md reports/phase08 "reports/figures/phase08_*"
git commit -m "feat(explain): SHAP and grouped permutation importance (Phase 8)"
git switch main && git merge --no-ff feature/evaluation-and-xai -m "Merge Phases 7-8: evaluation and interpretation"

# 6
git switch -c feature/decision-support
git add src/gap && git commit -m "feat(gap): UGC cut-off extraction and target-gap analysis"
git add configs/recommend.yaml src/recommend && git commit -m "feat(recommend): rule-based study recommendations with evidence labels"
git add src/explain/student.py src/models/service.py src/models/student.py && git commit -m "feat(explain): per-student explanations and prediction service"
git add src/chatbot "configs/chatbot_tests*.yaml" && git commit -m "feat(chatbot): local LLM chatbot with safety guard and number check"
git add configs/app.yaml configs/example_profiles.yaml src/system.py backend/__init__.py backend/app.py backend/schemas.py \
  src/evaluation/run_phase09.py tests/test_phase09.py docs/phase09_build_the_five_parts.md reports/phase09
git commit -m "feat(backend): FastAPI service joining the five parts (Phase 9)"
git switch main && git merge --no-ff feature/decision-support -m "Merge Phase 9: the five parts"

# 7
git switch -c feature/web-app
git add frontend/index.html frontend/css frontend/js frontend/i18n frontend/img src/evaluation/stats_api.py tests/test_phase10.py
git commit -m "feat(frontend): Alora web app in English, Sinhala and Tamil with light and dark mode"
git add frontend/package.json frontend/tools/check_i18n.mjs frontend/tools/capture_screens.mjs
git commit -m "test(frontend): translation check and screenshot tools"
git add docs/phase10_user_interface.md docs/phase10_screenshots
git commit -m "docs: Phase 10 interface design, UI theories and screenshots"
git switch main && git merge --no-ff feature/web-app -m "Merge Phase 10: user interface"

# 8
git switch -c feature/integration-testing
git add tests/test_e2e.py frontend/tools/e2e_browser.mjs reports/phase11/browser_e2e.json
git commit -m "test: end-to-end API and browser tests (Phase 11)"
git add docs/user_testing src/evaluation/user_test.py tests/test_user_test.py
git commit -m "feat(evaluation): user-test materials, Google Form script and scoring"
git add docs/manual_check reports/phase11/manual_check_expected_outputs.json reports/phase11/manual_check_extra_outputs.json \
  reports/phase11/manual_check_extra_run.py "reports/phase11/*SIMULATED*"
git commit -m "docs: manual check sheets (students A-J) and labelled simulated scoring dry run"

# 8b - ONLY if the check below confirms these are real, anonymised results (otherwise skip this step)
git add reports/phase11/sus_results.json reports/phase11/parts_bcd_results.json
git commit -m "feat(evaluation): user evaluation results (SUS and Parts B-D)"

git switch main && git merge --no-ff feature/integration-testing -m "Merge Phase 11: integration and user testing"

# 9
git switch -c docs/notebooks-and-design
git add notebooks && git commit -m "docs: appendix notebooks that reproduce training and evaluation"
git add docs/ui_design && git commit -m "docs: wireframes, user flow and style guide"
git add README.md docs/git_commit_plan.md && git commit -m "docs: final project README and Git plan"
git switch main && git merge --no-ff docs/notebooks-and-design -m "Merge appendix notebooks and UI design"

# check nothing is left, then push
git status
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
git push origin --all
```

`git status` at the end should say "nothing to commit". If anything is still listed (for example, because step 8b was skipped), decide where it belongs before you push.

## Step 8b: check before committing the user evaluation results

`reports/phase11/sus_results.json` and `reports/phase11/parts_bcd_results.json` contain per-tester scores (T01 to T12). Their source is "Alora - questionnaire for testers (Responses).xlsx". Commit them only if:

- they come from the 12 real participants of the user evaluation (not simulated or edited answers); and
- they contain no names or other details that could identify a participant (tester codes only).

If either is not true, skip step 8b. You can add the files to `.gitignore` or delete them.

## Before you push: privacy

**Already excluded from Git (in `.gitignore`):**
- the survey data and the test-set predictions;
- the trained models;
- the files in the project root (`r_dataset.xlsx`, `pilot test data set.xlsx`, `SUS.xlsx`, the UGC PDFs);
- the simulated `data/user_test_SIMULATED/` folder;
- the thesis folder `4th Year Research Documentations/`.

**One thing to decide:** `reports/phase03/cleaning_log.csv` lists 53 respondent codes (such as M0198) with what was changed in their rows. They are codes, not names, but the respondents are young.
- **Option 1 (simplest and safest):** make the GitHub repository private and give your supervisor access.
- **Option 2:** if the repository must be public, remove the code column from that file before committing.
