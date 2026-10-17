// My Profile: step-by-step questions with a progress bar (one small group of questions per screen).
import { api } from "../api.js";
import { label, t } from "../i18n.js";
import { icon } from "../icons.js";
import { store } from "../store.js";
import { announce, esc, exampleBanner, pageHead, toast } from "../ui.js";

const GRADES = ["ol_religion", "ol_first_language", "ol_english", "ol_maths", "ol_history", "ol_science", "ol_cat1", "ol_cat2", "ol_cat3"];
const STEPS = [
  [{ name: "ol_school_type", kind: "choice", col: true }, { name: "g6_11_perf_rating", kind: "rating" }, { name: "class_rank_freq", kind: "choice" }],
  [{ kind: "grades" }],
  [{ name: "g11_self_study_hours", kind: "choice", col: true, hint: true }, { kind: "likert", fields: ["er1", "er2", "er3", "er4"] }],
  [{ kind: "likert", fields: ["se1", "se2", "se3", "se4"] }],
  [{ kind: "likert", fields: ["int1", "int2", "int3", "int4"] }, { name: "career_goal_clear", kind: "choice" }, { name: "stream_influences", kind: "multi" }],
  [{ name: "al_subject_combination", kind: "choice", col: true }, { name: "al_district", kind: "select" }, { name: "al_target_degree", kind: "choice", col: true }],
];
const NUMERIC = new Set(["g6_11_perf_rating", "se1", "se2", "se3", "se4", "er1", "er2", "er3", "er4", "int1", "int2", "int3", "int4"]);

function fieldsOf(step) {
  return STEPS[step].flatMap((q) => (q.kind === "grades" ? GRADES : q.kind === "likert" ? q.fields : [q.name]));
}
const ALL_FIELDS = STEPS.flatMap((_, i) => fieldsOf(i));

function answered(name) {
  const v = store.answers[name];
  return Array.isArray(v) ? v.length > 0 : v !== undefined && v !== null && v !== "";
}

function radio(name, value, text, extraClass = "") {
  const id = `${name}-${String(value).replace(/\W+/g, "_")}`;
  const checked = String(store.answers[name]) === String(value);
  return `<div class="option ${extraClass}"><input type="radio" id="${id}" name="${name}" value="${esc(value)}" ${checked ? "checked" : ""}>
    <label for="${id}"><span class="tick">${icon("check", "icon icon-sm")}</span>${esc(text)}</label></div>`;
}

function scaleQuestion(name, text, low, high) {
  return `<fieldset class="question" data-q="${name}"><legend>${esc(text)}</legend>
    <div class="scale" role="radiogroup">${[1, 2, 3, 4, 5].map((v) => radio(name, v, v)).join("")}</div>
    <div class="scale-ends" aria-hidden="true"><span>1 = ${esc(low)}</span><span>5 = ${esc(high)}</span></div>
    <div class="q-error" hidden>${icon("alert", "icon icon-sm")}${esc(t("profile.missing"))}</div></fieldset>`;
}

function renderQuestion(q, options) {
  if (q.kind === "grades") {
    return `<fieldset class="question" data-q="grades"><legend>${esc(t("q.grades"))}</legend>
      <p class="hint">${esc(t("q.gradesHint"))}</p>
      ${GRADES.map((g) => `<div class="grade-row" data-q="${g}" role="radiogroup" aria-label="${esc(t(`subj.${g}`))}">
        <div class="subject">${esc(t(`subj.${g}`))}${t(`subj.${g}H`) !== `subj.${g}H` ? `<small>${esc(t(`subj.${g}H`))}</small>` : ""}</div>
        <div class="options">${["A", "B", "C", "S", "W"].map((v) => radio(g, v, v)).join("")}</div></div>`).join("")}
      <div class="q-error" hidden>${icon("alert", "icon icon-sm")}${esc(t("profile.missing"))}</div></fieldset>`;
  }
  if (q.kind === "likert") {
    return `<p class="hint"><strong>${esc(t("profile.likertIntro"))}</strong></p>` +
      q.fields.map((f) => scaleQuestion(f, t(`q.${f}`), t("profile.scaleLow"), t("profile.scaleHigh"))).join("");
  }
  if (q.kind === "rating") return scaleQuestion(q.name, t(`q.${q.name}`), t("profile.ratingLow"), t("profile.ratingHigh"));
  const opts = options[q.name] || [];
  const hint = q.hint ? `<p class="hint">${esc(t(`q.${q.name}Hint`))}</p>` : "";
  const error = `<div class="q-error" hidden>${icon("alert", "icon icon-sm")}${esc(t("profile.missing"))}</div>`;
  if (q.kind === "select") {
    return `<div class="question" data-q="${q.name}"><label class="q-label" for="${q.name}">${esc(t(`q.${q.name}`))}</label><br>
      <select class="input" id="${q.name}" name="${q.name}">
        <option value="">${esc(t("profile.selectPlaceholder"))}</option>
        ${opts.map((o) => `<option value="${esc(o)}" ${store.answers[q.name] === o ? "selected" : ""}>${esc(label("district", o))}</option>`).join("")}
      </select>${error}</div>`;
  }
  if (q.kind === "multi") {
    const chosen = store.answers[q.name] || [];
    return `<fieldset class="question" data-q="${q.name}"><legend>${esc(t(`q.${q.name}`))}</legend>
      <p class="hint">${esc(t("profile.chooseAll"))}</p><div class="options">
      ${opts.map((o) => {
        const id = `${q.name}-${o.replace(/\W+/g, "_")}`;
        return `<div class="option"><input type="checkbox" id="${id}" name="${q.name}" value="${esc(o)}" ${chosen.includes(o) ? "checked" : ""}>
          <label for="${id}"><span class="tick">${icon("check", "icon icon-sm")}</span>${esc(label("opt", o, q.name))}</label></div>`;
      }).join("")}</div>${error}</fieldset>`;
  }
  return `<fieldset class="question" data-q="${q.name}"><legend>${esc(t(`q.${q.name}`))}</legend>${hint}
    <div class="options ${q.col ? "col" : ""}" role="radiogroup">${opts.map((o) => radio(q.name, o, label("opt", o, q.name))).join("")}</div>${error}</fieldset>`;
}

function progressHtml(step) {
  const done = ALL_FIELDS.filter(answered).length;
  const pctDone = Math.round((done / ALL_FIELDS.length) * 100);
  const total = STEPS.length;
  const title = step < total ? t("profile.stepOf", { n: step + 1, total }) : t("profile.review");
  return `<div class="progress-wrap">
    <div class="progress-label"><span>${esc(title)}</span><span class="num" id="pct">${esc(t("profile.percent", { p: pctDone }))}</span></div>
    <div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pctDone}" aria-label="${esc(t("profile.percent", { p: pctDone }))}"><span style="width:${pctDone}%"></span></div>
    <div class="step-dots">${STEPS.map((_, i) => {
      const complete = fieldsOf(i).every(answered);
      return `<button type="button" class="step-dot ${complete ? "done" : ""}" data-goto="${i}" ${i === step ? 'aria-current="step"' : ""}>
        ${complete ? icon("check", "icon icon-sm") : `<span>${i + 1}</span>`}<span class="step-name">${esc(t("profile.steps")[i])}</span></button>`;
    }).join("")}</div></div>`;
}

function reviewHtml(options) {
  const value = (f) => {
    const v = store.answers[f];
    if (Array.isArray(v)) return v.map((x) => label("opt", x, f)).join(", ");
    if (f === "al_district") return label("district", v);
    if (GRADES.includes(f) || NUMERIC.has(f)) return v;
    return label("opt", v, f);
  };
  const short = (f) => (GRADES.includes(f) ? t(`subj.${f}`) : t(`q.${f}`));
  return `<div class="card"><h2>${esc(t("profile.review"))}</h2><p class="muted">${esc(t("profile.reviewSub"))}</p>
    ${STEPS.map((_, i) => `<details class="more" ${i === 0 ? "open" : ""}><summary>${icon("chev", "icon chev")}${esc(t("profile.steps")[i])}</summary>
      <dl class="review-list">${fieldsOf(i).map((f) => `<dt>${esc(short(f))}</dt><dd>${esc(value(f) ?? "—")}</dd>`).join("")}</dl>
      <div class="actions"><button type="button" class="btn btn-quiet" data-goto="${i}">${icon("edit")} ${esc(t("common.change"))}</button></div></details>`).join("")}
    <div class="actions between"><button type="button" class="btn btn-secondary" id="back">${icon("left")} ${esc(t("common.back"))}</button>
      <button type="button" class="btn btn-primary btn-lg" id="finish">${esc(t("profile.seeResults"))} ${icon("right")}</button></div></div>`;
}

export async function render(root) {
  const questions = await api.questions();
  const options = Object.fromEntries(questions.map((q) => [q.name, q.options]));
  let step = Math.min(store.step, STEPS.length);

  const draw = () => {
    const body = step < STEPS.length
      ? `<form class="card" id="step-form" novalidate>
          <h2>${icon(["home", "book", "clock", "sparkle", "compass", "flag"][step])} ${esc(t("profile.steps")[step])}</h2>
          <div class="note warn" id="summary-error" role="alert" hidden>${icon("alert")}${esc(t("profile.missingSummary"))}</div><br>
          ${STEPS[step].map((q) => renderQuestion(q, options)).join("")}
          <div class="encourage" id="encourage" aria-live="polite"></div>
          <div class="actions between">
            ${step > 0 ? `<button type="button" class="btn btn-secondary" id="back">${icon("left")} ${esc(t("common.back"))}</button>` : "<span></span>"}
            <button type="submit" class="btn btn-primary btn-lg">${esc(t("common.next"))} ${icon("right")}</button>
          </div></form>`
      : reviewHtml(options);
    root.innerHTML = `<div class="page">${pageHead(t("profile.title"), t("profile.sub"))}${exampleBanner()}
      ${progressHtml(step)}${body}
      <p class="small muted" style="display:flex;gap:8px;align-items:center">${icon("lock", "icon icon-sm")}${esc(t("profile.privacy"))}
        <button type="button" class="btn btn-quiet" id="reset">${esc(t("profile.reset"))}</button></p></div>`;
    wire();
  };

  const updateProgress = () => {
    const wrap = root.querySelector(".progress-wrap");
    if (wrap) wrap.outerHTML = progressHtml(step);
    root.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => { step = Number(b.dataset.goto); store.setStep(step); draw(); }));
  };

  const wire = () => {
    root.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => { step = Number(b.dataset.goto); store.setStep(step); draw(); }));
    root.querySelector("#back")?.addEventListener("click", () => { step -= 1; store.setStep(step); draw(); });
    root.querySelector("#reset").addEventListener("click", async () => {
      if (!window.confirm(t("profile.resetConfirm"))) return;
      let ok = true;
      try { await api.forget(); } catch { ok = false; }  // also delete what the server stored
      store.reset(); step = 0; toast(t(ok ? "profile.deleted" : "profile.deleteFailed")); draw();
    });
    root.querySelector("#finish")?.addEventListener("click", () => {
      const firstMissing = STEPS.findIndex((_, i) => !fieldsOf(i).every(answered));
      if (firstMissing >= 0) { step = firstMissing; store.setStep(step); draw(); showMissing(); return; }
      store.finish();
      location.hash = "#/prediction";
    });
    const form = root.querySelector("#step-form");
    if (!form) return;
    form.addEventListener("change", (e) => {
      const input = e.target;
      if (input.type === "checkbox") {
        store.set(input.name, [...form.querySelectorAll(`input[name="${input.name}"]:checked`)].map((x) => x.value));
      } else {
        store.set(input.name, NUMERIC.has(input.name) ? Number(input.value) : input.value);
      }
      const q = input.closest("[data-q]")?.closest(".question") || input.closest("[data-q]");
      if (q) { q.classList.remove("missing"); const err = q.querySelector(".q-error"); if (err && fieldsOfQuestion(q).every(answered)) err.hidden = true; }
      if (fieldsOf(step).every(answered)) {
        root.querySelector("#encourage").innerHTML = `${icon("checkCircle")}${esc(t("profile.encourage")[step])}`;
        root.querySelector("#summary-error").hidden = true;
      }
      updateProgress();
    });
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      if (!fieldsOf(step).every(answered)) { showMissing(); return; }
      step += 1;
      store.setStep(step);
      draw();
      root.querySelector("h2")?.scrollIntoView({ block: "start" });
      announce(step < STEPS.length ? t("profile.stepOf", { n: step + 1, total: STEPS.length }) : t("profile.review"));
    });
  };

  const fieldsOfQuestion = (q) => (q.dataset.q === "grades" ? GRADES : [q.dataset.q]);

  const showMissing = () => {
    let first = null;
    root.querySelectorAll(".question").forEach((q) => {
      const missing = !fieldsOfQuestion(q).every(answered);
      q.classList.toggle("missing", missing);
      const err = q.querySelector(".q-error");
      if (err) err.hidden = !missing;
      if (missing && !first) first = q;
    });
    const summary = root.querySelector("#summary-error");
    if (summary) summary.hidden = false;
    first?.scrollIntoView({ behavior: "smooth", block: "center" });
    first?.querySelector("input, select")?.focus({ preventScroll: true });
  };

  draw();
}
