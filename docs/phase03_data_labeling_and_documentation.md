# Phase 3 – Data Step: Labelling and Documentation

| | |
|---|---|
| Date | 15 October 2026 |
| Status | Complete. Researcher decisions D1–D4 recorded on 15 October 2026 (§8). |
| Code | `src/data/clean.py`, `src/data/labels.py`, `src/data/run_phase03.py` (`python -m src.data.run_phase03`) |
| Settings | `configs/labels.yaml`, `configs/roles.yaml`, `configs/cleaning.yaml` |
| Outputs | `data/interim/survey_labeled.csv` (not committed); `reports/phase03/*.csv`; `docs/data_dictionary.md`; `docs/datasheet.md` |

## 1. Purpose

This phase:
- fixes the prediction time
- gives every column a role (input, target, leakage and so on)
- defines the targets and counts their classes
- cleans the data with a logged, repeatable script
- documents the dataset (data dictionary, datasheet) and protects the respondents' privacy

## 2. Prediction time

**Just after the O/L results are known, when the student has chosen their A/L subjects.**
The researcher confirmed this on 15 October 2026.

At that moment a student knows:
- their background
- their Grade 5 result and school performance
- their O/L grades, study habits and attitudes
- their goals and activities
- their district
- **which** A/L subjects they will take

They do **not** know anything from the A/L years: grades, study hours, attempts, university or
degree.

## 3. Role of every column

Full table: `reports/phase03/column_roles.csv`. The data dictionary gives every column with its
role, missing count and values.

| Role | Columns | Use |
|---|---|---|
| **Input** (32 raw questions + derived columns) | O/L school type; Grade 5; Grades 6–11 rating; class rank; 9 O/L grades; Grade 11 study hours; O/L tuition; 12 attitude items; clear career goal; stream influences; school activities; leadership roles (D2); extracurricular rating; A/L district; **A/L subject combination** (derived from "taken / not taken" only) | Model inputs |
| **Target** | Z-score; university; degree programme | Sources of the 4 targets |
| **Gap only** | Degree aimed for at the start of A/L (and the derived target category, goal status and consistency flag) | Gap module, recommendation mode, hypothesis H8. **Never a model input** (thesis 4.5) |
| **Recommendation** | A/L study hours, past-paper practice, revision frequency | Known only after the prediction time. Used only as evidence for the study-plan rules |
| **Leakage** | A/L attempt; the six A/L grades; first-preference outcome | Outcomes or post-prediction facts. Never used |
| **Administrative** | ID, timestamp, consent, eligibility, A/L exam year | Not used by the model. The exam year is kept for the limitation analysis |
| **Fairness only** | Gender | Never an input. Used to check that the model works equally well for female and male students (D1). |

Points behind the roles:

- **A/L grades are leakage, but the subject *choice* is an input.** Only "taken / not taken" is
  read, to build `al_subject_combination`, and the grade values are never used. This follows the
  thesis scope (Chapter 1.5: "together with A/L subject and stream preferences").
- **A/L exam year is not an input.** A student using the tool will sit the A/L in a year outside
  the training years, so the model could not use it meaningfully.
- **A/L attempt is leakage.** Whether a student needs a second or third attempt is only known
  after the A/L.
- **School activities and extracurricular rating** are kept as inputs, with a timing caveat: the
  questions do not limit the answer to the O/L years.

## 4. Targets

| Target | Kind (decides the metrics) | Definition | Classes and counts (n = 1,015) |
|---|---|---|---|
| Z-score | Regression | Reported final Z-score | 0.75 to 2.61, no missing |
| Z-score band | **Ordered** | Three equal-sized bands (tertiles). The edges are computed on the **training split only** in Phase 5, then frozen and applied to validation and test. A value equal to an edge goes to the higher band. | About one third each, by construction. Exact counts in Phase 5. |
| University group | **Unordered** | Province of the main campus, merged into five regions (below) | Western 336 · Northern and Eastern 286 · Central and Highlands 217 · Southern 90 · North Central and North Western 86 |
| Degree category | **Unordered** | Programme mapped to the questionnaire's own "degree aimed for" categories | Biological Science 233 · Computing, IT, AI or Data Science 177 · Agriculture or Food Science 158 · Allied Health Sciences 156 · Physical Science 138 · Engineering 83 · Medicine 70 |

### 4.1 Why tertiles for the Z-score band

The researcher asked which option is better: bands from UGC cut-offs, or equal-sized bands.
Equal-sized bands (tertiles) are recommended and used, for four reasons:

1. **No arbitrary choices.**
   - UGC cut-offs are published separately for every course, university and district, and they
     change every year. The three supplied documents are tables of exactly this kind.
   - A single national band edge would require choosing which course, district and year sets it.
     Each such choice could be challenged.
2. **Balanced classes.** About 51 test students per band gives stable macro F1 and calibration
   estimates. UGC-based bands could leave one band with very few students.
3. **No loss of meaning.** The gap module (Phase 9) compares the predicted Z-score with the exact
   cut-off for the student's own target course and district. That is more precise than any band.
4. **Decided before training, and never changed afterwards.** The earlier draft chose its edges
   after seeing how the model did, and this avoids that.

**Thesis impact:** Section 3.7 should say the UGC cut-offs inform the **gap analysis**, not the
band edges. In the student interface the bands mean "relative standing among students who entered
university" and are worded gently (Phase 10).

### 4.2 University regions (proposal, for approval)

| Region | Universities (province of main campus) | n |
|---|---|---|
| Western | Colombo, Sri Jayewardenepura, Kelaniya, Moratuwa (Western) | 336 |
| Central and Highlands | Peradeniya (Central), Sabaragamuwa (Sabaragamuwa), Uva Wellassa (Uva) | 217 |
| Southern | Ruhuna (Southern) | 90 |
| Northern and Eastern | Jaffna, Vavuniya (Northern); Eastern, Trincomalee Campus, South Eastern (Eastern) | 286 |
| North Central and North Western | Rajarata (North Central), Wayamba (North Western) | 86 |

**Reasons for the merges:**
- Nine separate provinces would leave classes of 6 (Uva) and 21 (North Western), too few to
  learn or test.
- The merges join neighbouring provinces: the central highlands; the North and East; and the two
  northern-central provinces.

**Before citing:** the province of each campus should be confirmed from the UGC list of
universities.

### 4.3 Degree categories

The seven categories are the questionnaire's own answer options for "Which degree were you aiming
for when you started A/L?". The predicted category can therefore be compared directly with the
student's stated target in the gap module.

| Category | Programmes |
|---|---|
| Medicine | Medicine |
| Engineering | Engineering |
| Allied Health Sciences | Nursing, Pharmacy |
| Agriculture or Food Science | Agriculture, Food Science & Nutrition |
| Biological Science | Biological Science |
| Physical Science | Physical Science |
| Computing, IT, AI or Data Science | Computer Science, Data Science, Artificial Intelligence |

The questionnaire also offers "Dental Surgery or Veterinary Science", but no respondent is enrolled
in it, so it cannot be a predicted class.

### 4.4 Small classes

**Rule:** merge any class with fewer than 50 students, which is about 5 % of the data and about 7
students in the test set. **Result:** no class falls below this (smallest: Medicine, 70), so
nothing was merged.

### 4.5 Degree category and A/L subjects

The A/L subject combination largely limits the degree category
(`reports/phase03/degree_category_by_subject_combination.csv`):

- Every Computing student took Physics + Combined Maths + ICT (except 3 who took Chemistry +
  Physics + Combined Maths).
- Every Engineering student took Chemistry + Physics + Combined Maths.
- Medicine and Allied Health students all took Biology + Chemistry + Physics.

A model will therefore look accurate partly because the subject choice is an input. The real test
is whether it separates categories **within** the same subject combination. Phase 7 will report
this as well, so the headline score is not over-read.

### 4.6 Goal status (not a model target)

Goal status compares the degree aimed for at the start of A/L with the degree category entered.

| Goal status | n |
|---|---|
| Reached | 134 |
| Not reached | 674 |
| No usable target ("I had not decided", "Other") | 207 |

**Consistency flag (data-derived).** For each respondent with a target, it checks whether **anyone
in the data** entered that target category with the same A/L subjects:

| Result | n |
|---|---|
| Combination seen in the data | 506 |
| **Not seen** (e.g. aimed for Medicine while taking Combined Maths and ICT) | **208** |
| Cannot check (no target, or aimed for Dental / Veterinary, which nobody entered) | 301 |

This is not an admission rule. It only describes the data. It matters for H8, the retrospective gap
check: a target that no one reached with the same subjects will almost always show "not reached",
whatever the model predicts. Phase 9 will report H8 both for all respondents and for those with an
observed combination.

## 5. Cleaning

Full log: `reports/phase03/cleaning_log.csv`. **No row was deleted.**

| Step | Rows | Result |
|---|---|---|
| Trim spaces in text cells | 1 | Combined Mathematics "C " → "C" (M0198) |
| Value correction | 1 | District "M+AX533atara" → "Matara" (M0532). Typing error; no other district fits. |
| Answers outside the form's options | 0 | All single-choice, grid and scale answers match the form. |
| Exact duplicate rows | 0 | – |
| Skipped questions | 260 / 268 / 256 | Tuition, school activities, leadership. Kept as missing with a `_skipped` indicator (researcher's decision). |
| Tick-all questions | – | Split into yes/no columns. Option labels with commas are matched whole. "None" is recognised. Write-in text gets its own flag (none found in school activities or leadership). |
| Z-score checks | 0 | All numeric. Range 0.75–2.61. No extreme values (quartiles ± 3 × IQR = −0.72 to 3.79). |
| Rare degree / subject combination | 1 | M0211: Physical Science with Biology + Chemistry + Physics (0.7 % of Physical Science students). **Flagged, not changed.** Researcher to check. |
| Timestamp removed | – | Privacy |

The cleaned and labelled table has 1,015 rows × 81 columns.

## 6. Documentation and privacy

- **Data dictionary:** `docs/data_dictionary.md`, generated from the configs and the data, so it
  always matches the code. For every column it gives the meaning, type, role, missing count and
  values.
- **Datasheet:** `docs/datasheet.md`, following Gebru et al. (2021). It covers motivation,
  composition, collection, cleaning, data-quality observations, appropriate and inappropriate uses,
  and maintenance.
- **Privacy:**
  - No names or contact details were ever collected.
  - The submission timestamp is removed after cleaning.
  - Respondent IDs are row numbers.
  - Row-level files (`data/raw`, `data/interim`, `data/processed`) are excluded from Git.
  - Reports contain only aggregates, plus a few row IDs in the cleaning log.
  - Small combinations of district, university, programme, year and gender could narrow down a
    person, so row-level data must never be published.

## 7. Problems found

1. **208 targets inconsistent with the respondent's own subject choice** (§4.6). This affects how
   H8 can be read.
2. **34 % of respondents who answered the leadership question report being Head Prefect.** A school
   normally has one or two Head Prefects, so this share is very high. It adds to the data-quality
   observations from Phase 1.
3. **Leadership timing.** Prefect and captain roles are usually held in the A/L years, after the
   prediction time (§8).
4. **Degree category is largely limited by the subject choice** (§4.5). Scores must also be shown
   within each subject combination.
5. **One rare degree / subject combination** (M0211), flagged for the researcher.

## 8. Researcher decisions

| # | Question | Proposal |
|---|---|---|
| D1 | **Gender as a model input?** It is known at O/L, but a student-facing tool that predicts a lower result partly *because* of gender raises a fairness problem. | **Do not use it as an input.** Keep it to check the model's performance separately for female and male students (fairness check in Phases 7–8). |
| D2 | **Leadership roles as inputs?** Prefect, Head Prefect and captain roles are usually held in Grades 12–13, after the prediction time. | **Exclude** them as inputs. Keep school activities and the extracurricular rating, with the timing caveat. |
| D3 | **University regions** (§4.2) | Approve, or change the grouping. Confirm the provinces from the UGC list. |
| D4 | **M0211** (Physical Science with Biology + Chemistry + Physics) | Keep as recorded (it is flagged), unless you know it is an entry error. |

**Decided on 15 October 2026:**

| # | Decision |
|---|---|
| D1 | **Gender is not an input.** Role `fairness_only`: it is used to report model performance separately by gender. |
| D2 | **Leadership roles are inputs.** The researcher notes that prefect positions can be held by the O/L stage. The timing caveat is kept: some reported roles may date from the A/L years. |
| D3 | **University regions approved** as in §4.2. The provinces will be confirmed from the UGC list when cited. |
| D4 | **M0211 is excluded from modelling.** The researcher considers it an accidental entry error. Because it is unknown which answer is wrong, the row is **not edited**. It stays in the cleaned file with `exclude_from_modelling = 1`, and the reason is in the cleaning log. **Modelling uses 1,014 rows.** |

The degree categories (§4.3) and the tertile band rule (§4.1) are applied as recommended.

## 9. What the next phase needs (Phase 4: feature engineering)

- The final input list follows from §3 and D1–D2.
- The feature pipeline will be fitted on the training split only. Phase 5 does the splitting, but
  the pipeline code is written in Phase 4 and fitted once the split exists. It covers:
  - ordinal grades
  - one-hot encoding for small categories, and embeddings later for district
  - scaling
  - skipped-answer indicators
  - composite indices: mean O/L core grade, number of A grades, and the self-efficacy,
    effort-regulation (with and without er4) and interest indices
- Correlation-based feature checks use the training data only, with Spearman, Cramér's V or
  point-biserial as the data type requires.
