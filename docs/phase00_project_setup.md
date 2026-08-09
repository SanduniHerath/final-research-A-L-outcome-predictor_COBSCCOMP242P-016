# Phase 0 – Project Setup

| | |
|---|---|
| Date | 15 October 2026 |
| Status | Complete, awaiting approval to start Phase 1 |
| Location | `C:\AL_outcome_predictor` |

## 1. Purpose

Phase 0 creates a clean, reproducible project before any analysis is done. Specifically, it:

- protects the raw data from accidental change
- fixes where settings, seeds and logs live
- sets up testing and code-quality tools

The goal is that every later result can be traced back to an unchanged input file and re-run
with the same outcome.

## 2. What was done, step by step

1. **Agreed the setup with the researcher.** The project lives in the existing folder
   `C:\AL_outcome_predictor`, and phase documents are written in Markdown.
2. **Created the folder structure** required by the project brief (Section 4.1).
3. **Copied the raw files into `data/raw`.** The originals in the project root were left in place.
   - `data/raw/survey/r_dataset.xlsx` holds the main survey (1,015 rows × 53 columns).
   - `data/raw/pilot/pilot_test_data_set.xlsx` holds the pilot survey (13 rows × 53 columns).
   - `data/raw/ugc/` holds the three UGC admission handbooks (2019/20, 2021/22, 2023/24).
4. **Registered the raw data** with `python -m src.data.register_raw`:
   - recorded a SHA-256 checksum of every raw file in `data/raw_checksums.json`
   - recorded and checked the row and column counts of both spreadsheets
   - set every raw file to read-only
5. **Created a Python 3.12 virtual environment** (`.venv`). The top-level packages are listed in
   `requirements.in`. All 73 installed packages are pinned to exact versions in `requirements.txt`.
6. **Wrote the configuration files** `configs/project.yaml` (paths, seed, logging) and
   `configs/data.yaml` (raw file locations and expected shapes).
7. **Wrote shared utilities** in `src/utils`:
   - `config.py` loads the YAML files and resolves paths.
   - `logging_setup.py` sends logs to the console and to `logs/project.log`.
   - `seed.py` seeds Python, NumPy and PyTorch.
   - `checksum.py` computes and verifies SHA-256 checksums.
8. **Created one package per system part,** each with a docstring stating its role:
   - `src/models` (prediction)
   - `src/recommend` (recommendation)
   - `src/gap` (target gap analysis)
   - `src/chatbot` (chatbot)
   - `src/explain` (XAI)
9. **Added unit tests** (`tests/`) and the code-quality tool ruff (lint and format), configured in
   `pyproject.toml`.
10. **Initialised a Git repository** with a `.gitignore` that keeps survey data, trained models,
    logs and thesis working files out of version control.
11. **Wrote `README.md`** with the exact Windows (PowerShell) setup and run steps.

## 3. Decisions and reasons

| Decision | Reason |
|---|---|
| Use the existing folder `C:\AL_outcome_predictor` | The researcher chose it. The thesis files in it are ignored by Git, and nothing in the pipeline reads them. |
| Markdown for phase documents | The researcher chose it. Markdown is easy to compare between versions and can be converted to Word at the end. |
| Python 3.12, not the system default 3.14 | PyTorch, pytorch-tabnet and SHAP have mature Windows wheels for 3.12. |
| CPU build of PyTorch | The data is small (about 1,000 rows). A GPU gives no real benefit, and the CPU build installs reliably. |
| Seed 42, defined only in `configs/project.yaml` | One place to change it, and all modules read it from there. Repeated-seed experiments in Phase 6 will derive their seeds from this one. |
| Copy raw files into `data/raw` instead of moving them | The researcher's original files are not moved or changed. |
| Survey data is never committed to Git | The respondents are young people. A repository might later be pushed online, so only the checksum record is versioned. |
| `register_raw` refuses to overwrite an existing checksum record | Re-registering would silently accept a changed file. A deliberate change must be made by hand and documented. |
| Docstrings in Google style; ruff rules E, F, W, I, N, UP, B, D, ANN, SIM | These cover errors, import order, naming, docstrings and type hints, as the brief requires. |
| scikit-learn installed | Used only for preprocessing, data splitting and metrics. None of its ensemble models will be used. |
| TabPFN not installed yet | The brief lists it as "only if allowed". It will be added in Phase 6 only after the researcher confirms with the supervisor. |

## 4. Results

### 4.1 Folder structure

```
C:\AL_outcome_predictor
├── data
│   ├── raw              read-only originals (survey, pilot, ugc)
│   ├── interim
│   ├── processed
│   └── raw_checksums.json
├── configs              project.yaml, data.yaml
├── src
│   ├── data  features  models  evaluation  explain
│   └── recommend  gap  chatbot  utils
├── backend  frontend  models  notebooks
├── reports/figures
├── docs                 phase documents
├── tests
├── logs
├── README.md  pyproject.toml  requirements.in  requirements.txt  .gitignore
└── 4th Year Research Documentations   (thesis files, not part of the pipeline)
```

### 4.2 Raw data register

| File | Rows × columns | SHA-256 (first 16 characters) | Read-only |
|---|---|---|---|
| survey/r_dataset.xlsx | 1,015 × 53 | `7412753e206d94bf` | Yes |
| pilot/pilot_test_data_set.xlsx | 13 × 53 | `0c0892ba71bc528b` | Yes |
| ugc/2019_2020-NEW_SYLLABUS_ENGLISH.pdf | – | `9c369838ca210bed` | Yes |
| ugc/COP_2021_2022-ENGLISH.pdf | – | `b5effd59cc98b28a` | Yes |
| ugc/COP_2023_2024-ENGLISH_AR_A4.pdf | – | `7d03c7e3e46e48fa` | Yes |

The full checksums are in `data/raw_checksums.json`. Running `python -m src.data.register_raw --verify`
returned *"All 5 raw files match their recorded checksums"*.

### 4.3 Main package versions

| Package | Version | Use |
|---|---|---|
| torch | 2.14.1 (CPU) | All neural networks |
| pytorch-tabnet | 4.1.0 | TabNet |
| numpy / pandas | 2.5.4 / 3.0.6 | Data handling |
| scikit-learn | 1.9.1 | Preprocessing, splits, metrics |
| factor_analyzer | 0.5.1 | KMO, Bartlett's test, EFA (Phase 1) |
| shap | 0.53.0 | Explanations |
| fastapi | 0.143.1 | Backend |
| pytest / ruff | 9.1.1 / 0.17.0 | Tests and code quality |

### 4.4 Tests and code quality

| Check | Result |
|---|---|
| `python -m pytest` | 9 passed |
| `python -m ruff check .` | All checks passed |
| `python -m ruff format .` | All files formatted |

The tests check that:

- configs load, and a missing config raises an error
- paths resolve correctly
- the seed makes Python, NumPy and PyTorch draws repeatable
- the checksum function gives a known value and detects changed or missing files
- the registered raw files still match their checksums and are read-only

## 5. Problems found

1. **Different sample sizes in different places.**
   - The researcher confirmed on 15 October 2026 that `r_dataset.xlsx` is the real response file
     and has 1,015 rows.
   - The project brief says 1,029.
   - The thesis draft (`first 3 chapters of the thesis.docx`) says 1,021 in the abstract and
     Chapter 4, and 21 valid responses in Section 3.7.
   - Its Table 4.3 split (850 / 150 / 21) also differs from the 70 / 15 / 15 split this project
     will use.
   - **The thesis text needs to be updated to match the data that is actually used.**
2. **Pilot timing.**
   - Chapter 3 describes the pilot as coming before full data collection.
   - The pilot responses are dated 8–9 October 2026.
   - The main survey responses are dated 1 August – 10 October 2026, so the pilot falls inside
     the main collection period.
   - This must be explained correctly in the Phase 1 document and in the thesis.
3. **Source format.**
   - The main file is an `.xlsx` with one sheet named "Sheet1".
   - Earlier working copies of the survey file with different content were handled in previous
     sessions. Only `r_dataset.xlsx` is registered and used from now on.
   - **Recommendation:** keep the original Google Forms response sheet (or its download history)
     as provenance evidence in case an examiner asks how the file was produced.
4. **PowerShell may block `Activate.ps1`.** The README gives the one-line fix.
5. **PyTorch pin needs an extra install source.** `requirements.txt` pins `torch==2.14.1+cpu`,
   which is only on the PyTorch package index. The README install command includes
   `--extra-index-url` for this.

## 6. What the next phase needs

Phase 1 (questionnaire validation) needs these answers from the researcher before starting:

1. Were all 1,015 main responses collected with the **final** version of the questionnaire, with
   no wording or option changes during collection?
2. What exactly is the 13-row pilot file? Was it collected with the same questionnaire version,
   and why is it dated after most of the main responses?
3. Should the pilot respondents also appear in the main file, or are they separate people?
4. Which items belong to which construct? The proposed groups, based on the item wording, are:
   - **Self-efficacy:** 4 items, from MSLQ.
   - **Effort regulation and time management:** 4 items, from MSLQ. The item "I often found it
     hard to stick to a study schedule" is reverse-worded.
   - **Interest and value in Science and Mathematics:** 4 items.

   Please confirm these groups or correct them from the questionnaire source documents.
5. Which experts (number and role) will receive the content-validity form?
