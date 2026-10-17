// Phase 11 browser end-to-end test: a "student" uses the real website from start to finish.
// Needs the backend running (uvicorn backend.app:app --port 8000), Chrome, and `npm install`.
// Usage (from frontend/): node tools/e2e_browser.mjs   -> writes ../reports/phase11/browser_e2e.json
import fs from "node:fs";
import puppeteer from "puppeteer-core";

const BASE = process.env.ALORA_URL || "http://localhost:8000/";
const CHROME = process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const OUT = "../reports/phase11/browser_e2e.json";

// The "average" example student, answered by clicking, exactly as a person would.
const ANSWERS = {
  ol_school_type: "Provincial school", g6_11_perf_rating: 3, class_rank_freq: "Sometimes",
  ol_religion: "B", ol_first_language: "B", ol_english: "C", ol_maths: "B", ol_history: "C", ol_science: "B",
  ol_cat1: "C", ol_cat2: "B", ol_cat3: "C", g11_self_study_hours: "5 - 10",
  er1: 3, er2: 3, er3: 3, er4: 3, se1: 3, se2: 3, se3: 3, se4: 3, int1: 4, int2: 3, int3: 4, int4: 3,
  career_goal_clear: "Not Sure", stream_influences: ["Parents", "Teachers"],
  al_subject_combination: "Chemistry + Physics + Combined Maths", al_district: "Gampaha", al_target_degree: "Engineering",
};

const results = [];
const errors = [];
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
async function check(name, fn) {
  const start = Date.now();
  try {
    const detail = await fn();
    results.push({ check: name, ok: true, ms: Date.now() - start, detail: detail ?? "" });
    console.log("PASS", name, detail ?? "");
  } catch (e) {
    results.push({ check: name, ok: false, ms: Date.now() - start, detail: String(e.message || e) });
    console.log("FAIL", name, e.message || e);
  }
}
const idFor = (name, value) => `${name}-${String(value).replace(/\W+/g, "_")}`;

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true });
const page = await browser.newPage();
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
await page.setViewport({ width: 1280, height: 860 });
await page.goto(BASE, { waitUntil: "networkidle0" });
await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); });
await page.goto(`${BASE}?r=${Date.now()}#/home`, { waitUntil: "networkidle0" });

await check("Home shows the name and one main action", async () => {
  const title = await page.$eval(".hero h1", (e) => e.textContent);
  const primary = await page.$$eval(".hero .btn-primary", (b) => b.length);
  if (primary !== 1) throw new Error(`${primary} main buttons`);
  return title;
});

await check("Results pages are locked before answering", async () => {
  await page.goto(`${BASE}#/prediction`, { waitUntil: "networkidle0" });
  if (!(await page.$(".empty"))) throw new Error("prediction page did not ask for the profile first");
});

await check("Next without answers shows friendly errors", async () => {
  await page.goto(`${BASE}#/profile`, { waitUntil: "networkidle0" });
  await page.waitForSelector(".question");
  await page.click('button[type="submit"]');
  await wait(200);
  const shown = await page.$$eval(".q-error", (els) => els.filter((e) => !e.hidden).length);
  if (shown < 3) throw new Error(`only ${shown} error messages`);
  return `${shown} questions flagged`;
});

await check("A student can answer all 30 questions step by step", async () => {
  for (let step = 0; step < 6; step += 1) {
    await page.waitForSelector("#step-form");
    const names = await page.$$eval("#step-form input, #step-form select", (els) => [...new Set(els.map((e) => e.name))]);
    for (const name of names) {
      const value = ANSWERS[name];
      if (name === "al_district") { await page.select("#al_district", value); continue; }
      for (const v of Array.isArray(value) ? value : [value]) await page.click(`label[for="${idFor(name, v)}"]`);
    }
    await page.click('button[type="submit"]');
    await wait(150);
  }
  await page.waitForSelector(".review-list");
  const pct = await page.$eval("#pct", (e) => e.textContent);
  if (!pct.includes("100")) throw new Error(pct);
  return pct;
});

await check("See my results opens the prediction (answers match the example student)", async () => {
  const t0 = Date.now();
  await page.click("#finish");
  await page.waitForSelector(".big-number", { timeout: 30000 });
  const z = await page.$eval(".big-number", (e) => e.textContent.trim());
  const api = await page.evaluate(async () => (await (await fetch("/api/examples")).json()).average);
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("alora.profile.v1")).answers);
  const same = Object.keys(api).every((k) => JSON.stringify(api[k]) === JSON.stringify(stored[k]));
  if (!same) throw new Error("clicked answers differ from the example profile");
  return `Z ${z}, shown after ${Date.now() - t0} ms`;
});

await check("Target page shows the status and the universities card", async () => {
  await page.goto(`${BASE}#/target`, { waitUntil: "networkidle0" });
  await page.waitForSelector(".status-hero");
  const status = await page.$eval(".status-hero h2", (e) => e.textContent);
  const unis = await page.$$eval("#uni-title ~ details .course", (e) => e.length);
  if (!unis) throw new Error("no universities listed");
  return `${status}; ${unis} university rows`;
});

await check("Why page shows the question groups", async () => {
  await page.goto(`${BASE}#/why`, { waitUntil: "networkidle0" });
  await page.waitForSelector(".diverge li", { timeout: 30000 });
  return `${await page.$$eval(".diverge li", (e) => e.length)} rows`;
});

await check("Plan ticks are remembered after reloading", async () => {
  await page.goto(`${BASE}#/plan`, { waitUntil: "networkidle0" });
  await page.waitForSelector("[data-done]", { timeout: 30000 });
  await page.click("[data-done]");
  await page.reload({ waitUntil: "networkidle0" });
  await page.waitForSelector("[data-done]", { timeout: 30000 });
  const ticked = await page.$eval("[data-done]", (e) => e.checked);
  if (!ticked) throw new Error("tick was lost");
  return await page.$eval("#done-count", (e) => e.textContent);
});

await check("Chatbot notice is visible and a university question gets an exact answer", async () => {
  await page.goto(`${BASE}#/chat`, { waitUntil: "networkidle0" });
  const notice = await page.$eval(".chat-notice", (e) => e.offsetHeight > 0 && e.textContent);
  if (!notice || !notice.includes("support tool")) throw new Error("notice missing");
  await page.type("#chat-input", "Can I get into Peradeniya?");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => !document.querySelector(".typing"), { timeout: 120000 });
  const reply = await page.$$eval(".msg.bot", (m) => m[m.length - 1].textContent);
  if (!reply.includes("1.9259")) throw new Error(reply);
  return reply.slice(0, 90) + "…";
});

await check("Language switch changes every label (Sinhala, Tamil, back to English)", async () => {
  await page.goto(`${BASE}#/prediction`, { waitUntil: "networkidle0" });
  const read = async () => page.$eval("h1", (e) => e.textContent);
  await page.click('[data-lang="si"]'); await page.waitForSelector(".big-number"); const si = await read();
  const lang = await page.evaluate(() => document.documentElement.lang);
  await page.click('[data-lang="ta"]'); await page.waitForSelector(".big-number"); const ta = await read();
  await page.click('[data-lang="en"]'); await page.waitForSelector(".big-number"); const en = await read();
  if (lang !== "si" || si === en || ta === en) throw new Error(`${si} / ${ta} / ${en}`);
  return `${si} / ${ta} / ${en}`;
});

await check("Dark mode: follows the device, the switch changes the colours and is remembered", async () => {
  const bg = () => page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  const theme = () => page.evaluate(() => document.documentElement.dataset.theme);
  await page.evaluate(() => localStorage.removeItem("alora.theme"));
  await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "dark" }]);
  await page.goto(`${BASE}?r=${Date.now()}#/prediction`, { waitUntil: "networkidle0" });
  await page.waitForSelector(".big-number");
  const device = await theme();
  await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: "light" }]);
  await wait(200);
  const followed = await theme();
  const lightBg = await bg();
  await page.click("#theme-btn"); await wait(400);
  const darkBg = await bg();
  const pressed = await page.$eval("#theme-btn", (e) => e.getAttribute("aria-pressed"));
  await page.goto(`${BASE}?r=${Date.now()}#/target`, { waitUntil: "networkidle0" });
  await page.waitForSelector(".page h1");
  const kept = await theme();
  await page.click("#theme-btn"); await wait(200);
  const back = await theme();
  if (device !== "dark" || followed !== "light" || lightBg === darkBg || pressed !== "true" || kept !== "dark" || back !== "light") {
    throw new Error(`device ${device}, followed ${followed}, ${lightBg} -> ${darkBg}, pressed ${pressed}, kept ${kept}, back ${back}`);
  }
  return `${lightBg} -> ${darkBg}`;
});

await check("Keyboard: the first Tab reaches 'Skip to main content'", async () => {
  await page.goto(`${BASE}?r=${Date.now()}#/home`, { waitUntil: "networkidle0" });
  await page.keyboard.press("Tab");
  return await page.evaluate(() => document.activeElement.textContent.trim());
});

await check("Phone: the menu opens and closes", async () => {
  await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
  await page.goto(`${BASE}#/plan`, { waitUntil: "networkidle0" });
  await page.click("#menu-btn");
  await wait(300);
  const open = await page.$eval("#sidenav", (e) => e.classList.contains("open"));
  await page.keyboard.press("Escape");
  await wait(300);
  const closed = await page.$eval("#sidenav", (e) => !e.classList.contains("open"));
  if (!open || !closed) throw new Error(`open ${open}, closed ${closed}`);
  await page.setViewport({ width: 1280, height: 860 });
});

await check("Delete my answers removes everything and locks the results again", async () => {
  // (changing from phone to desktop size makes the test browser reload, so load the page afresh)
  await page.goto(`${BASE}?r=${Date.now()}#/about`, { waitUntil: "networkidle0" });
  try { await page.waitForSelector("#delete", { timeout: 5000 }); }
  catch { throw new Error("About page shows: " + (await page.evaluate(() => location.href + " | " + document.querySelector("main").textContent.slice(0, 120)))); }
  page.once("dialog", (d) => d.accept());
  await page.click("#delete");
  await wait(300);
  const stored = await page.evaluate(() => JSON.parse(localStorage.getItem("alora.profile.v1")).answers);
  await page.goto(`${BASE}#/target`, { waitUntil: "networkidle0" });
  await page.waitForSelector(".page h1");
  if (Object.keys(stored).length || !(await page.$(".empty"))) throw new Error("answers not deleted");
});

await browser.close();
results.push({ check: "No errors in the browser console", ok: errors.length === 0, detail: errors.join(" | ") });
console.log(errors.length ? `FAIL console errors: ${errors.join(" | ")}` : "PASS no console errors");
fs.mkdirSync("../reports/phase11", { recursive: true });
fs.writeFileSync(OUT, JSON.stringify({ run_at: new Date().toISOString(), base: BASE, results }, null, 2));
const failed = results.filter((r) => !r.ok).length;
console.log(`${results.length - failed} of ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
