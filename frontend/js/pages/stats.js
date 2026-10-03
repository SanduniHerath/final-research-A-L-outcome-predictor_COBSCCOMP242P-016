// Statistics: three tabs (the survey / how well it works / checks), so each view stays short.
import { api } from "../api.js";
import { barList, histogram } from "../charts.js";
import { fmt, label, t } from "../i18n.js";
import { icon } from "../icons.js";
import { errorBox, esc, loading, pageHead, pct } from "../ui.js";

const CHOSEN = "MLP";

function countBars(rows, group) {
  const max = Math.max(...rows.map((r) => r.count || 0));
  return barList(rows.map((r) => ({ label: group ? label(group, r.label) : r.label, value: r.count || 0, text: r.small ? t("stats.small") : String(r.count) })), max);
}

function dataTab(s) {
  const d = s.dataset;
  return `<div class="kpis">
      <div class="kpi"><div class="kpi-val num">${d.respondents.toLocaleString()}</div><div class="kpi-label">${esc(t("stats.kStudents"))}</div></div>
      <div class="kpi"><div class="kpi-val num">${d.splits.train}</div><div class="kpi-label">${esc(t("stats.kTrain"))}</div></div>
      <div class="kpi"><div class="kpi-val num">${d.splits.test}</div><div class="kpi-label">${esc(t("stats.kTest"))}</div></div>
      <div class="kpi"><div class="kpi-val num">${pct(s.model.zscore.within_0_4)}%</div><div class="kpi-label">${esc(t("stats.kWithin"))}</div></div>
    </div>
    <section class="card"><h2>${esc(t("stats.zHist"))}</h2><p class="card-sub small">${esc(t("stats.zHistSub", { m: fmt(d.zscore.median) }))}</p>
      ${histogram(d.zscore.bins, t("stats.zHist"))}</section>
    <div class="grid-2">
      <section class="card"><h3>${esc(t("stats.degree"))}</h3>${countBars(d.degree_category, "cat")}
        <p class="small muted">${esc(t("stats.reached", { p: pct(d.reached_target_share) }))}</p></section>
      <section class="card"><h3>${esc(t("stats.subjects"))}</h3>${countBars(d.subject_combination.map((r) => ({ ...r, label: label("opt", r.label, "al_subject_combination") })))}</section>
      <section class="card"><h3>${esc(t("stats.region"))}</h3>${countBars(d.university_group, "uni")}</section>
      <section class="card"><h3>${esc(t("stats.years"))}</h3>${countBars(d.exam_year)}</section>
    </div><br>
    <section class="card"><h3>${esc(t("stats.scales"))}</h3><p class="card-sub small">${esc(t("stats.scalesSub"))}</p>
      ${barList(s.questionnaire.map((q) => ({ label: t(`stats.scaleName.${q.construct}`), value: q.alpha, text: q.alpha.toFixed(2), color: "var(--c-growth)" })), 1)}</section>`;
}

function modelTab(s) {
  const m = s.model, z = m.zscore;
  const mae = [{ label: t("stats.ourModel"), value: z.chosen.mae.value, text: fmt(z.chosen.mae.value), top: true },
    { label: t("stats.simpleGuess"), value: z.baseline.mae.value, text: fmt(z.baseline.mae.value), color: "var(--c-muted-bar)" }];
  const all = z.all_models_mae.map((r) => ({ label: r.model + (r.model === CHOSEN ? " ✓" : ""), value: r.value, text: fmt(r.value, 3), top: r.model === CHOSEN }));
  const tasks = ["zscore_band", "degree_category", "university_group"];
  return `<section class="card"><h2>${esc(t("stats.mz"))}</h2><p class="card-sub small">${esc(t("stats.mzSub", { n: m.test_students }))}</p>
      ${barList(mae, 0.4)}</section>
    <section class="card"><h2>${esc(t("stats.classTitle"))}</h2><p class="card-sub small">${esc(t("stats.classSub"))}</p>
      ${tasks.map((task) => `<h3 style="margin-top:16px">${esc(t(`stats.tasks.${task}`))}</h3>
        ${barList([{ label: t("stats.ourModel"), value: m[task].chosen.macro_f1.value, text: fmt(m[task].chosen.macro_f1.value), top: true },
          { label: t("stats.simpleGuess"), value: m[task].baseline.macro_f1.value, text: fmt(m[task].baseline.macro_f1.value), color: "var(--c-muted-bar)" }], 1)}`).join("")}
    </section>
    <details class="card more" style="padding-top:8px"><summary>${icon("chev", "icon chev")}${esc(t("stats.allModels"))}</summary>
      <p class="small muted">${esc(t("stats.allModelsSub"))}</p>${barList(all, 0.3)}</details>`;
}

function checksTab(s) {
  const c = s.parts.chatbot, r = s.parts.recommendation;
  const cls = (res) => (/^Supported/.test(res) ? "green" : /Partly/.test(res) ? "amber" : /Pending/.test(res) ? "" : "orange");
  return `<section class="card"><h2>${esc(t("stats.hypTitle"))}</h2><p class="card-sub small">${esc(t("stats.hypSub"))}</p>
      <table class="simple"><tbody>${s.hypotheses.map((h) => `<tr><th>${esc(h.id)}</th><td><span class="chip ${cls(h.result)}">${esc(h.result)}</span></td></tr>`).join("")}</tbody></table></section>
    <section class="card"><h2>${esc(t("stats.partsTitle"))}</h2>
      <p>${esc(t("stats.chatbotCheck", { n: c.prompts, inv: c.invented_numbers, ref: pct(c.refusal), uns: pct(c.unsure), s: fmt(c.max_seconds, 1) }))}</p>
      <p>${esc(t("stats.recCheck", { p: pct(r.reason_and_evidence), ok: t(r.similar_closer_than_random ? "stats.yes" : "stats.no") }))}</p></section>`;
}

export async function render(root) {
  const head = pageHead(t("stats.title"), t("stats.sub"));
  root.innerHTML = `<div class="page">${head}${loading()}</div>`;
  let s;
  try { s = await api.stats(); } catch (e) { root.innerHTML = `<div class="page">${head}${errorBox(e.message, "#/stats")}</div>`; return; }
  const tabs = [["data", "stats.tabData", dataTab], ["model", "stats.tabModel", modelTab], ["checks", "stats.tabChecks", checksTab]];
  let active = "data";
  const draw = () => {
    root.innerHTML = `<div class="page">${head}
      <div class="tabs" role="tablist">${tabs.map(([id, key]) => `<button role="tab" id="tab-${id}" aria-controls="panel" aria-selected="${id === active}" tabindex="${id === active ? 0 : -1}" data-tab="${id}">${esc(t(key))}</button>`).join("")}</div>
      <div id="panel" role="tabpanel" aria-labelledby="tab-${active}">${tabs.find(([id]) => id === active)[2](s)}</div>
      <p class="small muted">${esc(t("stats.source"))}</p></div>`;
    root.querySelectorAll("[data-tab]").forEach((b) => {
      b.addEventListener("click", () => { active = b.dataset.tab; draw(); root.querySelector(`#tab-${active}`).focus(); });
      b.addEventListener("keydown", (e) => {
        const ids = tabs.map(([id]) => id), i = ids.indexOf(active);
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
          active = ids[(i + (e.key === "ArrowRight" ? 1 : ids.length - 1)) % ids.length];
          draw(); root.querySelector(`#tab-${active}`).focus();
        }
      });
    });
  };
  draw();
}
