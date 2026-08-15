# Datasheet – A/L Science-Stream Outcomes Survey

Structure follows *Datasheets for Datasets* (Gebru et al., 2021). The facts below come from the
files, the questionnaire and the researcher's statements. Where something rests only on the
researcher's statement, this is said.

## 1. Motivation

| | |
|---|---|
| Purpose | To train and evaluate a decision-support tool that estimates A/L Science-stream outcomes for students who have just finished the O/L, and compares them with the student's own target. |
| Created by | The researcher (final-year undergraduate), as part of a thesis. |
| Funding | None stated. |

## 2. Composition

| | |
|---|---|
| Unit | One questionnaire response from one undergraduate of a Sri Lankan state university who completed the A/L in the Science stream. |
| Main file | `data/raw/survey/r_dataset.xlsx`: 1,015 rows × 53 columns. |
| Pilot file | `data/raw/pilot/pilot_test_data_set.xlsx`: 13 rows, same 53 columns, different people (researcher's statement). Used only for questionnaire validation. |
| Checksums | SHA-256 recorded in `data/raw_checksums.json` (Phase 0). |
| Content | Background; Grade 5 result; Grades 6–11 performance; nine O/L grades; Grade 11 study hours and tuition; 12 attitude items (self-efficacy, effort regulation, interest); career goal and stream influences; degree aimed for; school activities and leadership; A/L preparation habits; A/L subjects and grades; district; Z-score; university; degree programme; first preference. |
| Labels (Phase 3) | Z-score (number); Z-score band (tertiles of the training split, Phase 5); university group (5 regions); degree category (7 categories). See `configs/labels.yaml` and `reports/phase03/class_counts.csv`. |
| Missing data | Only three questions have blanks: O/L tuition (260), school activities (268) and leadership (256). The form marks all three as required. The researcher states the respondents probably skipped them. They are kept as missing, with "skipped" indicators. |
| Sample make-up | 51 % female, 49 % male. A/L years from 2018 or earlier to 2025. 71 % first attempt. 25 A/L districts. 15 universities. 11 degree programmes. |
| Subpopulations not covered | Students not admitted to a state university; Arts, Commerce and Technology streams; private and foreign institutions; Dental Surgery and Veterinary Science (no respondents enrolled). |
| Confidential / sensitive data | No names, contact details or registration numbers. Quasi-identifiers (district + university + programme + year + gender) could narrow down a person in small cells. Row-level data is therefore never committed to version control or published. |

## 3. Collection process

| | |
|---|---|
| Instrument | Bilingual (English / Sinhala) Google Form: a screening and consent block plus sections A–F, 40 questions (the two grade grids count as one question each). The live form was read on 15 October 2026, and its wording and options are stored in `configs/columns.yaml`. |
| Sampling | Convenience sample of state-university undergraduates (thesis Section 3.7). |
| Period | Main file timestamps: 1 August – 10 October 2026. Pilot timestamps: 8–9 October 2026. |
| Consent | Every respondent ticked both consent statements (bilingual). Email collection was disabled (thesis 3.12). |
| Ethics review | To be stated by the researcher. |
| Questionnaire version | Final version for all responses, including the pilot (researcher's statement, 15 October 2026). |
| File provenance | The main file is an `.xlsx` with a single sheet named "Sheet1", supplied by the researcher. It is not a direct Google Forms export file. Earlier working copies of the same survey with different content were handled in earlier sessions. Only this file is registered and used. |

## 4. Preprocessing and cleaning

All cleaning is done by `python -m src.data.run_phase03` and logged in
`reports/phase03/cleaning_log.csv`. The raw files are read-only.

- **Whitespace:** one A/L Combined Mathematics grade "C " was trimmed to "C".
- **District:** one cell "M+AX533atara" was corrected to "Matara" (reason logged).
- **Duplicates:** none found.
- **Z-scores:** all numeric, between 0.75 and 2.61. No extreme values (quartiles ± 3 × IQR).
- **Tick-all questions** were split into yes/no columns. Option labels that contain commas are
  matched as whole items, so they are not split apart.
- **A/L subject combination** was derived from which subjects were taken. The grades themselves
  are not used.
- **Flagged, not changed:** one respondent (M0211) entered Physical Science with Biology,
  Chemistry and Physics. This is the only Physical Science student with that combination. The
  researcher considers it an entry error, so the row is kept unedited but **excluded from
  modelling** (1,014 modelling rows).
- **Submission timestamp** removed from the cleaned data.

## 5. Known data-quality observations

These are reported in Phase 1 §8 and Phase 3. The researcher has chosen to proceed.

1. All 12 attitude items have almost identical answer distributions (means 2.99–3.08), and most
   multiple-choice options are chosen almost equally often.
2. Blank answers to three questions the form marks as required.
3. 34 % of those who answered the leadership question report having been **Head Prefect**.
4. Of respondents with a usable degree target, 208 aimed at a degree category that **nobody in
   the data** entered with the subjects they themselves took. For example, students who took
   Combined Maths and ICT but aimed for Medicine.

## 6. Uses

| | |
|---|---|
| Intended | Training and evaluating the thesis prototype. Describing associations between O/L-stage answers and A/L outcomes **within this sample**. |
| Not appropriate | Making admission decisions; any causal claim; predicting for students below the sample's Z-score range or outside the Science stream; publishing row-level data. |

## 7. Distribution and maintenance

| | |
|---|---|
| Distribution | Not distributed. Row-level data stays on the researcher's computer. Only aggregate tables and figures appear in reports. |
| Maintenance | The researcher. Any new or corrected raw file must be registered as a new file with a new checksum and a written reason. Existing raw files are never overwritten. |
