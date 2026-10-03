// My Recommendations: the mode, a short weekly checklist (5 items at most), then all suggestions.
import { api } from "../api.js";
import { barList } from "../charts.js";
import { fmt, getLang, label, t } from "../i18n.js";
import { icon } from "../icons.js";
import { store } from "../store.js";
import { errorBox, esc, exampleBanner, journey, loading, needProfile, nextStep, pageHead } from "../ui.js";

/** Rule text in the chosen language, from the structured values the backend sends. */
function ruleText(rec) {
  if (getLang() === "en") return { title: rec.title, text: rec.text, reason: rec.reason };
  const p = rec.params || {};
  const group = p.similar_group ? label("cat", p.similar_group) : null;
  const who = group ? t("rule.whoTarget", { group }) : t("rule.whoTop");
  const target = p.target && p.target !== "your goal" ? label("cat", p.target) : t("rule.targetFallback");
  const subject = p.weak_foundation_subject === "Maths" ? t("rule.subjMaths") : t("rule.subjScience");
  const values = {
    who, target,
    hours: p.soft_hours ? t("plan.simHoursSoft") : label("opt", p.similar_hours, "al_study_hours"),
    mine: label("opt", p.g11_self_study_hours, "g11_self_study_hours"),
    freq: label("opt", p.similar_past_paper || p.similar_revision, p.similar_past_paper ? "al_past_paper_freq" : "al_revision_freq"),
    subject, grade: p.weak_foundation_grade, gap: p.gap_points,
    list: (p.backup_categories || []).map((c) => label("cat", c)).join(", "),
    course: p.reference_course, uni: p.reference_university, min: p.reference_min, max: p.reference_max,
  };
  if (p.target_or_future) values.target = p.target_or_future === "the careers you are interested in" ? t("rule.futureFallback") : label("cat", p.target_or_future);
  return {
    title: t(`rule.${rec.id}.title`, values),
    text: t(`rule.${rec.id}.text`, values),
    reason: t(`rule.${rec.id}.reason`, values),
  };
}

export async function render(root) {
  const head = pageHead(t("plan.title"), t("plan.sub"));
  if (!store.complete) { root.innerHTML = `<div class="page">${head}${needProfile()}</div>`; return; }
  root.innerHTML = `<div class="page">${head}${journey("plan")}${loading()}</div>`;
  let r;
  try { r = await api.recommend(store.answers); } catch (e) { root.innerHTML = `<div class="page">${head}${errorBox(e.message, "#/plan")}</div>`; return; }

  const recs = r.recommendations.map((rec) => ({ ...rec, ...ruleText(rec) }));
  const week = recs.filter((x) => !["Options", "Subjects"].includes(x.area)).slice(0, 5);
  const done = store.done;
  const sim = r.similar_students;
  const wi = r.what_if;
  const wiItems = ["habits", "motivation", "goals", "all"].map((k) => ({ label: t(`plan.wi.${k}`), value: Math.max(wi[k], 0), text: `${wi[k] >= 0 ? "+" : ""}${fmt(wi[k])}`, top: k === "all" }));
  const who = sim.group ? t("plan.whoGroup", { group: label("cat", sim.group) }) : t("plan.whoTop");
  const hoursMode = sim.al_study_hours_mode;
  const soft = hoursMode && ["31 - 40", "More than 40"].includes(hoursMode);

  const evChip = { model: "blue", survey: "green", official: "amber", research: "" };
  const recCard = (x) => `<article class="card rec">
      <div class="rec-head"><span class="prio" aria-hidden="true">${x.priority}</span>
        <div><span class="chip">${esc(label("area", x.area))}</span><h3>${esc(x.title)}</h3><p>${esc(x.text)}</p>
          <details class="more"><summary>${icon("chev", "icon chev")}${esc(t("plan.whyThis"))}</summary>
            <p>${esc(x.reason)}</p>
            <div class="evidence">${x.evidence_types.map((e, i) => `<span class="chip ${evChip[e]}" title="${esc(x.evidence[i])}">${esc(t(`plan.ev.${e}`))}</span>`).join("")}</div>
            ${x.evidence.filter((e) => e.startsWith("Research")).map((e) => `<p class="small muted">${esc(e.replace(/^Research: ?/, ""))}</p>`).join("")}
          </details></div></div></article>`;
  root.innerHTML = `<div class="page">${head}${journey("plan")}${exampleBanner()}
    <div class="mode-banner ${r.mode}"><span class="icon-wrap">${icon(r.mode === "close_the_gap" ? "up" : "shield", "icon icon-lg")}</span>
      <div><h2 style="margin:0">${esc(t(`plan.${r.mode}T`))}</h2><p style="margin:0">${esc(t(`plan.${r.mode}B`))}</p></div></div>

    <section class="card"><h2>${icon("list")} ${esc(t("plan.weekTitle"))}</h2>
      <p class="card-sub small">${esc(t("plan.weekSub"))}</p>
      <ul class="checklist">${week.map((x) => `<li><label><input type="checkbox" data-done="${x.id}" ${done[x.id] ? "checked" : ""}><span>${esc(x.title)}</span></label></li>`).join("")}</ul>
      <p class="encourage" id="done-count" aria-live="polite"></p>
    </section>

    <h2>${esc(t("plan.recsTitle"))}</h2>
    ${recs.slice(0, 3).map(recCard).join("")}
    ${recs.length > 3 ? `<details class="more" style="margin-bottom:24px"><summary>${icon("chev", "icon chev")}${esc(t("plan.moreRecs", { n: recs.length - 3 }))}</summary>
      ${recs.slice(3).map(recCard).join("")}</details>` : ""}

    <div class="grid-2">
      ${sim.available ? `<section class="card"><h2>${icon("people")} ${esc(t("plan.similarTitle"))}</h2>
        <p class="card-sub small">${esc(t("plan.similarSub", { n: sim.n, who }))}</p>
        <table class="simple"><tbody>
          <tr><th>${esc(t("plan.simHours"))}</th><td>${esc(soft ? t("plan.simHoursSoft") : label("opt", hoursMode, "al_study_hours"))}</td></tr>
          <tr><th>${esc(t("plan.simPast"))}</th><td>${esc(label("opt", sim.al_past_paper_freq_mode, "al_past_paper_freq"))}</td></tr>
          <tr><th>${esc(t("plan.simRev"))}</th><td>${esc(label("opt", sim.al_revision_freq_mode, "al_revision_freq"))}</td></tr>
          <tr><th>${esc(t("plan.simMedian"))}</th><td class="num">${fmt(sim.median_z)}</td></tr>
        </tbody></table></section>` : ""}
      <section class="card"><h2>${icon("sparkle")} ${esc(t("plan.whatIfTitle"))}</h2>
        <p class="card-sub small">${esc(t("plan.whatIfSub"))}</p>
        ${barList(wiItems, Math.max(...wiItems.map((i) => i.value), 0.05))}
      </section>
    </div>
    ${nextStep(t("plan.next"), "#/chat", "chat")}
  </div>`;

  const count = () => {
    const boxes = [...root.querySelectorAll("[data-done]")];
    const n = boxes.filter((b) => b.checked).length;
    root.querySelector("#done-count").innerHTML = n === boxes.length && n > 0
      ? `${icon("checkCircle")}${esc(t("plan.allDone"))}`
      : esc(t("plan.done", { n, total: boxes.length }));
  };
  root.querySelectorAll("[data-done]").forEach((b) => b.addEventListener("change", () => { store.setDone(b.dataset.done, b.checked); count(); }));
  count();
}
