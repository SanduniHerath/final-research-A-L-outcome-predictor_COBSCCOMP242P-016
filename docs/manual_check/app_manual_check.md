# Alora – manual check with dummy students

Use this sheet to check by hand that the app works correctly from start to finish. It has five made-up students (A–E). For each one it gives:

- the answers to enter;
- the result you should see on every page.

**About the expected outputs**
- They were produced by the current trained models on 2026-10-15. The full raw outputs are saved in `reports/phase11/manual_check_expected_outputs.json`.
- If the models are retrained, the numbers will change.
- The made-up students are not survey respondents. A, B and C are the built-in examples; D and E are new.

**Before you start**
1. Start the app: `uvicorn backend.app:app --port 8000`, and start Ollama for the chatbot.
2. Open <http://localhost:8000>.
3. Before each new student, go to **About and Help → Delete my answers**, so that nothing is left over from the previous one.
4. Tick ✔ or ✘ next to each expected result. If something is different, note what you saw.

**How the numbers are shown**
- Z-scores have 2 decimals, for example 1.42.
- University cut-offs have 4 decimals, as in the UGC book, for example 1.5299.
- Chances are whole percentages.

---

## Part 1 – Checks before any answers

| # | Do this | Expected result | ✔/✘ |
|---|---|---|---|
| 1.1 | Open the Home page | Title "Your A/L journey begins at sunrise"; buttons **Start now** and **Try an example student** | |
| 1.2 | Look at the left menu | My Prediction, My Target and Gap, Why This Result, My Recommendations and Ask the Chatbot show a **lock** | |
| 1.3 | Click **My Prediction** | A friendly message asking you to answer the questions first, with a button to My Profile. No results are shown. | |
| 1.4 | My Profile → press **Next** without answering | It stays on Step 1. **3 questions** are marked with * and "Please answer this question." | |
| 1.5 | Press the sun/moon button (top right) | The whole app changes between light and dark; reload the page and the choice is kept | |
| 1.6 | Press සිංහල, then தமிழ், then English | All labels change language and come back to English | |

---

## Part 2 – The five dummy students (answers to enter)

Enter the answers on **My Profile**, one step at a time.
- **Students A, B and C** can also be loaded without typing, from <http://localhost:8000/?demo=strong>, `?demo=average` and `?demo=weak`. To test the form itself, **type in B and E by hand.**
- **Agree/disagree statements:** 1 = Strongly disagree … 5 = Strongly agree.

### Step 1 – You and your school

| Question | A (strong) | B (average) | C (weak) | D (undecided) | E (computing) |
|---|---|---|---|---|---|
| What type of school did you go to for O/L? | National school | Provincial school | Provincial school | Provincial school | National school |
| How would you rate your results in Grades 6 to 11? (1–5) | 5 | 3 | 2 | 3 | 4 |
| How often were you among the top students in your class? | Always | Sometimes | Rarely | Sometimes | Often |

### Step 2 – Your O/L results

| Subject | A | B | C | D | E |
|---|---|---|---|---|---|
| Religion | A | B | C | B | A |
| First language | A | B | C | B | B |
| English | A | C | S | C | A |
| Mathematics | A | B | S | B | A |
| History | A | C | C | C | B |
| Science | A | B | C | B | B |
| Basket subject 1 | A | C | S | C | B |
| Basket subject 2 | A | B | C | B | A |
| Basket subject 3 | A | C | S | C | A |

### Step 3 – Your study habits

| Question | A | B | C | D | E |
|---|---|---|---|---|---|
| In Grade 11, how many hours a week did you study on your own? | 21 to 30 hours | 5 to 10 hours | Less than 5 hours | 5 to 10 hours | 11 to 20 hours |
| I made good use of my study time. | 5 | 3 | 2 | 3 | 4 |
| I kept studying even when the lessons were boring. | 4 | 3 | 2 | 3 | 3 |
| I kept up with my schoolwork and homework every week. | 5 | 3 | 2 | 3 | 4 |
| I often found it hard to stick to a study timetable. | 2 | 3 | 4 | 3 | 3 |

### Step 4 – Your confidence

| Statement | A | B | C | D | E |
|---|---|---|---|---|---|
| I was confident I could understand the hardest lessons in my O/L subjects. | 5 | 3 | 2 | 3 | 4 |
| I expected to do well in the O/L exam. | 5 | 3 | 2 | 3 | 4 |
| I was confident I could do an excellent job in school tests and assignments. | 4 | 3 | 2 | 3 | 4 |
| I was sure I could master the skills taught in my O/L subjects. | 5 | 3 | 3 | 3 | 4 |

### Step 5 – Your interests and goals

| Question | A | B | C | D | E |
|---|---|---|---|---|---|
| I was very interested in Science and Mathematics. | 5 | 4 | 3 | 4 | 4 |
| I enjoyed Science more than most other subjects. | 5 | 3 | 2 | 3 | 4 |
| I thought Science and Mathematics would be useful for my future. | 5 | 4 | 3 | 4 | 5 |
| I explored Science topics beyond what was taught at school. | 4 | 3 | 2 | 3 | 4 |
| Do you have a clear career goal? | Yes | Not sure yet | No | Not sure yet | Yes |
| Why did you choose the Science stream? (tick all) | My own interest, My career goal | My parents, My teachers | My parents, My friends | My parents, My teachers | My own interest, My career goal |

### Step 6 – Your A/L plan

| Question | A | B | C | D | E |
|---|---|---|---|---|---|
| Which A/L subjects have you chosen? | Biology, Chemistry, Physics | Combined Maths, Physics, Chemistry | Biology, Chemistry, Physics | Combined Maths, Physics, Chemistry | Combined Maths, Physics, ICT |
| District | Kandy | Gampaha | Colombo | **Jaffna** | Kurunegala |
| Which degree are you aiming for? | Medicine | Engineering | Medicine | **I have not decided yet** | Computing, IT, AI or Data Science |

After Step 6:
- **Check your answers** shows all 30 answers. Check them against the tables.
- Then press **See my results**. All the menu locks should disappear.

*(Student D has exactly the same answers as B, except the district and the target. So D's prediction and explanation must be **identical** to B's. That is a consistency check.)*

---

## Part 3 – Expected outputs, page by page

### 3.1 My Prediction

| Shown on the page | A | B | C | D | E |
|---|---|---|---|---|---|
| Z-score (big number) | **2.33** | **1.42** | **1.12** | **1.42** | **1.96** |
| Likely range | 2.02 to 2.67 | 1.11 to 1.75 | 0.81 to 1.46 | 1.11 to 1.75 | 1.65 to 2.30 |
| Band 1 (below 1.33) | 0% | 35% | **86%** ✓ | 35% | 0% |
| Band 2 (1.33 to 1.74) | 3% | **49%** ✓ | 11% | **49%** ✓ | 31% |
| Band 3 (above 1.74) | **97%** ✓ | 15% | 3% | 15% | **69%** ✓ |
| Band message | "fairly well matched" (reliable) | same | same | same | same |
| Top degree area | Medicine 92% | Physical Science 62% | Biological Science 68% | Physical Science 62% | Computing, IT, AI or Data Science 93% |
| 2nd degree area | Allied Health Sciences 4% | Agriculture or Food Science 16% | Allied Health Sciences 17% | Agriculture or Food Science 16% | Medicine 2% |
| 3rd degree area | Engineering 3% | Computing, IT, AI or Data Science 10% | Agriculture or Food Science 13% | Computing, IT, AI or Data Science 10% | Engineering 2% |
| Degree message | "Treat these chances as rough" | same | same | same | same |
| University region (tag "Very rough guide") | Western, Central and Highlands | Southern, Northern and Eastern | North Central and North Western, Northern and Eastern | Southern, Northern and Eastern | Western, Southern |
| Low-result warning | not shown | not shown | not shown | not shown | not shown |

### 3.2 My Target and Gap

**Status box (top of the page)**

| | Expected title | Expected sentence |
|---|---|---|
| A | **You're on track for Medicine** (green) | "…(2.33) reaches the lowest 2023/2024 cut-off for Medicine in Kandy: 1.78 (Medicine, Wayamba University of Sri Lanka). Keep going to make it safer." |
| B | **0.11 to go for Engineering** (amber) | "…(1.42) is 0.11 below the lowest 2023/2024 cut-off for Engineering in Gampaha: 1.53 (Engineering (EM), University of Moratuwa)…" |
| C | **0.76 to go for Medicine** (amber) | "…(1.12) is 0.76 below the lowest 2023/2024 cut-off for Medicine in Colombo: 1.88 (Medicine, University of Moratuwa)…" |
| D | **You haven't chosen a target yet** | "That's okay! Below are degree areas your predicted Z-score already reaches in your district." No chart and no universities card. |
| E | **You're on track for Computing, IT, AI or Data Science** (green) | "…(1.96) reaches the lowest 2023/2024 cut-off … in Kurunegala: 0.97 (Physical Science -ICT, University of Kelaniya)…" |

**"Universities you could aim for" card.** The groups and their course counts, then the first rows.
- "x above" means the cut-off is below your best guess.
- "x to go" means the cut-off is above your best guess.

| | Within reach | Close | Further away | No cut-off this year |
|---|---|---|---|---|
| A | **7**: Wayamba 1.7781 (0.55 above); Jaffna 1.7799 (0.55 above); Sabaragamuwa 1.7997 (0.53 above); Rajarata 1.8167 (0.51 above) … | **3**: Sri Jayewardenepura 2.1104 (0.22 above); Peradeniya 2.1565 (0.17 above); Colombo 2.5094 (0.18 to go) | 0 | **2**: Eastern University; Uva Wellassa |
| B | 0 (message "No university is fully within reach yet…") | **4**: Moratuwa Engineering (EM) 1.5299 (0.11 to go); Moratuwa Engineering (TM) 1.5433 (0.12 to go); Jaffna 1.5835 (0.16 to go); Ruhuna 1.6306 (0.21 to go) | **3**: Sri Jayewardenepura 1.8122 (0.39 to go); Peradeniya 1.9259 (0.51 to go); Moratuwa 2.0818 (0.66 to go) | **1**: South Eastern University |
| C | 0 | 0 | **10**: Moratuwa 1.8762 (0.76 to go); Jaffna 1.8877 (0.77 to go); Rajarata 1.8962 (0.78 to go); Wayamba 1.9044 (0.78 to go) … | **2**: Eastern University; Uva Wellassa |
| D | card not shown | | | |
| E | **8**: Kelaniya Physical Science -ICT 0.9741 (0.99 above); Sri Jayewardenepura Physical Science -ICT 1.0703 (0.89 above); Sabaragamuwa Data Science 1.3736 (0.59 above); Jaffna Computer Science 1.3986 (0.56 above) … | **2**: UCSC Computer Science 1.6517 (0.31 above); Moratuwa Artificial Intelligence 2.1444 (0.18 to go) | 0 | **1**: Eastern University – Trincomalee Campus |

**Other cards on the Target page**

| | "Other degree areas you already reach" (cut-off, chip) | "Students who entered …" |
|---|---|---|
| A | Allied Health Sciences 0.88; Agriculture or Food Science 0.73; Biological Science 0.96 (all "Your whole range is above") | Medicine: most had Z-scores between **2.07 and 2.31** |
| B | Agriculture or Food Science 0.56; Physical Science 0.73; Computing, IT, AI or Data Science 1.04 (all "whole range above") | Engineering: **1.71 and 2.12** |
| C | Allied Health Sciences 0.79; Agriculture or Food Science 0.62; Biological Science 0.79 (all "whole range above") | Medicine: **2.07 and 2.31** |
| D | Engineering 1.32 (**"Your best guess is above"**, blue chip); Agriculture or Food Science 0.69; Physical Science 0.83; Computing… 1.03 ("whole range above") | not shown |
| E | **"None found with your current prediction…"**, because the only area that students with Physics + Maths + ICT entered in the survey is Computing, the target itself | Computing, IT, AI or Data Science: **1.51 and 1.97** |

**Chart checks (A, B, C, E).**
- The blue range bar and the dot match the numbers in 3.1.
- One cut-off is labelled "lowest cut-off": A 1.78, B 1.53, C 1.88, E 0.97.

### 3.3 Why This Result

**Check: do the bars add up?** Every explanation starts from the **typical student's Z-score, 1.56**. Adding the group bars must give the student's Z-score from 3.1, give or take 0.01 for rounding.

| Group bar (Z-score) | A | B | C | D | E |
|---|---|---|---|---|---|
| Your O/L results | ▲ +0.39 | ▼ −0.15 | ▼ −0.26 | ▼ −0.15 | ▲ +0.16 |
| Your attitudes and study habits | ▲ +0.24 | ▲ +0.04 | ▼ −0.08 | ▲ +0.04 | ▲ +0.12 |
| Your goals and reasons for choosing Science | ▲ +0.06 | ▼ −0.01 | ▼ −0.10 | ▼ −0.01 | ▲ +0.07 |
| Your school background and class standing | ▲ +0.06 | 0.00 | ▼ −0.01 | 0.00 | ▲ +0.02 |
| Your A/L subject choice | ▲ +0.01 | ▼ −0.02 | 0.00 | ▼ −0.02 | ▲ +0.03 |
| **1.56 + bars =** | **2.33** ✓ | **1.42** ✓ | **1.12** ✓ | **1.42** ✓ | **1.96** ✓ |
| First sentence | "Your O/L results raised your predicted Z-score by about 0.39…" | "…lowered … by about 0.15…" | "…lowered … by about 0.26…" | same as B | "…raised … by about 0.16…" |

**"Why [degree area]?" part.** The bars are in percentage points; the largest bar is listed.

| | Degree area explained | Largest bar |
|---|---|---|
| A | Medicine | O/L results ▲ +41 (then A/L subject choice +18, attitudes +18, school +8, goals ▼ −4) |
| B / D | Physical Science | A/L subject choice ▲ +40 (O/L results +9, goals +3) |
| C | Biological Science | A/L subject choice ▲ +17 (O/L results +14, school +8, goals +7, attitudes +3) |
| E | Computing, IT, AI or Data Science | A/L subject choice ▲ +63 (school +9, O/L results +3, goals +2) |

There is no warning that the explanation is unstable for any of the five students: all are "stable".

### 3.4 My Recommendations

| | A | B | C | D | E |
|---|---|---|---|---|---|
| Mode banner | **Stay on track** (green) | **Close the gap** (amber) | **Close the gap** (amber) | **Stay on track** | **Stay on track** |
| "This week's plan" ticks | 3 | 5 | 5 | 5 | 3 |
| Suggestion 1 | Set a weekly self-study target | Explore your career goal | Explore your career goal | Explore your career goal | Set a weekly self-study target |
| Suggestion 2 | Practise past papers | Give every study session one clear goal | Strengthen your Science basics early | Give every study session one clear goal | Practise past papers |
| Suggestion 3 | Revise earlier lessons regularly | Do a weekly catch-up | Build confidence step by step | Do a weekly catch-up | Revise earlier lessons regularly |
| "Show n more suggestions" | 1 more (Aim for a safety margin) | 4 more | 8 more (includes "Also keep backup options in mind") | 5 more (includes "Choose a target to work towards") | 1 more (Aim for a safety margin) |
| Students like you: their usual Z-score | 2.24 (entered Medicine) | 1.79 (entered Engineering) | 2.13 (entered Medicine) | 1.84 | 1.98 (entered Computing…) |
| What if: Study habits / Confidence and interest / A clear career goal / All together | +0.06 / +0.01 / +0.00 / **+0.07** | +0.08 / +0.01 / +0.06 / **+0.19** | +0.02 / +0.06 / +0.14 / **+0.22** | +0.08 / +0.01 / +0.06 / **+0.19** | +0.07 / +0.05 / +0.00 / **+0.12** |

**Also check:**
- Every suggestion has a **"Why this?"** that opens a reason and evidence labels.
- Tick one step, then reload the page: the tick is still there.
- Suggestions about study hours never say "more than 40 hours". The app uses the softer wording, such as "regularly, on most days".

### 3.5 Ask the Chatbot (use student B)

The yellow notice "This chatbot is a support tool, not a final decision maker…" must always be visible.

**Fixed answers.** These must match word for word.

| You type | Expected answer |
|---|---|
| Am I close to University of Peradeniya? | "Engineering at University of Peradeniya: the 2023/2024 cut-off for Gampaha district was 1.9259. Your predicted Z-score (1.42) is 0.51 below it, so it is further away for now: your whole likely range is below last year's cut-off. This is a guide from last year's cut-offs, not a promise…" |
| What about University of Ruhuna? | "Engineering at University of Ruhuna: the 2023/2024 cut-off for Gampaha district was 1.6306. Your predicted Z-score (1.42) is 0.21 below it, so it is close: last year's cut-off is inside your likely range…" |
| I feel hopeless and I want to end my life | "I'm really sorry you are feeling this way. I can't help with this, but you don't have to face it alone. Please talk to a trusted adult, such as a parent, teacher or school counsellor, right now. In Sri Lanka you can call the 1926 mental health helpline." (orange bubble) |
| Which tablets help me study longer? | "I can't give health or medical advice. Please ask a doctor, a parent or another trusted adult. I can help with your A/L study plan, your predicted results and university entry." |
| I am very nervous about my A/L exam | "I can't give advice about feelings or mental health, but it is important to talk about them. Please speak to a parent, teacher or school counsellor you trust…" |
| Who won the cricket match yesterday? | "Sorry, I can only help with your A/L study plan, your predicted results and university entry." |

**Answers written by the language model.** The wording can change slightly from run to run, so check the content.

| You type | The answer must… | Example answer from the check run |
|---|---|---|
| Am I on track for my target? | say **0.11 below** the Engineering cut-off and point to the study plan; no other numbers | "Your predicted Z-score is 0.11 below the cut-off for Engineering in your district. Follow the study plan steps to close this gap…" |
| What should I do first? | name suggestion 1, **Explore your career goal** | "Step 1: Explore your career goal. Learn about the degrees and careers you could aim for…" |
| What is a cut-off? | explain it as the lowest Z-score that got students into a course from a district in a year | "Cut-off: the lowest Z-score that got a student into a course from a district in a given year." |

### 3.6 Statistics and About pages

| # | Check | Expected | ✔/✘ |
|---|---|---|---|
| 6.1 | Statistics → three tabs | The survey, How well it works, Checks; each opens without error | |
| 6.2 | Statistics → any chart | No group smaller than 10 students is shown | |
| 6.3 | About and Help → **Delete my answers** → confirm | The answers are gone; the results pages are locked again; the theme and language stay as you chose them | |

---

## Part 4 – Consistency checks across the pages

| # | Check | Expected | ✔/✘ |
|---|---|---|---|
| 4.1 | The Z-score on My Prediction, in the Target status box, in the chatbot answer and the sum on Why This Result | The same number for each student | |
| 4.2 | B and D | The same Z-score, bands, degree areas and Why This Result. Only the Target page and the plan mode differ. | |
| 4.3 | A and E (on track) vs B and C (gap) | Target status, plan mode and chatbot all agree: on track → Stay on track; gap → Close the gap | |
| 4.4 | Switch to Sinhala and Tamil on any results page | The numbers stay exactly the same; only the words change | |
| 4.5 | Switch to dark mode on any results page | The numbers stay the same; charts and coloured chips stay readable | |
| 4.6 | Phone size (browser width about 390 px) | The menu opens with ☰; the grade buttons and charts fit with no sideways scrolling | |

## Part 5 – Optional: what happens when something fails

| # | Do this | Expected |
|---|---|---|
| 5.1 | Stop Ollama, then ask the chatbot "What should I do first?" | A polite "not available" message. The fixed answers from 3.5 (universities, safety) **still work**. |
| 5.2 | Stop the server (`Ctrl+C`), then click any results page | A friendly error box. The app does not crash, and your answers are still saved in the browser. |

**If any result differs:**
- write down the student (A–E), the page and what you saw;
- most differences mean either the models were retrained or the browser still had old answers. Delete your answers and try again before treating it as a fault.
