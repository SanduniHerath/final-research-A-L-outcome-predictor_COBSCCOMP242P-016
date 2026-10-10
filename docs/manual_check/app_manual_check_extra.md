# Alora – extra manual check with five more dummy students (F–J)

This sheet adds five new made-up students to the first sheet (`app_manual_check.md`, students A–E). They test cases that A–E do not cover:

| Student | What it tests |
|---|---|
| F, agriculture | The Biology + Chemistry + Agricultural Science combination; a private or semi-government school; a district (Anuradhapura) not used before |
| G, high grades but weak habits | Excellent O/L results with poor study habits and confidence: do the results and the habits pull in opposite directions? |
| H, Medicine with a gap | A middle student aiming high: the "close the gap" path, with universities that are close and further away |
| I, very weak | The lowest answers (S and W grades, "Never", 1s and 2s), the "Other" school type and a district with many missing cut-offs (Kilinochchi) |
| J, physical science | Top study habits ("More than 30 hours"), so the what-if card should show almost nothing left to gain |

**About the expected outputs**
- They were produced by the current trained models on 2026-10-16 by running each student through the system (`reports/phase11/manual_check_extra_run.py`). The full raw outputs are in `reports/phase11/manual_check_extra_outputs.json`.
- If the models are retrained, the numbers will change.
- These students are made up. They are not survey respondents.

**Before you start**
- Follow the same steps as in the first sheet: start the app, open <http://localhost:8000>, and use **About and Help → Delete my answers** before each new student.
- Agree/disagree statements: 1 = Strongly disagree … 5 = Strongly agree.

---

## Part 1 – Answers to enter

### Step 1 – You and your school

| Question | F | G | H | I | J |
|---|---|---|---|---|---|
| What type of school did you go to for O/L? | Private or semi-government school | National school | Provincial school | Other | National school |
| How would you rate your results in Grades 6 to 11? (1–5) | 3 | 5 | 3 | 1 | 4 |
| How often were you among the top students in your class? | Often | Always | Sometimes | Never | Often |

### Step 2 – Your O/L results

| Subject | F | G | H | I | J |
|---|---|---|---|---|---|
| Religion | A | A | B | S | A |
| First language | B | A | A | C | A |
| English | B | A | C | W | B |
| Mathematics | C | A | C | S | A |
| History | B | A | B | S | B |
| Science | B | A | B | S | A |
| Basket subject 1 | B | A | B | W | A |
| Basket subject 2 | A | A | C | S | B |
| Basket subject 3 | C | A | B | S | A |

### Step 3 – Your study habits

| Question | F | G | H | I | J |
|---|---|---|---|---|---|
| In Grade 11, how many hours a week did you study on your own? | 11 to 20 hours | Less than 5 hours | 5 to 10 hours | Less than 5 hours | More than 30 hours |
| I made good use of my study time. | 4 | 2 | 3 | 2 | 5 |
| I kept studying even when the lessons were boring. | 4 | 2 | 4 | 1 | 4 |
| I kept up with my schoolwork and homework every week. | 4 | 2 | 4 | 2 | 5 |
| I often found it hard to stick to a study timetable. | 2 | 4 | 3 | 5 | 1 |

### Step 4 – Your confidence

| Statement | F | G | H | I | J |
|---|---|---|---|---|---|
| I was confident I could understand the hardest lessons in my O/L subjects. | 3 | 3 | 3 | 1 | 4 |
| I expected to do well in the O/L exam. | 4 | 3 | 4 | 2 | 5 |
| I was confident I could do an excellent job in school tests and assignments. | 3 | 3 | 3 | 1 | 4 |
| I was sure I could master the skills taught in my O/L subjects. | 3 | 3 | 4 | 2 | 4 |

### Step 5 – Your interests and goals

| Question | F | G | H | I | J |
|---|---|---|---|---|---|
| I was very interested in Science and Mathematics. | 4 | 3 | 4 | 2 | 5 |
| I enjoyed Science more than most other subjects. | 4 | 2 | 4 | 2 | 4 |
| I thought Science and Mathematics would be useful for my future. | 5 | 3 | 4 | 3 | 5 |
| I explored Science topics beyond what was taught at school. | 3 | 2 | 3 | 1 | 5 |
| Do you have a clear career goal? | Yes | Not sure yet | Yes | No | Yes |
| Why did you choose the Science stream? (tick all) | My own interest, My career goal | My parents | My own interest, My teachers | My friends | My own interest, My teachers, My career goal |

### Step 6 – Your A/L plan

| Question | F | G | H | I | J |
|---|---|---|---|---|---|
| Which A/L subjects have you chosen? | Biology, Chemistry, Agricultural Science | Combined Maths, Physics, Chemistry | Biology, Chemistry, Physics | Biology, Chemistry, Physics | Combined Maths, Physics, Chemistry |
| District | Anuradhapura | Colombo | Matara | Kilinochchi | Hambantota |
| Which degree are you aiming for? | Agriculture or Food Science | Engineering | Medicine | Biological Science | Physical Science |

---

## Part 2 – Expected outputs, page by page

### 2.1 My Prediction

| Shown on the page | F | G | H | I | J |
|---|---|---|---|---|---|
| Z-score (big number) | **1.73** | **1.90** | **1.61** | **1.08** | **2.20** |
| Likely range | 1.42 to 2.06 | 1.59 to 2.24 | 1.30 to 1.95 | 0.77 to 1.42 | 1.88 to 2.53 |
| Band 1 (below 1.33) | 5% | 1% | 13% | **88%** ✓ | 0% |
| Band 2 (1.33 to 1.74) | 29% | 27% | **48%** ✓ | 10% | 7% |
| Band 3 (above 1.74) | **66%** ✓ | **72%** ✓ | 39% | 2% | **93%** ✓ |
| Top degree area | Allied Health Sciences 36% | Engineering 88% | Allied Health Sciences 70% | Biological Science 81% | Engineering 90% |
| 2nd degree area | Agriculture or Food Science 31% | Computing, IT, AI or Data Science 7% | Biological Science 19% | Agriculture or Food Science 9% | Medicine 8% |
| 3rd degree area | Computing, IT, AI or Data Science 20% | Medicine 3% | Agriculture or Food Science 6% | Allied Health Sciences 8% | Computing, IT, AI or Data Science 1% |
| University region (tag "Very rough guide") | Central and Highlands, Western | Southern, Western | Western, Central and Highlands | North Central and North Western, Northern and Eastern | Western, Central and Highlands |
| Low-result warning | not shown | not shown | not shown | not shown | not shown |

**Note on F.** The Z-score of 1.73 lies just inside Band 2 (the edge is 1.74), but the band chart shows Band 3 as most likely (66%). This is expected, not a fault: the Z-score and the band come from two separate networks, and F sits right on the edge between the two bands.

### 2.2 My Target and Gap

**Status box**

| | Expected title | Expected sentence |
|---|---|---|
| F | **You're on track for Agriculture or Food Science** (green) | "…(1.73) reaches the lowest 2023/2024 cut-off for Agriculture or Food Science in Anuradhapura: 0.60 (Agriculture, Eastern University, Sri Lanka)…" |
| G | **You're on track for Engineering** (green) | "…(1.90) reaches the lowest 2023/2024 cut-off for Engineering in Colombo: 1.61 (Engineering (TM), University of Moratuwa)…" |
| H | **0.22 to go for Medicine** (amber) | "…(1.61) is 0.22 below the lowest 2023/2024 cut-off for Medicine in Matara: 1.83 (Medicine, Rajarata University of Sri Lanka)…" |
| I | **You're on track for Biological Science** (green) | "…(1.08) reaches the lowest 2023/2024 cut-off for Biological Science in Kilinochchi: 0.57 (Applied Sciences (BIO.SC), University of Vavuniya, Sri Lanka)…" |
| J | **You're on track for Physical Science** (green) | "…(2.20) reaches the lowest 2023/2024 cut-off for Physical Science in Hambantota: 0.86 (Applied Sciences (PHY.SC), Wayamba University of Sri Lanka)…" |

**"Universities you could aim for" card**

| | Within reach | Close | Further away | No cut-off this year |
|---|---|---|---|---|
| F | **12**: Eastern University 0.6020 (1.13 above); Jaffna 0.6351 (1.09 above); Uva Wellassa, Export Agriculture 0.6874 (1.04 above); Wayamba 0.7115 (1.02 above) … | **1**: Sri Jayewardenepura, Food Science & Technology 1.4463 (0.28 above) | 0 | **1**: Peradeniya, Food Science & Technology |
| G | 0 | **6**: Moratuwa Engineering (TM) 1.6074 (0.29 above); Moratuwa Engineering (EM) 1.6222 (0.28 above); Sri Jayewardenepura 1.8086 (0.09 above); Ruhuna 1.8176 (0.08 above) … | 0 | **2**: Jaffna; South Eastern University |
| H | 0 | **5**: Rajarata 1.8311 (0.22 to go); Wayamba 1.8335 (0.22 to go); Sabaragamuwa 1.8474 (0.24 to go); Moratuwa 1.8480 (0.24 to go) … | **4**: Kelaniya 2.0192 (0.41 to go); Sri Jayewardenepura 2.1027 (0.49 to go); Peradeniya 2.2008 (0.59 to go); Colombo 2.3706 (0.76 to go) | **3**: Jaffna; Eastern University; Uva Wellassa |
| I | **2**: Vavuniya, Applied Sciences (BIO.SC) 0.5652 (0.51 above); South Eastern University 0.6312 (0.45 above) | 0 | 0 | **9**: Colombo, Peradeniya, Sri Jayewardenepura, Kelaniya … |
| J | **10**: Wayamba, Applied Sciences (PHY.SC) 0.8607 (1.34 above); Rajarata 0.8838 (1.32 above); Jaffna 0.9414 (1.26 above); South Eastern University 0.9692 (1.23 above) … | 0 | 0 | **3**: Eastern University; Vavuniya; Eastern University – Trincomalee Campus |

**Things to notice in this card**
- **G is "on track" but has no university "within reach".** This is correct. The status uses the best guess (1.90), which is above the lowest cut-off (1.61). "Within reach" needs the whole likely range (from 1.59) to be above the cut-off, and 1.59 is just below 1.61.
- **I gets many "No cut-off this year" rows.** Kilinochchi had no 2023/2024 cut-off for many courses in the UGC book. This is the official data, not a fault.

**Other cards on the Target page**

| | "Other degree areas you already reach" | "Students who entered …" |
|---|---|---|
| F | **"None found with your current prediction…"**, because with Biology, Chemistry and Agricultural Science the only area found is the target itself | Agriculture or Food Science: **1.12 and 1.55** |
| G | Agriculture or Food Science 0.62; Physical Science 0.83; Computing, IT, AI or Data Science 1.09 (all "Your whole range is above") | Engineering: **1.71 and 2.12** (same as student B) |
| H | Allied Health Sciences 1.08; Agriculture or Food Science 0.72; Biological Science 0.81 (all "whole range above") | Medicine: **2.07 and 2.31** (same as students A and C) |
| I | Allied Health Sciences 0.96 (**"Your best guess is above"**, blue chip); Agriculture or Food Science 0.55 ("whole range above") | Biological Science: **1.03 and 1.65** |
| J | Engineering 1.59; Agriculture or Food Science 0.72; Computing, IT, AI or Data Science 0.95 (all "whole range above") | Physical Science: **1.05 and 1.58** |

### 2.3 Why This Result

Every explanation starts from the **typical student's Z-score, 1.56**. Adding the group bars must give the Z-score from 2.1. Because each bar is rounded to 2 decimals, the total can differ by up to **0.02**; for F it does.

| Group bar (Z-score) | F | G | H | I | J |
|---|---|---|---|---|---|
| Your O/L results | ▼ −0.06 | ▲ +0.40 | ▼ −0.10 | ▼ −0.27 | ▲ +0.28 |
| Your attitudes and study habits | ▲ +0.14 | ▼ −0.07 | ▲ +0.09 | ▼ −0.15 | ▲ +0.27 |
| Your goals and reasons for choosing Science | ▲ +0.08 | ▼ −0.02 | ▲ +0.06 | ▼ −0.10 | ▲ +0.09 |
| Your school background and class standing | ▲ +0.03 | ▲ +0.04 | 0.00 | ▲ +0.05 | ▲ +0.02 |
| Your A/L subject choice | ▼ −0.04 | ▼ −0.02 | 0.00 | 0.00 | ▼ −0.03 |
| **1.56 + bars =** | **1.71** (shown 1.73) | **1.89** (shown 1.90) | **1.61** ✓ | **1.09** (shown 1.08) | **2.19** (shown 2.20) |
| First sentence | "Your attitudes and study habits raised your predicted Z-score by about 0.14…" | "Your O/L results raised … by about 0.40…" | "Your O/L results lowered … by about 0.10…" | "Your O/L results lowered … by about 0.27…" | "Your O/L results raised … by about 0.28…" |

**Student G is the key check here.** The O/L results bar should be large and up (+0.40), and the attitudes and study habits bar should be down (−0.07). The two pull in opposite directions, as the answers do.

**"Why [degree area]?" part.** The bars are in percentage points.

| | Degree area explained | Bars, largest first |
|---|---|---|
| F | Allied Health Sciences | Attitudes ▲ +9, O/L results ▲ +9, goals ▲ +8, A/L subject choice ▼ −8, school ▼ −1 |
| G | Engineering | O/L results ▲ +43, A/L subject choice ▲ +31, school ▲ +4, attitudes ▼ −3, goals ▲ +2 |
| H | Allied Health Sciences | A/L subject choice ▲ +19, O/L results ▲ +11, attitudes ▲ +10, goals ▲ +6, school ▲ +5 |
| I | Biological Science | A/L subject choice ▲ +18, school ▲ +15, O/L results ▲ +15, attitudes ▲ +8, goals ▲ +6 |
| J | Engineering | A/L subject choice ▲ +42, O/L results ▲ +32, attitudes ▲ +6, school ▲ +2, goals ▼ −1 |

All five explanations are "stable", so no instability warning should appear.

### 2.4 My Recommendations

| | F | G | H | I | J |
|---|---|---|---|---|---|
| Mode banner | **Stay on track** (green) | **Stay on track** (green) | **Close the gap** (amber) | **Stay on track** (green) | **Stay on track** (green) |
| "This week's plan" ticks | 3 | 5 | 4 | 5 | 2 |
| Suggestion 1 | Practise past papers | Make a simple weekly timetable | Practise past papers | Explore your career goal | Practise past papers |
| Suggestion 2 | Revise earlier lessons regularly | Give every study session one clear goal | Revise earlier lessons regularly | Build confidence step by step | Revise earlier lessons regularly |
| Suggestion 3 | Aim for a safety margin | Do a weekly catch-up | Set a weekly self-study target | Make a simple weekly timetable | Aim for a safety margin |
| "Show n more suggestions" | 1 more (Set a weekly self-study target) | 7 more (includes "Explore your career goal" and "Build confidence step by step") | 1 more (Give every study session one clear goal) | 7 more (includes "Strengthen your Science basics early") | none (only 3 suggestions) |
| Students like you: their usual Z-score | 1.47 (entered Agriculture or Food Science) | 1.89 (entered Engineering) | 2.16 (entered Medicine) | 1.07 (entered Biological Science) | 1.62 (entered Physical Science) |
| What if: Study habits / Confidence and interest / A clear career goal / All together | +0.04 / +0.07 / +0.00 / **+0.12** | +0.10 / +0.09 / +0.10 / **+0.26** | +0.07 / +0.07 / +0.00 / **+0.15** | +0.00 / +0.07 / +0.18 / **+0.24** | +0.00 / +0.03 / +0.00 / **+0.04** |

**Checks that should make sense**
- **G** has weak habits, so the plan starts with habit steps (timetable, clear goals, weekly catch-up), and every what-if row is above zero.
- **J** already gave the best answers for habits and has a clear goal, so those what-if rows are +0.00 and there are only 3 suggestions.
- **F, H and J** already have a clear career goal, so "A clear career goal" is +0.00.
- **I**'s "Study habits" row is +0.00 even though the habits are weak. This is not a mistake: it is what the model estimates for this student (moving every habit answer one step changes the prediction very little at this level). The largest gain for I is a clear career goal (+0.18).
- **H** is the only "Close the gap" student. The status box, the plan banner and the chatbot (if asked "Am I on track?") must all say there is a 0.22 gap.

### 2.5 Chatbot (use student H)

| You type | The answer must… |
|---|---|
| Am I on track for my target? | say **0.22 below** the Medicine cut-off and point to the study plan; no other numbers |
| Am I close to University of Colombo? | match word for word (fixed answer, checked on 2026-10-16): "Medicine at University of Colombo: the 2023/2024 cut-off for Matara district was 2.3706. Your predicted Z-score (1.61) is 0.76 below it, so it is further away for now: your whole likely range is below last year's cut-off. This is a guide from last year's cut-offs, not a promise…" |
| What should I do first? | name suggestion 1, **Practise past papers** |

---

## Part 3 – Extra checks

| # | Check | How | Expected | ✔/✘ |
|---|---|---|---|---|
| 3.1 | **Direction check** (better grades → higher prediction) | Enter student I again, but change **Mathematics S → B** and **Science S → B** only | Z-score rises from **1.08 to 1.11** (range 0.80 to 1.45); the O/L results bar becomes smaller (−0.27 → −0.23); "Strengthen your Science basics early" disappears from the suggestions | |
| 3.2 | **Target does not change the prediction** | For student H, change only the target from Medicine to Allied Health Sciences | The prediction and Why This Result stay exactly the same; the status becomes **"You're on track for Allied Health Sciences"**, with the lowest cut-off 1.08 (Nursing, University of Ruhuna); the plan becomes "Stay on track" | |
| 3.3 | **Same Medicine data across students** | Compare "Students who entered Medicine" for A, C and H | All show **2.07 and 2.31** | |
| 3.4 | **No unrealistic hours** | Look at H's "This week's plan" and "Set a weekly self-study target". Similar students who entered Medicine mostly studied more than 40 hours a week | No text says "more than 40 hours". Both use the softer wording: "Similar successful students studied regularly, on most days of the week, during A/L…" (For J the plan instead says "…mostly studied 21 - 30 hours a week…", because that number is realistic.) | |

**If any result differs:** write down the student (F–J), the page and what you saw. Delete your answers and try again before treating it as a fault.
