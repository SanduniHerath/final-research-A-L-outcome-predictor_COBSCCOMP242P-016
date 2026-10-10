# Alora user test – session plan

For the researcher running the sessions. One session per student, about 45 minutes.

## 1. What the test measures

These targets were locked in Phase 2 (`configs/success_criteria.yaml`).

| Hypothesis | What is measured | Target |
|---|---|---|
| H12 Usability | System Usability Scale (SUS), questionnaire part A | Average SUS ≥ 68 |
| H10 Understanding | "Why this result" comprehension questions, part B | ≥ 70 % of answers correct |
| H9 Recommendations (testers) | Usefulness of the study plan, 1–5, part C, **in both modes** (close the gap and strengthen) | Median ≥ 4 in each mode |
| H9 Recommendations (expert) | Expert review form (`05_expert_review.md`) | Median ≥ 4 for relevance, actionability and age-appropriateness |
| Chatbot clarity | Clarity of chatbot answers, 1–5, part D | Median ≥ 4 |
| Task success (descriptive) | Observation sheet (`03_tasks_and_observation.md`) | Reported, no target |

**With 5 testers, results are described against these targets, not tested statistically** (Phase 2, limitation 7). Five users is the usual number for finding most usability problems (Nielsen & Landauer, 1993).

## 2. Who takes part

- **Five students** who have just finished their O/L and plan to do A/L in the Science stream.
- **Most will be about 16, so they are minors.** You need:
  - signed **parental consent** and the student's own **assent** (`02_information_and_consent.md`);
  - your university's ethics approval for the session.
- **Mix:** if possible, at least one student from a Sinhala-medium school and one from a Tamil-medium school, and a mix of boys and girls.
- **No names in the data.** Give each student a code (T1–T5). Keep the consent forms, which carry names, separate from the data.

## 3. What to prepare

- [ ] The laptop with Alora running: `uvicorn backend.app:app --port 8000`, then open <http://localhost:8000>. Check `/api/health` shows `"chatbot_available": true`.
- [ ] **Before each session:**
  - press **Delete my answers** on the About and Help page;
  - clear the chat ("Start a new chat");
  - set the language the student prefers.
- [ ] Printed: information sheet, consent and assent forms, task and observation sheet, questionnaire (parts A–E).
- [ ] A timer (phone) and a pen.
- [ ] The expert review form, sent to the expert separately (they review the three example students, not the testers).

## 4. Session steps

| Time | Step | What you say or do |
|---|---|---|
| 0–5 min | **Welcome and consent** | Check the signed parental consent. Go through the assent form with the student, who signs it. Say: *"We are testing the app, not you. There are no wrong answers. You can stop at any time."* |
| 5–7 min | **Choose how to take part** | The student can enter **their own O/L answers** or use a **made-up example student**. Say: *"Your answers stay on this laptop and we delete them at the end."* Never push a student to use their own results. |
| 7–30 min | **Tasks with thinking aloud** | Give the tasks one at a time (`03_tasks_and_observation.md`). Ask the student to say what they are thinking. **Do not help unless they are stuck for 2 minutes.** Then give the smallest hint and record it. |
| 30–33 min | **Second mode** | The student opens **one example student** whose mode is the opposite of their own plan. "Close the gap" → show Example A (strengthen); "Stay on track" → show Example C (close the gap). This lets every tester rate both modes (H9). **Open the example in a new private window** (Chrome: Ctrl+Shift+N, then `localhost:8000/?demo=strong` or `?demo=weak`). A private window keeps its own storage, so the tester's own answers stay safe in the normal window. Do **not** open the example in the same window or click "Use my own answers": both replace or delete the tester's answers. |
| 33–43 min | **Questionnaire** | Parts A (SUS), B (understanding), C (plan), D (chatbot), E (open questions). The student fills it in alone. Answer questions about wording only. |
| 43–45 min | **Debrief and clean-up** | Thank them. Say: *"This is a student prototype. It learned from a small survey, so its predictions are rough. Your A/L result is not fixed: your work changes it. Talk to your teachers about your plans."* Press **Delete my answers** together. |

## 5. Wellbeing

- **If a student seems upset by a low prediction,** stop the task. Remind them that the prediction is only a pattern from other students, and that many students improve a lot in A/L.
- **Offer to switch** to an example student.
- **If a student shares something worrying** (for example, about their feelings or safety), stop the session. Follow your university's safeguarding procedure, and tell a parent or teacher. The 1926 helpline is listed in the app.

## 6. After all sessions

- **Type the answers** into the templates in `templates/` and save them as `data/user_test/*.csv`. That folder is not committed to Git.
- **Score them:** `python -m src.evaluation.user_test` writes `reports/phase11/user_test_results.json` with every score next to its target.
- **Keep the observation notes.** Problems seen by two or more students go into the final report as usability findings.
