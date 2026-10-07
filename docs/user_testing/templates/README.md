# Answer templates

Copy these files to `data/user_test/` (not committed to Git) and fill in one row per tester.

| File | Filled from | Values |
|---|---|---|
| `sus.csv` | Questionnaire part A | 1–5 per item |
| `comprehension.csv` | Part B | letters a/b/c; `b3_correct` = 1 if the group named matches the tester's screen, else 0 |
| `ratings.csv` | Parts C and D | 1–5; `own_mode`/`example_mode` = `close_the_gap` or `strengthen`; `d3_noticed` = yes/no |
| `tasks.csv` | Observation sheet | `result` = done / hint / not_done; one row per tester and task (1–9) |
| `expert.csv` | Expert review | 1–5; `example` = strong / average / weak |

Then run `python -m src.evaluation.user_test`.
