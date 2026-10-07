/**
 * Alora - user-test questionnaire as a Google Form (Phase 11).
 * Same questions as docs/user_testing/04_questionnaire.md.
 *
 * HOW TO USE
 * 1. Go to https://script.google.com and click "New project".
 * 2. Delete the example code, paste this whole file, and click Save.
 * 3. Choose the function "createAloraForm" at the top and click Run.
 *    The first time, Google asks for permission: click "Review permissions" and allow.
 * 4. Open "Execution log" (View > Logs). It shows three links:
 *      - the form to EDIT (check it once),
 *      - the form to FILL IN (open this on the test laptop),
 *      - the response spreadsheet.
 * 5. AFTER the sessions: choose "exportForScoring" and click Run. The response spreadsheet then has
 *    three new tabs: sus, comprehension, ratings, in the exact columns that
 *    src/evaluation/user_test.py reads.
 *      - In the "comprehension" tab, type 1 (correct) or 0 (wrong) in "b3_correct" for every tester,
 *        after checking their B3 answer (column "b3_answer") against their own screen or notes.
 *      - Download each tab with File > Download > Comma-separated values (.csv) and save it as
 *        data/user_test/sus.csv, comprehension.csv and ratings.csv.
 *      - tasks.csv and expert.csv come from the paper observation sheet and expert form.
 *    Then run:  python -m src.evaluation.user_test
 *
 * PRIVACY (the testers are minors)
 * - No names and no e-mail addresses are collected; testers are identified only by a code (T1, T2...).
 *   Do not put real names anywhere in the form or the spreadsheet.
 * - Testers cannot see other people's answers (no summary page).
 * - Keep the response spreadsheet private (do not share the link), and delete it when the study ends,
 *   following your consent form.
 */

const FORM_TITLE = 'Alora - questionnaire for testers';
const SHEET_TITLE = 'Alora - user test responses';
const AGREE = ['Strongly disagree', 'Strongly agree'];

// Every question, in order. "key" is the column name used by the scoring script.
// "codes" turns an answer into the value the script expects (for example "Stay on track" -> "strengthen").
const PAGES = [
  {
    title: 'For the researcher (fill in before giving the laptop to the tester)',
    help: 'The tester does not answer this page.',
    items: [
      { key: 'tester', type: 'code', title: 'R1. Tester code (for example T1). No names.' },
      { key: 'language', type: 'choice', title: 'R2. Language the tester used in the app',
        codes: { 'English': 'en', 'Sinhala': 'si', 'Tamil': 'ta' } },
      { key: 'own_mode', type: 'choice', title: "R3. Mode of the tester's own study plan",
        codes: { 'Close the gap': 'close_the_gap', 'Stay on track': 'strengthen' } },
      { key: 'example_mode', type: 'choice', title: "R4. Mode of the example student's plan you showed",
        codes: { 'Close the gap': 'close_the_gap', 'Stay on track': 'strengthen' } },
    ],
  },
  {
    title: 'Welcome',
    help: 'Thank you for helping us test Alora! There are no right or wrong answers about what you like. ' +
      'Part B checks whether the app explained things clearly, NOT what you know. Please do not write your name anywhere.',
    items: [
      { key: 'assent', type: 'choice', title: 'I agree to answer these questions. I know I can stop at any time.',
        codes: { 'Yes, I agree': 'yes' } },
    ],
  },
  {
    title: 'Part A - Using Alora',
    help: 'Choose one number for each sentence. 1 = strongly disagree, 5 = strongly agree. Answer quickly, with your first feeling.',
    items: [
      { key: 'a1', type: 'scale', title: 'A1. I think that I would like to use this app often.' },
      { key: 'a2', type: 'scale', title: 'A2. I found the app unnecessarily complicated.' },
      { key: 'a3', type: 'scale', title: 'A3. I thought the app was easy to use.' },
      { key: 'a4', type: 'scale', title: 'A4. I think that I would need help from a technical person to use this app.' },
      { key: 'a5', type: 'scale', title: 'A5. I found the different parts of this app worked well together.' },
      { key: 'a6', type: 'scale', title: 'A6. I thought there was too much inconsistency in this app.' },
      { key: 'a7', type: 'scale', title: 'A7. I would imagine that most people would learn to use this app very quickly.' },
      { key: 'a8', type: 'scale', title: 'A8. I found the app very awkward to use.' },
      { key: 'a9', type: 'scale', title: 'A9. I felt very confident using the app.' },
      { key: 'a10', type: 'scale', title: 'A10. I needed to learn a lot of things before I could get going with this app.' },
    ],
  },
  {
    title: 'Part B - Understanding "Why This Result"',
    help: 'Choose ONE answer for each question.',
    items: [
      { key: 'b1', type: 'letters', title: 'B1. On the "Why This Result" page, a blue bar with ▲ next to a group of answers means:',
        options: ['a) you answered those questions correctly',
          'b) that group of answers raised your predicted Z-score compared with a typical student',
          'c) those subjects are your best subjects in A/L'] },
      { key: 'b2', type: 'letters', title: 'B2. The app says: "Your O/L results lowered your predicted Z-score by about 0.15." This means:',
        options: ['a) your A/L result will be exactly 0.15 lower',
          'b) your O/L grades were marked wrongly',
          'c) compared with a typical student in the survey, your O/L results are linked to a prediction about 0.15 lower'] },
      { key: 'b3_answer', type: 'text', title: 'B3. Look at your own "Why This Result" page. Which group of answers moved your predicted Z-score the most?',
        help: 'Write it in your own words. The researcher checks it against your screen.' },
      { key: 'b4', type: 'letters', title: 'B4. Does the "Why This Result" page prove that your study habits cause your Z-score?',
        options: ['a) Yes, it proves it',
          "b) No. It shows patterns in other students' answers, not proof of cause",
          'c) Only for students with good results'] },
      { key: 'b5', type: 'letters', title: 'B5. Which of these can you still work on to improve, according to the app?',
        options: ['a) your O/L grades', 'b) your study habits', 'c) the type of school you went to'] },
      { key: 'b6', type: 'letters', title: 'B6. The app compares you with a "typical student". This is:',
        options: ['a) an average student from the survey the app learned from',
          'b) the best student in your class', 'c) a student from your own school'] },
      { key: 'b7', type: 'letters', title: 'B7. Under "Why [degree area]?", a bar says ▲ +40 for "Your A/L subject choice". This means:',
        options: ['a) you need 40 more marks in A/L',
          'b) your A/L subject choice raised the chance of that degree area by about 40 percentage points',
          'c) 40 students chose the same subjects'] },
      { key: 'b8', type: 'letters', title: 'B8. If some single answers seem to point the "wrong" way, what does the app tell you to do?',
        options: ['a) Look at the groups of answers first', 'b) Answer the questions again', 'c) Ignore the whole page'] },
    ],
  },
  {
    title: 'Part C - The study plan',
    help: 'Answer first for YOUR OWN plan, then for the EXAMPLE STUDENT the researcher showed you. 1 = strongly disagree, 5 = strongly agree.',
    items: [
      { key: 'own_c1', type: 'scale', title: 'C1 (my own plan). This study plan would be useful for a student like this.' },
      { key: 'own_c2', type: 'scale', title: 'C2 (my own plan). The suggestions are clear and easy to understand.' },
      { key: 'own_c3', type: 'scale', title: 'C3 (my own plan). I would try at least one of the steps.' },
      { key: 'own_c4', type: 'scale', title: 'C4 (my own plan). The suggestions are suitable for someone my age.' },
      { key: 'ex_c1', type: 'scale', title: "C1 (example student's plan). This study plan would be useful for a student like this." },
      { key: 'ex_c2', type: 'scale', title: "C2 (example student's plan). The suggestions are clear and easy to understand." },
      { key: 'ex_c3', type: 'scale', title: "C3 (example student's plan). I would try at least one of the steps." },
      { key: 'ex_c4', type: 'scale', title: "C4 (example student's plan). The suggestions are suitable for someone my age." },
    ],
  },
  {
    title: 'Part D - The chatbot',
    help: '1 = strongly disagree, 5 = strongly agree.',
    items: [
      { key: 'd1', type: 'scale', title: "D1. The chatbot's answers were clear." },
      { key: 'd2', type: 'scale', title: "D2. The chatbot's answers were about my own results." },
      { key: 'd3_noticed', type: 'choice', title: 'D3. I noticed the message that the chatbot is a support tool, not a final decision maker.',
        codes: { 'Yes': 'yes', 'No': 'no' } },
    ],
  },
  {
    title: 'Part E - In your own words',
    help: 'Write as much or as little as you like. These questions are optional.',
    items: [
      { key: 'e1', type: 'text', optional: true, title: 'E1. What did you like most about Alora?' },
      { key: 'e2', type: 'text', optional: true, title: 'E2. What was confusing or hard?' },
      { key: 'e3', type: 'text', optional: true, title: 'E3. What would you change or add?' },
      { key: 'e4', type: 'choice', optional: true, title: 'E4. Which language would you use the app in?',
        codes: { 'English': 'en', 'Sinhala': 'si', 'Tamil': 'ta' } },
      { key: 'e5', type: 'choice', optional: true, title: 'E5. Was the text in that language easy to understand?',
        codes: { 'Yes': 'yes', 'Partly': 'partly', 'No': 'no' } },
    ],
  },
];

// Columns of the three CSV files read by src/evaluation/user_test.py (extra columns are ignored by it).
const EXPORTS = {
  sus: ['tester', 'a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 'a8', 'a9', 'a10'],
  comprehension: ['tester', 'b1', 'b2', 'b3_correct', 'b4', 'b5', 'b6', 'b7', 'b8', 'b3_answer'],
  ratings: ['tester', 'own_mode', 'own_c1', 'own_c2', 'own_c3', 'own_c4', 'example_mode', 'ex_c1', 'ex_c2',
    'ex_c3', 'ex_c4', 'd1', 'd2', 'd3_noticed', 'language'],
  open_answers: ['tester', 'e1', 'e2', 'e3', 'e4', 'e5'],
};

function createAloraForm() {
  const form = FormApp.create(FORM_TITLE);
  form.setDescription('Alora user test. Takes about 10 minutes. Please do not write your name.')
    .setCollectEmail(false)
    .setProgressBar(true)
    .setPublishingSummary(false)
    .setAllowResponseEdits(false)
    .setShowLinkToRespondAgain(true) // the same laptop is used for the next tester
    .setConfirmationMessage('Thank you very much! Please give the laptop back to the researcher.');

  PAGES.forEach(function (page, index) {
    if (index > 0) form.addPageBreakItem().setTitle(page.title).setHelpText(page.help);
    else form.addSectionHeaderItem().setTitle(page.title).setHelpText(page.help);
    page.items.forEach(function (q) { addItem(form, q); });
  });

  const sheet = SpreadsheetApp.create(SHEET_TITLE);
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());
  PropertiesService.getScriptProperties().setProperty('FORM_ID', form.getId());

  Logger.log('Edit the form:      ' + form.getEditUrl());
  Logger.log('Fill in the form:   ' + form.getPublishedUrl());
  Logger.log('Response sheet:     ' + sheet.getUrl());
}

function addItem(form, q) {
  const required = !q.optional;
  if (q.type === 'scale') {
    form.addScaleItem().setTitle(q.title).setBounds(1, 5).setLabels(AGREE[0], AGREE[1]).setRequired(required);
  } else if (q.type === 'letters') {
    form.addMultipleChoiceItem().setTitle(q.title).setChoiceValues(q.options).setRequired(required);
  } else if (q.type === 'choice') {
    form.addMultipleChoiceItem().setTitle(q.title).setChoiceValues(Object.keys(q.codes)).setRequired(required);
  } else if (q.type === 'code') {
    const rule = FormApp.createTextValidation().requireTextMatchesPattern('^[Tt][0-9]+$')
      .setHelpText('Use a code like T1, T2... (no names).').build();
    form.addTextItem().setTitle(q.title).setValidation(rule).setRequired(true);
  } else {
    const item = form.addParagraphTextItem().setTitle(q.title).setRequired(required);
    if (q.help) item.setHelpText(q.help);
  }
}

// Turn one answer into the value the scoring script expects.
function toValue(q, answer) {
  if (q.type === 'scale') return Number(answer);
  if (q.type === 'letters') return String(answer).charAt(0); // "b) ..." -> "b"
  if (q.type === 'choice') return q.codes[answer] || answer;
  if (q.type === 'code') return String(answer).trim().toUpperCase();
  return answer;
}

function exportForScoring() {
  const formId = PropertiesService.getScriptProperties().getProperty('FORM_ID');
  if (!formId) throw new Error('Run createAloraForm first (it remembers which form to export).');
  const form = FormApp.openById(formId);
  const spreadsheet = SpreadsheetApp.openById(form.getDestinationId());

  const byTitle = {};
  PAGES.forEach(function (page) { page.items.forEach(function (q) { byTitle[q.title] = q; }); });

  // One row per tester; if a tester code was submitted twice, the LATER submission is kept.
  const testers = {};
  form.getResponses().forEach(function (response) {
    const row = {};
    response.getItemResponses().forEach(function (itemResponse) {
      const q = byTitle[itemResponse.getItem().getTitle()];
      if (q) row[q.key] = toValue(q, itemResponse.getResponse());
    });
    if (row.tester) testers[row.tester] = row;
  });
  const rows = Object.keys(testers).sort().map(function (code) { return testers[code]; });

  Object.keys(EXPORTS).forEach(function (name) {
    const columns = EXPORTS[name];
    const tab = spreadsheet.getSheetByName(name) || spreadsheet.insertSheet(name);
    tab.clear();
    const values = [columns].concat(rows.map(function (row) {
      return columns.map(function (c) { return row[c] === undefined ? '' : row[c]; });
    }));
    tab.getRange(1, 1, values.length, columns.length).setValues(values);
    tab.setFrozenRows(1);
  });
  Logger.log('Exported ' + rows.length + ' testers. Now fill in b3_correct (1 or 0) in the "comprehension" tab, ' +
    'then download the sus, comprehension and ratings tabs as CSV into data/user_test/.');
}
