# Phase 10 – User Interface: Alora

| | |
|---|---|
| Date | 15 October 2026 |
| Status | Complete. Waiting for approval to start Phase 11. Sinhala and Tamil text are first drafts waiting for the researcher's check (§7). |
| App name | **Alora** – "A/L" + *aurora*, the light at dawn. Tagline: **"Your A/L, lit up."** (researcher's name and idea) |
| Code | `frontend/` – `index.html`, `css/tokens.css` (design tokens), `css/app.css`, `js/main.js` (router and menu), `js/pages/*.js` (one file per page), `js/charts.js`, `js/i18n.js`, `i18n/en.js`, `i18n/si.js`, `i18n/ta.js`, `img/logo.svg` |
| Backend additions | `GET /api/stats` (`src/evaluation/stats_api.py`, aggregates only), `GET /api/examples`, the interface served at `/`. Recommendation rules now also return their values (`params`) so the interface can show them in Sinhala and Tamil. |
| Run | `uvicorn backend.app:app --port 8000`, then open <http://localhost:8000> |
| Screenshots | `docs/phase10_screenshots/` (24 images, made by `frontend/tools/capture_screens.mjs`) |

## 0. Summary in plain words

- **Alora is a website with nine pages**, one for each job:
  - Home
  - My Profile
  - My Prediction
  - My Target and Gap
  - Why This Result
  - My Recommendations
  - Ask the Chatbot
  - Statistics
  - About and Help
- **It is built for 15–16 year olds:**
  - simple words and short sentences
  - one main button per screen
  - big buttons that are easy to tap
  - questions asked step by step, with a progress bar
  - kind wording for weak results, for example "0.76 to go", never "fail"
- **The look follows the name.** A deep morning-blue sky stands for trust and warms into an amber sunrise for hope. The colours follow a 60-30-10 plan.
  - **Every text colour passes the WCAG AA contrast test.** All 23 checked pairs are 4.5:1 or more.
  - **Nothing relies on colour alone.** Every colour comes with an icon, an arrow or a word.
- **It works in English, Sinhala and Tamil.**
  - The Sinhala questions reuse the exact Sinhala wording of your Google Form.
  - The Tamil text is new, so it must be checked.
  - The chatbot still answers in English, and the page says so.
- **Nothing about a student leaves their device**, except the answers sent to work out the results. The server keeps nothing.
- **It also works offline.** No internet fonts or libraries are used.
- **Tests:** `python -m pytest` gives 145 passed. The new checks cover the served pages, the statistics privacy rule, colour contrast, translation keys and script syntax. The screenshot tool found no errors in the browser console.

## 1. Brand and visual identity

| Element | Choice | Why |
|---|---|---|
| Name | **Alora** ("A/L" + aurora) | Researcher's choice: "your A/L journey begins at sunrise". Short, easy to say in all three languages. |
| Tagline | "Your A/L, lit up." (සිං: "ඔබේ උසස් පෙළ, ආලෝකමත් කරමු." / த: "உங்கள் உயர்தரம், ஒளிமயமாக.") | Shown next to the logo and on the Home page. |
| Logo | A sun rising over the horizon, on a night-to-morning blue square (`img/logo.svg`) | Says "dawn" at a glance. Works at 16 px (browser tab). |
| Home picture | The sun rising behind hills, with a dotted path from a book (start) to a flag (goal), framed in a round "dawn window" | The A/L journey as a path towards a goal. |
| Hero background | Deep night blue at the top, warming into an amber sunrise glow in the lower right | The glow sits behind the picture, never behind text, so contrast stays high. |
| Tone of voice | Friendly, direct, encouraging, honest | "Your result is not fixed. Your work in A/L can change it." |

## 2. Pages and the student's journey

```
Home ──► My Profile (6 steps + review) ──► 1 Prediction ► 2 Target ► 3 Why ► 4 Plan ► 5 Chat
                                                       (step pills on every results page)
Always available: Statistics, About and Help.  "Try an example student" works without answering.
```

| Page | Main content | Main action |
|---|---|---|
| Home | Dawn hero, 3-step "How it works", 3 trust notes | **Start now** (or "Continue my answers" / "See my results") |
| My Profile | 30 questions in 6 short steps: progress bar, step pills, encouragement, a review page | **Next** → **See my results** |
| My Prediction | Z-score with range line, band, top-3 degree areas, region (collapsed) | Next: compare with your target |
| My Target and Gap | Big status card (on track / "x to go"), range vs cut-offs line, backup areas, courses (collapsed) | Next: why |
| Why This Result | 5 question groups as up/down bars, plain sentences; single answers on request; why the degree area | Next: my plan |
| My Recommendations | Mode banner, "This week's plan" checklist (5 items), top-3 suggestions (more on request), similar students, what-if | Questions? Ask the chatbot |
| Ask the Chatbot | Notice always visible, suggested questions, chat | Send |
| Statistics | 3 tabs: the survey / how well it works / checks and hypotheses | – |
| About and Help | What Alora is, 5 parts, how to use, Q&A, help and 1926, delete my answers | – |

**Design notes:**
- **Results pages are locked** (with a lock icon) until the profile is finished.
- **"Try an example student"** opens three made-up students. Testers and teachers can see everything without typing. The page shows a banner saying it is an example.

## 2a. Addition: "Universities you could aim for" (researcher's request)

**The model does not name universities.** In Phase 7 it could only guess the region, and no better than chance: placement also depends on the order in which a student lists universities. So the named universities come **from the three UGC cut-off documents**, not from the model, and the page says so.

**What changed:**
- **Backend** (`GapAnalyzer.university_groups`, `src/gap/analysis.py`):
  - every university offering the target's courses in the student's district is put into one of four groups by last year's (2023/24) cut-off:
    - **Within reach:** the whole likely range is at or above the cut-off.
    - **Close:** the cut-off lies inside the range.
    - **Further away:** the whole range is below.
    - **No cut-off this year:** NQC.
  - each row also carries `gap_from_best_guess` (cut-off minus predicted Z);
  - each backup degree area also lists the universities whose cut-off the best guess reaches.
- **Interface (My Target and Gap):** a visible card with the four groups:
  - "Within reach" and "Close" are open; the other groups are folded;
  - each university shows its cut-off and "0.16 to go" or "0.55 above";
  - a fixed note says: "This is a guide from last year's official cut-offs, not a prediction of your university. The UGC places students by Z-score AND by the order in which they list universities, and cut-offs change every year."
  - The old folded course list was removed because the card replaces it.
- **Chatbot:**
  - The fact sheet lists the groups with each university's cut-off and gap.
  - **A live check found a problem.** The language model attached correct numbers to the wrong university. For example, it said Peradeniya was 0.11 away; the real gap is 0.51.
  - **Questions that name a university** ("Can I get into Peradeniya?") are therefore now answered **by an exact lookup in Python** (`src/chatbot/lookup.py`), without the language model. Questions about a *district* ("…for Jaffna district?") are not treated as university questions.
  - This follows the Phase 9 rule: Python decides, the model only explains.

**H11 still stands at run 3.** These chatbot changes came **after** the final scripted test, so its result is unchanged. The new lookup path is covered by unit tests and the live check, not by a new scripted run. Phase 11 should include university questions in the user test.

Tests: `python -m pytest` now gives **148 passed**.

## 2b. Addition: dark mode (researcher's request, before the user test)

The app now has a **light theme** (morning) and a **dark theme** ("the night before the sunrise"), which fits the Alora dawn idea.

- **How a student switches.** A sun / moon button sits in the top bar, next to the language switch. The moon means "switch to dark", the sun "switch to light".
- **First visit.** Alora follows the device's own setting (light or dark). After the student presses the button, their choice is remembered on that device. It stays even when "Delete my answers" is used, because it is a preference, not an answer.
- **No white flash.** A tiny script (`frontend/js/theme-init.js`) picks the theme before the page is drawn.
- **One set of colours per theme.** All colours live in `frontend/css/tokens.css`; the dark set redefines them under `:root[data-theme="dark"]`. The charts and legends now read these colours too, so they change with the theme.
- **Design choices** (theories in section 3):
  - **Dark blue, not pure black,** and off-white text, not pure white. This gives less glare and halo, which is easier for long evening study.
  - **Colours keep their meaning in both themes:** blue = up / you, orange = down / gap, green = on track, amber = highlight (consistency, Nielsen 4).
  - **Fills that carry text become lighter in dark mode,** so the text on them turns dark. Examples are the primary buttons and the student's chat bubbles.
  - **The dawn hero stays a dark sky in both themes,** so its white text always passes.
- **Checked.**
  - Every WCAG contrast pair in section 3.2 is now tested in **both** themes, plus the new pairs: text on blue, green and amber fills, and the hero sky.
  - A browser check confirms three things: the theme follows the device, the button changes the colours, and the choice survives a reload.

Tests: `python -m pytest` now gives **235 passed**; the browser check gives **15 of 15**.

## 3. Design theories used, and exactly where

### 3.1 Colour theory

| Theory | Where it is applied |
|---|---|
| **60-30-10 rule** | **60 %:** calm neutral surfaces (page `#F5F8FC`, cards white). **30 %:** trust blue (`#1F5FAD`/`#174C8C`): primary buttons, active menu item, bars, the Z-score number, hero. **10 %:** warm amber accent (`#F4A62A`): only the single most important button ("Start now"), the tagline, step-number badges and "gap" highlights. Tokens in `css/tokens.css`. |
| **Complementary harmony** | Blue (sky) and amber/orange (sun) sit opposite each other on the colour wheel. The accent therefore stands out against the blue without clashing. The logo, hero, "Start now" button and gap card use this pair. |
| **Analogous harmony** | The sky gradient moves through neighbouring blues (`#143A6B` → `#1F5FAD` → `#2B6CB8`). This keeps large areas calm. |
| **Colour psychology** | **Blue = trust and calm:** results, navigation. **Green = growth:** "on track", reliable chances, ticked steps, "you can work on this". **Amber/orange = warmth and attention**, used for a gap ("0.11 to go") instead of red, so a gap feels like a next step, not a failure. **Red is used only for real errors** (an unanswered question). |
| **Colour-blind safety** | **Up/down** use blue vs orange, the safest pair for the common types of colour blindness. **Every colour meaning also has a sign:** ▲/▼ arrows, ✓, icons in status chips, and word labels and legends ("Raised it" / "Lowered it", "Within reach", "Close – just below"). Bands show a ✓ and a thicker border, not only a colour. |

### 3.2 Accessibility (WCAG 2.2 AA)

**Contrast**, computed with the WCAG formula. Text needs 4.5:1; graphics and focus rings need 3:1. Regression tests are in `tests/test_phase10.py`.

| Pair | Ratio | | Pair | Ratio |
|---|---|---|---|---|
| Body text on page / card | 15.1 / 16.1 | | Hero heading (white on night blue) | 11.4 |
| Secondary text on card / page | 7.7 / 7.2 | | Hero text on blue | 5.6 |
| Links, quiet buttons | 8.6 | | Tagline (amber on night blue) | 5.6 |
| White on primary button | 6.4 | | Active menu item | 7.4 |
| "Start now" (ink on amber) | 7.9 | | Amber / green / orange notes | 7.3 / 7.1 / 5.7 |
| Encouragement (green) | 5.3 | | Error text | 6.6 |
| Up / down values | 8.6 / 6.5 | | Down bar / up bar (graphics) | 4.4 / 6.4 |
| Focus ring (deep amber on white) | 4.6 | | Focus ring on dark hero (white) | 11.4 |

The first focus colour (light amber, 2.0:1) **failed** this check and was changed to a deep amber. On the dark hero the focus ring is white.

**Other accessibility features:**
- **Structure:** semantic HTML; a "Skip to main content" link; real radio buttons and checkboxes under the styled answer chips, so they work with the keyboard and screen readers.
- **Announcements and keyboard:** `aria-live` messages for step changes and results; Statistics tabs work with the arrow keys.
- **Language:** `lang` changes with the language, so screen readers use the right voice.
- **Motion and print:** `prefers-reduced-motion` turns animations off; there is a print layout.
- **Charts:** each chart has a text description, and bar lists also show the number in words.

### 3.3 Typography and layout

| Theory | Where |
|---|---|
| **Modular type scale (1.25, "major third")** | Sizes are 0.8, 0.9, 1, 1.25, 1.56, 1.95 and 2.44 rem from a 17 px base: a larger base for long reading sessions on phones. One family, Segoe UI with Nirmala UI and Noto, covers English, Sinhala and Tamil. |
| **Line length and spacing** | Paragraphs are at most 66 characters wide, with line height 1.55. |
| **8-point spacing grid** | Every space is 4, 8, 12, 16, 24, 32, 48 or 64 px (`--s-1`…`--s-8`). This gives an even rhythm. |
| **Visual hierarchy / focal point** | Each page has one big number or status as the focal point: the Z-score "1.42", the status card "0.11 to go", the mode banner. Supporting details are smaller and lower. |

### 3.4 Nielsen's 10 usability heuristics

| Heuristic | Where |
|---|---|
| 1. Visibility of system status | Progress bar and "% done"; step pills with ticks; loading card with spinner and placeholder ("Working out your results…"); the chat shows "…" while thinking; "2 of 5 done" on the weekly plan. |
| 2. Match with the real world | The student's own words: O/L, A/L, Z-score, cut-off, district, the real grade letters A/B/C/S/W, UGC course names. A "range" instead of a decimal error term. |
| 3. User control and freedom | Back on every step; edit any step from the review page; "Use my own answers" leaves example mode; "Start a new chat"; "Delete my answers". |
| 4. Consistency and standards | The same card, chip, button and "Next" bar on every page; the same colours always mean the same thing; menu groups match the journey. |
| 5. Error prevention | Only valid answers can be chosen (buttons, not typing); the district is a list; the results pages are locked until the profile is complete; delete asks for confirmation. |
| 6. Recognition rather than recall | All options are visible; the review page shows every answer; the journey pills show where you are; the example banner reminds that it is an example. |
| 7. Flexibility and efficiency | The menu can jump to any page; step pills jump to any step; example students skip typing; answers are remembered on the device. |
| 8. Aesthetic and minimalist design | Top-3 degree areas and top-3 suggestions; details hidden behind "Show…"; no decoration that carries no meaning. |
| 9. Help users recognise and recover from errors | A friendly message under each unanswered question ("Please answer this question.") plus a summary at the top; the page scrolls to the first one; "Try again" on a failed load. |
| 10. Help and documentation | The About and Help page with questions and answers; "What is a Z-score?" next to the number; "Why this?" on every suggestion; the chatbot. |

### 3.5 Gestalt principles

| Principle | Where |
|---|---|
| **Proximity** | Menu items in 4 groups (Start / My results / My plan / More); each question's options sit right under it; course name, university and cut-off sit together in one row. |
| **Common region** | Each idea in its own card (Z-score, band, degree areas); the weekly plan in its own box; the chatbot notice in its own coloured band. |
| **Similarity** | All status chips share one shape; all "up" bars are blue and all "down" bars are orange; all primary actions are blue pills. |
| **Continuity** | The numbered journey pills 1→5; the number line from 0.5 to 3.0; the dotted path in the logo and Home picture. |
| **Figure–ground** | The dawn hero stands out from the light page; dialogs dim the page behind them; the mobile menu dims the content. |

### 3.6 Hick's law (fewer choices = faster decisions)

- **One main button per screen.** "Start now", "Next" and "See my results" each appear as the single filled button. Other actions are outlined or text-only.
- **The menu is split into 4 small groups** instead of 9 loose links.
- **Each profile step asks at most 9 things** (6 steps instead of one page of 30 questions).
- **Lists are kept short.** Only the top 3 degree areas, the top 3 suggestions and a 5-item weekly plan are shown first. Statistics are split into 3 tabs.

### 3.7 Fitts's law (big, close targets are easier to hit)

- **Every button and answer is at least 48 × 48 px** (`--tap: 48px`). The language buttons are 44 px.
- **The main buttons are bigger:** "Start now", "Next" and "See my results" are 56 px tall.
- **Grade answers are 48 px squares in one row per subject.**
- **"Next" is always in the same place:** bottom right of the form, and at the end of each results page.
- **On phones, the menu opens from the top-left button.** Tapping outside closes it.

### 3.8 Miller's law (chunking, about 7 ± 2 items)

- **Questions:**
  - 30 questions in 6 chunks of 3–9;
  - the 12 attitude statements are split 4 + 4 + 4 across three steps;
  - O/L grades form one table of 9 subjects.
- **Explanations** use 5 question groups, not 34 single answers.
- **Menus and lists:** groups of 2–3 links; at most 5 items in the weekly plan.

### 3.9 Cognitive load reduction

- **Plain words and short sentences.** No jargon such as "SHAP", "calibration" or "macro F1" on student pages. These words appear only on the Statistics tab, with an explanation.
- **Numbers are rounded** (Z-scores to 2 decimals, chances to whole %). A **range** replaces an uncertain exact number.
- **The interface does the maths.** It says "0.11 to go" instead of asking the student to compare 1.42 with 1.53. It says "Your whole range is above" instead of asking them to read a chart.
- **Answers are remembered between visits.** The review page lets the student check everything at once.

### 3.10 Progressive disclosure

Details are hidden until the student asks for them:
- **My Prediction:** "What is a Z-score?", "Show all areas", and University region (collapsed, with a "Very rough guide" label).
- **My Target and Gap:** the course list.
- **Why This Result:** "Show single answers".
- **My Recommendations:** "Why this?" with the evidence, and "Show 8 more suggestions".
- **Statistics:** tabs, and "All 8 neural networks" collapsed.
- **About and Help:** the questions and answers as an accordion.

### 3.11 Other principles used

| Principle | Where |
|---|---|
| **Jakob's law** (use familiar patterns) | Top bar with logo, menu button on phones, side menu on desktop, tabs, progress bar, chat bubbles: patterns students already know from other apps. |
| **Von Restorff (isolation) effect** | The only amber button on Home is "Start now", so the eye goes there first. |
| **Goal-gradient and Zeigarnik effects** | The progress bar, "% done", ticks on finished steps, encouragement ("You're halfway there!"), and the "2 of 5 done" weekly checklist motivate finishing. |
| **Doherty threshold (fast feedback)** | Answer chips change at once on tap. Results show a loading card at once and are kept in memory for later pages. The language switch is instant. |
| **Serial-position effect** | The most important suggestion is shown first; the gap status opens the target page. |
| **Aesthetic–usability effect** | A calm, coherent dawn theme makes the tool feel trustworthy and pleasant for teenagers. |

### 3.12 Designing for 15–16 year olds

- **Non-judgmental wording:**
  - Bands are "Band 1 / 2 / 3", never "low";
  - a gap is "x to go";
  - the weak example is "still building up";
  - the question about a low result is answered with "A prediction is not your future".
- **Encouragement and achievement:** step messages, ticks, and "Brilliant! All steps done this week."
- **Privacy is said plainly:** "Your answers stay on this device", with a delete button on two pages.
- **Health:** advice about sleep, rest and family is built into the study-time tip. The 1926 helpline is on the Help page.
- **Example students** let a nervous student look around before answering.

## 4. Languages (English, Sinhala, Tamil)

- **Switching language:** the three buttons in the top bar (EN / සිං / த on phones) change every word at once. The choice is remembered on the device.
- **Sinhala survey questions** (attitudes, study hours, school type, rating, class rank, Science stream) use **the exact Sinhala wording of the original Google Form.** So Sinhala users answer the same questions the model learned from.
- **Tamil:** the form had no Tamil, so **all Tamil text is new and must be checked**, especially the 12 attitude statements.
- **What stays in English:** official UGC course and university names, and the chatbot's replies (with a visible note).
- **Recommendations in Sinhala and Tamil** are built from translated templates and the values sent by the backend. Their meaning matches the English rules.
- **`npm run check:i18n`** confirms that Sinhala and Tamil have all 491 text keys (0 missing, 0 unknown).

## 5. Privacy and data

- **The answers are kept only in the browser** (`localStorage`). They are sent to the local server only to work out results, and the server does not store them (Phase 9).
- **The Statistics page shows only aggregates.** Any group smaller than 10 students would be shown as "fewer than 10". The top Z-score bin was widened (2.25–2.75) so that no bar holds one person.
- **No outside services:** no web fonts, CDNs or tracking. The app works offline on the laptop.

## 6. Screenshots

All are made-up example students. Desktop is 1280 px wide; phone is 390 px.

| | |
|---|---|
| ![Home](phase10_screenshots/01_home.png) Home – dawn hero, one main action | ![Example students](phase10_screenshots/17_home_example_dialog.png) "Try an example student" |
| ![Profile step 1](phase10_screenshots/02_profile_step1.png) Profile step 1 | ![Grades](phase10_screenshots/03_profile_grades.png) O/L grades with progress and ticks |
| ![Missing answers](phase10_screenshots/04_profile_missing.png) Friendly error messages | ![Likert](phase10_screenshots/05_profile_likert.png) 1–5 statements |
| ![Review](phase10_screenshots/06_profile_review.png) Review before results | ![Prediction](phase10_screenshots/07_prediction.png) My Prediction |
| ![Target gap](phase10_screenshots/08_target_gap.png) My Target – gap | ![Target on track](phase10_screenshots/09_target_on_track.png) My Target – on track |
| ![Why](phase10_screenshots/10_why.png) Why This Result | ![Plan](phase10_screenshots/11_plan.png) My Recommendations |
| ![Chat](phase10_screenshots/12_chat.png) Chatbot with notice and safe reply | ![Statistics](phase10_screenshots/13_stats_data.png) Statistics – the survey |
| ![Statistics model](phase10_screenshots/14_stats_model.png) Statistics – how well it works | ![Statistics checks](phase10_screenshots/15_stats_checks.png) Statistics – checks |
| ![About](phase10_screenshots/16_about.png) About and Help | ![Sinhala home](phase10_screenshots/32_sinhala_home.png) Sinhala – Home |
| ![Sinhala prediction](phase10_screenshots/30_sinhala_prediction.png) Sinhala – Prediction | ![Tamil plan](phase10_screenshots/31_tamil_plan.png) Tamil – Recommendations |
| ![Phone home](phase10_screenshots/20_mobile_home.png) Phone – Home | ![Phone prediction](phase10_screenshots/21_mobile_prediction.png) Phone – Prediction |
| ![Phone menu](phase10_screenshots/22_mobile_menu.png) Phone – menu | ![Phone profile](phase10_screenshots/23_mobile_profile.png) Phone – O/L grades |
| ![Dark home](phase10_screenshots/40_dark_home.png) Dark – Home | ![Dark prediction](phase10_screenshots/41_dark_prediction.png) Dark – Prediction |
| ![Dark target](phase10_screenshots/42_dark_target.png) Dark – Target | ![Dark why](phase10_screenshots/43_dark_why.png) Dark – Why This Result |
| ![Dark plan](phase10_screenshots/44_dark_plan.png) Dark – Recommendations | ![Dark chat](phase10_screenshots/45_dark_chat.png) Dark – Chatbot |
| ![Dark profile](phase10_screenshots/46_dark_profile.png) Dark – O/L grades | ![Dark statistics](phase10_screenshots/47_dark_stats.png) Dark – Statistics |
| ![Dark phone target](phase10_screenshots/48_dark_mobile_target.png) Dark – Phone, Target | |

## 7. Problems found while building, and limitations

**Found and fixed using the screenshots:**
1. Error messages showed before any answer, because a CSS rule overrode `hidden`.
2. Degree bars were empty.
3. Cut-off labels overlapped. Now only the lowest cut-off is labelled; the others are thin ticks.
4. The plan page was too long (11 cards). Now the top 3 are shown and the rest are folded.
5. The phone language buttons were cut off. Now they show short labels.
6. Chart text was too small on phones.
7. The Home picture had hard edges. Now it sits in a round "dawn window".
8. The focus ring contrast was too low.
9. A broken script (from an editing slip) stopped the app. The test suite now checks the syntax of every script.

**Limitations:**
- **Translations are first drafts.** The Sinhala rest-of-app text and all Tamil text need your check. Sinhala question wording is from the form.
- **The 1–5 scales are labelled only at the ends** ("1 = Strongly disagree … 5 = Strongly agree"), as in the original form, so answers stay comparable.
  - **The Grades 6–11 rating** uses "Low / High" at its ends. The form gave no end labels, so this is my wording.
  - **Questions are reworded only lightly** for clarity (for example "study timetable" for "study schedule"). The meaning is unchanged; the Sinhala wording is the form's.
- **The questions keep the survey's past tense** ("During O/L, I was…"). This fits students who have just finished O/L.
- **Not yet tested with real students.** The user test (SUS, comprehension, chatbot clarity) is Phase 11.
- **Some text stays in English in all languages:** UGC course and university names, the hypothesis results on the Statistics "checks" tab, and the chatbot replies.

## 8. Tests

`python -m pytest`: **148 passed** (123 earlier, 22 in `tests/test_phase10.py`, and 3 for the university addition). The new tests check that:
- the interface and all its files are served;
- `/api/examples` and `/api/stats` work, and hypotheses H1–H12 are listed;
- statistics never show a group under 10;
- every text colour pair passes WCAG AA (4.5:1), and graphics and the focus ring pass 3:1;
- touch targets are 48 px;
- every Sinhala and Tamil key matches English (`node`);
- every script parses (`node --check`).

`ruff check .` passes. The browser-console check during screenshots found no errors.

## 9. What Phase 11 needs from you

1. **Check the Sinhala and Tamil text**, especially the 12 Tamil attitude statements. Edit `frontend/i18n/si.js` and `ta.js` directly, or send me corrections.
2. **Testers.** The user test with 5 recent O/L students needs:
   - a short session plan;
   - parental consent for minors;
   - the SUS questionnaire;
   - comprehension questions about "Why this result" (H10);
   - ratings of recommendations (H9) and of chatbot clarity.

   I will prepare these in Phase 11.
