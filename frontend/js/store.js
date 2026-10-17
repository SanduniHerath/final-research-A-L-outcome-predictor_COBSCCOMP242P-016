// The student's answers are kept in this browser (localStorage) so the form can be continued.
// The server also saves them, with the results, in the app database (see api.js).
import { api } from "./api.js";

const KEY = "alora.profile.v1";
const LANG = "alora.lang";
const DONE = "alora.plan.done";
const THEME = "alora.theme";  // "light" | "dark" | null (= follow the device); kept when answers are deleted

function read(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
function write(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode: keep in memory */ }
}

let memory = read(KEY, { answers: {}, step: 0, complete: false, example: null });

export const store = {
  get answers() { return memory.answers; },
  get step() { return memory.step; },
  get complete() { return memory.complete; },
  get example() { return memory.example; },
  get started() { return Object.keys(memory.answers).length > 0; },
  set(name, value) { memory.answers = { ...memory.answers, [name]: value }; memory.complete = false; memory.example = null; this.save(); },
  setStep(step) { memory.step = step; this.save(); },
  finish() { memory.complete = true; this.save(); api.clear(); },
  load(answers, example = null) { memory = { answers: { ...answers }, step: 0, complete: true, example }; this.save(); api.clear(); },
  reset() { memory = { answers: {}, step: 0, complete: false, example: null }; this.save(); api.clear(); try { localStorage.removeItem(DONE); } catch { /* ignore */ } },
  save() { write(KEY, memory); },
  get lang() { return read(LANG, "en"); },
  set lang(value) { write(LANG, value); },
  get theme() { return read(THEME, null); },
  set theme(value) { write(THEME, value); },
  get done() { return read(DONE, {}); },
  setDone(id, value) { const d = this.done; d[id] = value; write(DONE, d); },
};
