# Phase 2 – Hypotheses and Success Criteria

| | |
|---|---|
| Date | 15 October 2026 |
| Status | **Confirmed by the researcher and locked.** See §10 for the lock record. |
| Settings | `configs/success_criteria.yaml` (`status: confirmed`) |
| Lock | `configs/success_criteria.lock.json` (SHA-256 of the criteria file) |
| Code | `src/evaluation/criteria.py`: `require_locked()` stops any modelling or evaluation script if the criteria file has changed since locking |

## 1. Purpose

This phase does four things before any model is trained:

- turns the thesis research questions into testable hypotheses, linked to the five system parts
- fixes measurable success criteria for every prediction target and for the other four parts
- fixes how "better", "met" and "weak" will be decided
- records the limitations

Fixing these first means the results cannot shape the criteria used to judge them.

## 2. What was read

- **Thesis draft** (`first 3 chapters of the thesis.docx`, 11 October 2026):
  - Chapter 1: objectives and research questions
  - Chapter 3: evaluation strategy and metrics
  - Chapter 4: requirements FR1–FR7 and NFR1–NFR4
  - Chapter 5: Table 5.1
- **Supervisor guidance notes.** These have no specific requirement on hypotheses.
- **The project brief:** evaluation criteria A–E and the correlation rules.
- **No outcome variable was looked at to set any number in this document.**

## 3. Decisions taken in this phase

| Topic | Decision | Made by |
|---|---|---|
| One model or one per target | **Stage 1:** each architecture is built as one multi-output network (FR2). **Stage 2:** the model is replaced by a single-task network only for a target where the multi-output model is "weak" under the rule in §6.1. | Researcher (rule written by the engineer, see §6.1) |
| Prediction targets | Z-score, Z-score band, **university group (universities grouped by region)**, degree category | Researcher |
| "Intended goal achieved" | **Not a model target.** The gap between the student's stated target and their prediction decides the recommendation mode: *close the gap*, or *strengthen* the student's position where there is no gap. | Researcher |
| Linear / logistic reference | **Not added.** Only the trivial baselines are used. | Researcher |
| TabPFN | Included as a candidate. **The supervisor has not approved it**, and it is reported with that label. Run with one estimator (`n_estimators = 1`), because TabPFN otherwise averages several internal predictions, which the no-ensemble rule forbids. | Researcher (technical setting by the engineer) |
| Success-criteria numbers | Accepted as proposed | Researcher |
| User testing | 5 testers, students who have recently finished O/L | Researcher |
| UGC cut-offs | Only the three supplied documents (2019/20, 2021/22, 2023/24) are used. The thesis will state this. | Researcher |
| Research questions | The **four thesis RQs stay unchanged**. The checks for each system part are evaluation aspects of RQ4, not new questions. | Researcher |
| Data augmentation | **Not used.** The earlier draft (Section 4.7) used it, but the brief forbids changing the data to raise scores. | Brief |
| Z-score band boundaries | Must be fixed by a rule **before** training in Phase 3. The earlier draft chose 0.75 / 1.5 after seeing how the model did, which is a form of tuning to the data. | Brief |

## 4. Research questions (unchanged from Chapter 1)

| RQ | Question (thesis wording) | System part(s) | Answered in |
|---|---|---|---|
| RQ1 | What O/L stage academic, behavioral and preference related factors influence A/L performance and higher education outcomes among Sri Lankan Science stream students? | 5 XAI, 1 Prediction | Phases 4, 8 |
| RQ2 | Which O/L stage and A/L preference features are most significant in predicting A/L z-score, university and degree related outcomes? | 1 Prediction, 5 XAI | Phases 4, 8 |
| RQ3 | Which machine learning model achieves the best performance in predicting A/L z-score band, university and degree related outcomes for Sri Lankan Science stream students? | 1 Prediction | Phases 6, 7 |
| RQ4 | To what extent can the web-based decision support prototype identify the gap between a student's predicted A/L outcomes and their stated target, and deliver personalized study recommendations that target users find clear, relevant and useful? | 3 Gap, 2 Recommendation, 4 Chatbot, 5 XAI, interface | Phases 9–11 |

**Two points to note for the thesis:**
- RQ1 says "influence". The analysis can show **association only**, so the answer to RQ1 must say
  so (see §8, limitation 8).
- RQ3 says "machine learning model". The supervisor requires neural networks, so the answer will
  compare neural-network architectures.

## 5. Hypotheses

"Supported" means H0 is rejected under the decision rule in §6.1.

| ID | RQ | System part | H0 (null) | H1 (alternative) | Evidence |
|---|---|---|---|---|---|
| H1 | RQ3 | Prediction | The selected model's test MAE for the Z-score is not lower than that of the mean predictor. | The test MAE is at least 10 % lower than the mean predictor's. | Paired bootstrap CI of the MAE difference; R² and Spearman CIs |
| H2 | RQ3 | Prediction | For the Z-score band, macro F1 is not higher than the majority-class baseline. | Macro F1 is at least 0.10 higher than the baseline. | Paired bootstrap CI; QWK, balanced accuracy, ROC-AUC |
| H3 | RQ3 | Prediction | For the university group, macro F1 is not higher than the majority-class baseline. | Macro F1 is at least 0.10 higher than the baseline. | As for H2 (no QWK, because the classes are unordered) |
| H4 | RQ3 | Prediction | For the degree category, macro F1 is not higher than the majority-class baseline. | Macro F1 is at least 0.10 higher than the baseline. | As for H3 |
| H5 | RQ3 | Prediction | The selected classifiers are not acceptably calibrated (ECE > 0.10, or Brier score no better than predicting the class frequencies). | ECE ≤ 0.10 and the Brier skill score's CI lies above 0. | ECE, Brier skill score with CI, reliability plot |
| H6 | RQ3 | Prediction | For each task, the multi-output (multi-task) network performs the same as the single-task network of the same architecture. | It differs: better (positive transfer) or worse (negative transfer). Two-sided. | Paired bootstrap on validation; both loss curves |
| H7 | RQ1, RQ2 | XAI | A feature group (O/L results; background; attitudes; goals and activities; A/L subject choice) contributes nothing to prediction. | The group's grouped permutation importance is above 0. Tested for each group and each target. | Repeated permutations with a CI; SHAP for direction. **Association, not causation.** |
| H8 | RQ4 | Gap analysis | The gap status (gap / on track) agrees with whether test respondents actually reached the degree they aimed for at the start of A/L no better than chance. | Balanced accuracy's CI lies above 0.5. | Retrospective check on the test set. This evaluates the gap module; it is not a model target. |
| H9 | RQ4 | Recommendation | Recommendations are not rated acceptable. | Expert median ≥ 4/5 and tester median usefulness ≥ 4/5, in both modes (*close the gap*, *strengthen*). | Strong, average and weak example profiles |
| H10 | RQ4 | XAI | Explanations are unfaithful or unstable, or students do not understand them. | Additivity error ≤ 10⁻⁶, top-5 stability ρ ≥ 0.80, and ≥ 70 % of comprehension questions correct. | Automated checks plus user test |
| H11 | RQ4 | Chatbot | The chatbot states things it cannot support. | 0 invented numbers in 30 test prompts; 100 % out-of-scope refusal; ≥ 90 % "not sure" when unsupported. | Scripted test set |
| H12 | RQ4 | Interface | The prototype's usability is below average. | SUS ≥ 68. | System Usability Scale in the user test |

H9–H12 rely on 1 expert and 5 testers. They are judged against the threshold and reported
descriptively, with the number of raters stated. They are not tested statistically.

## 6. Success criteria for prediction

### 6.1 General rules

| Rule | Setting | Reason |
|---|---|---|
| Trivial baselines | Regression: training mean. Classification labels: majority class. Classification probabilities: training class frequencies. | A model must beat "guessing the usual answer" to be useful. |
| Confidence intervals | Percentile bootstrap, 2,000 resamples of the test set, 95 %, paired (model and baseline scored on the same resampled students). | Required by the brief. Pairing gives a fair comparison. |
| "Met" | The point estimate meets the threshold **and** the paired 95 % CI lies entirely on the better side. | Prevents claiming success from a lucky split. |
| "Partly met" | The point estimate meets the threshold, but the CI crosses it. | Honest middle category. |
| "Not met" | The point estimate does not meet the threshold. | – |
| Comparing two models | Model A is better than model B only if the CI of the paired difference excludes 0. Otherwise they are "not distinguishable". | – |
| **Stage 1: selection** | Every architecture is one multi-output network. Choose the architecture with the best mean rank of cross-validated primary metrics across the four targets. If several are within 1 SD, choose the one with the fewest parameters. Decided before the test set is opened. | The researcher's decision to start with one model (FR2). |
| **Stage 2: weakness rule** | Using training-set cross-validation only, the selected multi-output model is **weak** for a target if: **(a)** its primary metric misses that target's minimum against the baseline, or **(b)** it shows negative transfer against the single-task network of the same architecture. Only for weak targets, the best single-task network (same selection rule) is used instead. Both results are reported. | Puts the researcher's "if it shows weakness, change it" into an exact rule decided before the results exist. It never looks at the test set. |
| Cross-validation | Repeated stratified 5-fold, 3 repeats, inside the training set. | Required by the brief. |
| Stability | SD of macro F1 across folds ≤ 0.05; for MAE, SD / mean ≤ 0.10. | A score that moves more than this between folds is not reliable for one student. |
| Overfitting | Classification: train − validation macro F1 ≤ 0.10. Regression: (validation MAE − train MAE) / train MAE ≤ 0.20. | Judgement for about 720 training rows. |
| Repeated seeds | 5 seeds. Report the mean and SD of the score. Predictions are never averaged. | No-ensemble rule. |

**Size of the test set.** About 154 students means a proportion has a 95 % CI half-width of
about ±0.08. That is why the thresholds are 10 % / 0.10.

### 6.2 Per target

The class lists, band boundaries and regional groups are fixed in Phase 3.

| Target | Type | Primary metric | Secondary metrics | Minimum to count as "met" |
|---|---|---|---|---|
| Z-score | Regression | MAE | RMSE, R², Spearman ρ | MAE ≥ 10 % below the mean predictor; R² CI lower bound > 0; Spearman CI lower bound > 0 |
| Z-score band | Ordered classes | Macro F1 | Balanced accuracy, accuracy, per-class precision and recall, confusion matrix, QWK, within-one-band accuracy, ROC-AUC (OvR), log loss | Macro F1 ≥ baseline + 0.10; balanced accuracy CI lower bound > chance; QWK CI lower bound > 0; ROC-AUC CI lower bound > 0.5; log loss below baseline |
| University group (by region) | Unordered classes | Macro F1 | Balanced accuracy, accuracy, per-class precision and recall, confusion matrix, ROC-AUC (OvR), log loss | Macro F1 ≥ baseline + 0.10; balanced accuracy CI lower bound > chance; ROC-AUC CI lower bound > 0.5; log loss below baseline |
| Degree category | Unordered classes | Macro F1 | As for university group | As for university group |

**Why 10 % and +0.10.** These are the smallest improvements that would change what a student is
told, compared with "you are like the average student". They are a stated judgement, not a
figure from the literature.

### 6.3 Calibration (every classification target)

| Measure | Level | Reason |
|---|---|---|
| ECE (10 bins) | ≤ 0.10 | Students see probabilities, and neural networks are often over-confident. With about 15 test cases per bin, ECE is noisy, so 0.10 is not made stricter. |
| Brier skill score vs class frequencies | CI lower bound > 0 | The probabilities must be more informative than the class frequencies. |
| Reliability plot | Required | Shows where the model is over- or under-confident. |
| Fixing poor calibration | Temperature scaling on the validation set only | Adjusts one network's outputs; it is not an ensemble. |

### 6.4 Model-specific checks

The checks the brief requires for each model are all reported:

- ablations: dropout and L2; wide only / deep only / both; autoencoder size
- TabNet: masks, sparsity and stability across seeds
- entity embeddings compared with one-hot encoding
- ResNet-style network compared with the regularised DNN at the same depth
- training time and number of parameters

They are not pass / fail. The exception is negative transfer, which feeds the weakness rule.

**TabPFN** is a pretrained network that is not trained on this data in the usual way. Learning
curves and train–validation gaps are therefore reported as far as they apply, and it is labelled
"not supervisor-approved" in every table.

## 7. How the other four parts will be judged

| Part | Automated checks (all must pass) | Human judgement |
|---|---|---|
| 2 Recommendation | Every recommendation carries a reason and an evidence label (100 %). Rule unit tests pass. The mode (*close the gap* / *strengthen*) follows the gap status. "Similar successful profiles" are closer to the student than random profiles. | Expert median ≥ 4/5 (relevance, actionability, age-appropriateness) for the strong, average and weak profiles. Testers' usefulness median ≥ 4/5. |
| 3 Target gap | All scenario tests correct. Only the three supplied UGC documents or data-derived figures are used; **no cut-off is invented**. | H8 retrospective check: balanced accuracy CI lower bound > 0.5. |
| 5 XAI | Additivity error ≤ 10⁻⁶. Top-5 stability ρ ≥ 0.80. SHAP–permutation agreement reported. | ≥ 70 % of comprehension questions correct. |
| 4 Chatbot | 30-prompt scripted test: 0 invented numbers; 100 % refusal of medical, psychological and unrelated questions; ≥ 90 % "not sure" when unsupported. The support-tool notice is always visible. Reply within 10 s. | Testers' clarity median ≥ 4/5. |
| Interface | WCAG AA contrast (4.5:1) and the Phase 10 checks. | SUS ≥ 68 (Sauro, 2011; Bangor, Kortum & Miller, 2009). |

**User testing.** There will be 5 testers who have recently finished O/L. Most will be about 16
and still minors, so parental consent is needed and the session must be described in the ethics
section. Five testers is a common size for finding usability problems (Nielsen & Landauer, 1993).
It is not enough for statistical claims.

## 8. Limitations, recorded now

1. **Selection bias and a truncated outcome range.**
   - Every respondent entered a state university, so the model never sees students who did not.
   - In this dataset the lowest Z-score is 0.75.
   - Predictions for students whose likely outcome is below this range will be too optimistic,
     and the tool must say so.
2. **Recall and self-report.** O/L-stage answers were given years later by university students.
3. **Different exam years.** Respondents sat the A/L from 2018 or earlier to 2025, so Z-scores
   and cut-offs are not strictly comparable. Only three cut-off years are available.
4. **Convenience sample.** Generalisation to all Science-stream students is not guaranteed.
5. **Data-quality notes from Phase 1:**
   - uniform answer distributions
   - skipped answers to questions the form marks as required
   - two hand-typed cells
6. **Small test set (about 154).** Small differences cannot be confirmed.
7. **One expert and five testers.** H9–H12 are descriptive.
8. **Association, not causation.** This applies to RQ1, H7 and the wording of every
   recommendation.
9. **University group by region.** The region of a respondent's university is closely tied to
   their district through the UGC district quota system. A good score on this target may mostly
   reflect district, not academic profile. This will be checked and reported in Phase 8.
10. **TabPFN** has no supervisor approval. If the supervisor objects later, its results can be
    removed without affecting the other models.

## 9. What the next phase needs (Phase 3: labelling and documentation)

1. **Prediction time.** The proposal is "just after the O/L results are known, when the A/L
   subjects have been chosen", so the A/L subject choice is an input but A/L grades are not.
2. **Z-score band rule.** It must be fixed before training. The options are UGC cut-off levels
   from the three supplied documents, or fixed quantiles of the training set.
3. **Region grouping of the 15 universities.** The researcher must supply it or approve it, with
   the source of the regions (e.g. the province of the main campus).
4. **Degree categories.** The grouping of the 11 programmes must be approved.
5. **Small classes.** Merging rules must be decided.

## 10. Lock record

| | |
|---|---|
| File | `configs/success_criteria.yaml` |
| Locked | 15 October 2026, 00:57 (Sri Lanka time) |
| SHA-256 | `84403b283d1aa21c218992caaef9e28d2ead2f31ad05c924b2c2f7c3c9cd805d` |
| Command | `python -m src.evaluation.criteria --lock` |
| Check | `python -m src.evaluation.criteria --verify` |

Any later change needs: a written reason in this document, deleting the lock file, re-locking,
and a note in the phase document where the change was made. **It is never allowed after the test
set has been opened (Phase 7).**

## 11. Addendum (15 October 2026): TabPFN not used

The researcher decided not to use TabPFN. The locked criteria file still mentions it as an allowed
candidate (`general.tabpfn`). Because no threshold, metric or rule changes, the file was **not**
unlocked or edited. This addendum is the record of the decision. The candidate models are the
eight neural networks in the brief: MLP, regularised DNN, Wide & Deep, TabNet, multi-task
variant, entity-embedding MLP, autoencoder + MLP, and ResNet-style network.
