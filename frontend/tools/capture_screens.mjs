// Phase 10 screenshots for docs/phase10_screenshots.
// Needs the backend running (uvicorn backend.app:app --port 8000), Google Chrome, and
// "npm install" in frontend/ (installs puppeteer-core only; it uses the installed Chrome).
// Usage (from frontend/): node tools/capture_screens.mjs ../docs/phase10_screenshots [name filters...]
import puppeteer from "puppeteer-core";
import fs from "node:fs";

const OUT = process.argv[2] || "out";
const ONLY = process.argv.slice(3);
fs.mkdirSync(OUT, { recursive: true });
const BASE = "http://localhost:8000/";
const CHROME = process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe";

const SHOTS = [
  { name: "01_home", url: "#/home", fresh: true },
  { name: "02_profile_step1", url: "#/profile", fresh: true },
  { name: "03_profile_grades", url: "#/profile", fresh: true, action: "grades" },
  { name: "04_profile_missing", url: "#/profile", fresh: true, action: "missing" },
  { name: "05_profile_likert", url: "#/profile", demo: "average", action: "step4" },
  { name: "06_profile_review", url: "#/profile", demo: "average", action: "review" },
  { name: "07_prediction", url: "#/prediction", demo: "average" },
  { name: "08_target_gap", url: "#/target", demo: "average" },
  { name: "09_target_on_track", url: "#/target", demo: "strong" },
  { name: "10_why", url: "#/why", demo: "average", action: "openDetails" },
  { name: "11_plan", url: "#/plan", demo: "weak" },
  { name: "12_chat", url: "#/chat", demo: "average", action: "chat" },
  { name: "16_about", url: "#/about" },
  { name: "17_home_example_dialog", url: "#/home", fresh: true, action: "dialog" },
  { name: "20_mobile_home", url: "#/home", fresh: true, mobile: true },
  { name: "21_mobile_prediction", url: "#/prediction", demo: "average", mobile: true },
  { name: "22_mobile_menu", url: "#/target", demo: "average", mobile: true, action: "menu" },
  { name: "23_mobile_profile", url: "#/profile", demo: "weak", mobile: true, action: "grades2" },
  { name: "30_sinhala_prediction", url: "#/prediction", demo: "average", lang: "si" },
  { name: "31_tamil_plan", url: "#/plan", demo: "weak", lang: "ta" },
  { name: "32_sinhala_home", url: "#/home", fresh: true, lang: "si" },
  { name: "40_dark_home", url: "#/home", fresh: true, theme: "dark" },
  { name: "41_dark_prediction", url: "#/prediction", demo: "average", theme: "dark" },
  { name: "42_dark_target", url: "#/target", demo: "average", theme: "dark" },
  { name: "43_dark_why", url: "#/why", demo: "average", theme: "dark" },
  { name: "44_dark_plan", url: "#/plan", demo: "weak", theme: "dark" },
  { name: "45_dark_chat", url: "#/chat", demo: "average", theme: "dark", action: "chat" },
  { name: "46_dark_profile", url: "#/profile", fresh: true, theme: "dark", action: "grades" },
  { name: "48_dark_mobile_target", url: "#/target", demo: "average", mobile: true, theme: "dark" },
];

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ["--no-sandbox", "--lang=en-GB"] });
const errors = [];
for (const s of SHOTS.filter((s) => !ONLY.length || ONLY.some((o) => s.name.includes(o)))) {
  const page = await browser.newPage();
  page.on("console", (m) => { if (m.type() === "error") errors.push(`${s.name}: ${m.text()}`); });
  page.on("pageerror", (e) => errors.push(`${s.name}: ${e.message}`));
  await page.setViewport(s.mobile ? { width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true } : { width: 1280, height: 860, deviceScaleFactor: 1 });
  await page.goto(BASE, { waitUntil: "networkidle0" });
  await page.evaluate((lang, theme) => { localStorage.clear(); sessionStorage.clear(); localStorage.setItem("alora.lang", JSON.stringify(lang)); localStorage.setItem("alora.theme", JSON.stringify(theme)); }, s.lang || "en", s.theme || "light");
  const q = `?r=${Date.now()}` + (s.demo ? `&demo=${s.demo}` : "");  // new query = full reload
  await page.goto(`${BASE}${q}${s.url}`, { waitUntil: "networkidle0" });
  await page.waitForFunction(() => !document.querySelector(".spinner"), { timeout: 60000 });
  await wait(300);
  await page.waitForSelector(".page h1", { timeout: 60000 });
  if (s.url === "#/profile") await page.waitForSelector(".question, .review-list", { timeout: 60000 });
  await wait(300);
  const a = s.action;
  if (a === "grades") {
    for (const sel of ['#ol_school_type-National_school', '#g6_11_perf_rating-4', '#class_rank_freq-Often']) await page.click(`label[for="${sel.slice(1)}"]`);
    await page.click('button[type="submit"]'); await wait(300);
    for (const [g, v] of [["ol_religion", "A"], ["ol_first_language", "B"], ["ol_english", "B"], ["ol_maths", "A"]]) await page.click(`label[for="${g}-${v}"]`);
  }
  if (a === "missing") { await page.click('label[for="ol_school_type-National_school"]'); await page.click('button[type="submit"]'); await wait(400); }
  if (a === "step4") { await page.evaluate(() => { document.querySelectorAll("[data-goto]")[3].click(); }); await wait(300); }
  if (a === "review") { await page.evaluate(() => { const s = JSON.parse(localStorage.getItem("alora.profile.v1")); s.step = 6; localStorage.setItem("alora.profile.v1", JSON.stringify(s)); }); await page.goto(`${BASE}#/home`); await page.goto(`${BASE}#/profile`, { waitUntil: "networkidle0" }); await wait(400); }
  if (a === "grades2") { await page.evaluate(() => { document.querySelectorAll("[data-goto]")[1].click(); }); await wait(300); }
  if (a === "openDetails") { await page.evaluate(() => document.querySelectorAll("details.more").forEach((d) => (d.open = true))); }
  if (a === "dialog") { await page.click("#try-example"); await wait(300); }
  if (a === "menu") { await page.click("#menu-btn"); await wait(400); }
  if (a?.startsWith("tab-")) { await page.click(`#${a}`); await wait(300); }
  if (a === "chat") {
    await page.click("#suggest button");
    await page.waitForFunction(() => !document.querySelector(".typing"), { timeout: 120000 });
    await page.type("#chat-input", "Which tablets help me study longer?");
    await page.keyboard.press("Enter");
    await page.waitForFunction(() => !document.querySelector(".typing"), { timeout: 120000 });
    await wait(300);
  }
  if (!["menu", "dialog", "chat"].includes(a)) await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `${OUT}/${s.name}.png`, fullPage: !["menu", "dialog", "chat"].includes(a) });
  console.log("saved", s.name);
  await page.close();
}
await browser.close();
console.log(errors.length ? "ERRORS:\n" + errors.join("\n") : "no console errors");
