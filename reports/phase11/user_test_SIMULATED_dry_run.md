# Phase 11 – dry run of the user-test scoring with SIMULATED answers

> **SIMULATED DATA – NOT A RESULT.** Every answer below was made up on 2026-10-15 by the
> AI assistant, at the researcher's request, to try the scoring script before the real sessions.
> No student or expert took part. These numbers say nothing about Alora's usability and **must
> not be reported as user-test results** in the thesis. The real results will be written to
> `reports/phase11/user_test_results.json` after the real sessions.

## Why this was done

To check that `src/evaluation/user_test.py` reads the answer sheets and scores them correctly against the targets locked in Phase 2 (`configs/success_criteria.yaml`). The made-up data covered:

- a mix of good and poor answers;
- both plan modes;
- three languages;
- tasks done with and without hints;
- a task that was not done.

## What was made up

| File (in `data/user_test_SIMULATED/`, not in Git) | Content |
|---|---|
| `sus.csv` | 5 testers (SIM_T1–SIM_T5), Part A. Two were deliberately below 68. |
| `comprehension.csv` | Part B, with typical mistakes in B2, B7, B8 and one wrong B3 |
| `ratings.csv` | Parts C and D: own plan and example plan for both modes; one tester did not notice the support-tool notice |
| `tasks.csv` | 9 tasks per tester; tasks 4 and 5 deliberately made harder |
| `expert.csv` | 1 expert (SIM_E1), ratings for the three example students |

Command:

```
python -m src.evaluation.user_test --folder data/user_test_SIMULATED --out data/user_test_SIMULATED/results_SIMULATED.json
```

A copy of the output is in `user_test_results_SIMULATED_dry_run.json` (this folder).

## Output of the dry run (simulated)

| Measure | Target (Phase 2) | Simulated value | Script verdict |
|---|---|---|---|
| H12 usability (SUS) | mean ≥ 68 | 75.0 (90, 77.5, 62.5, 55, 90) | met |
| H10 understanding "Why this result" | ≥ 70 % correct | 85 % (B2 and B7 at 60 %) | met |
| H9 study plan, testers | median usefulness ≥ 4 in each mode | close the gap 4.0, stay on track 4.0 | met |
| H9 study plan, expert | median ≥ 4 for each rating | 4 / 4 / 4 | met |
| Chatbot clarity | median ≥ 4 | 4.0 (4 of 5 noticed the notice) | met |

**Tasks (simulated):**
- tasks 1, 3, 6 and 8 were done by all five without help;
- task 4 (name a university): 2 done, 2 with a hint, 1 not done;
- task 5 (biggest group on "Why this result"): 3 done, 2 with a hint.

## What the dry run shows

1. **The script works.** It read all five sheets and produced the following without errors:
   - usability per tester and the mean;
   - the share correct per question and per tester;
   - medians per plan mode;
   - the expert medians;
   - the task summary.
2. **The verdicts are exactly what the made-up answers were built to produce.** They show only that the comparison with the targets works, not how Alora performs.
3. **Values exactly on the line.** Several made-up medians are exactly 4.0, the threshold. With 5 testers, one lower answer per person can turn "met" into "not met". The real results must be reported descriptively, as the script's note says (Phase 2, limitation 7).

## Before the real sessions

- Enter the real answers into the templates in `docs/user_testing/templates/` and save them as `data/user_test/*.csv`.
- Run `python -m src.evaluation.user_test`. It writes `reports/phase11/user_test_results.json`.
- The simulated folder `data/user_test_SIMULATED/` can then be deleted. It is never mixed with the real data, because the script reads `data/user_test/` by default.
