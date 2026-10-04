// My Target and Gap: a clear status first, then the details (progressive disclosure).
import { api } from "../api.js";
import { numberLine } from "../charts.js";
import { fmt, label, t } from "../i18n.js";
import { icon } from "../icons.js";
import { store } from "../store.js";
import { errorBox, esc, exampleBanner, journey, loading, needProfile, nextStep, pageHead } from "../ui.js";


function statusHero(g) {
  const target = label("cat", g.target_category || "");
  if (g.status === "not_applicable") {
    return `<div class="status-hero none"><span class="icon-wrap">${icon("compass", "icon icon-lg")}</span>
      <div><h2>${esc(t("target.noTargetTitle"))}</h2><p>${esc(t("target.noTargetBody"))}</p></div></div>`;
  }
  const r = g.reference || {};
  const params = { target, z: fmt(g.predicted_z), year: g.cutoff_year, district: label("district", g.district), cut: fmt(r.value),
    course: r.course ? niceCourse(r.course) : "", uni: r.university || "", gap: fmt(g.gap_points || 0) };
  if (g.status === "on_track") {
    return `<div class="status-hero on_track"><span class="icon-wrap">${icon("check", "icon icon-lg")}</span>
      <div><h2>${esc(t("target.onTrackTitle", params))}</h2><p>${esc(t(r.source === "official" ? "target.onTrackBody" : "target.dataBody", params))}</p></div></div>`;
  }
  return `<div class="status-hero gap"><span class="icon-wrap">${icon("up", "icon icon-lg")}</span>
    <div><h2>${esc(t("target.gapTitle", params))}</h2><p>${esc(t(r.source === "official" ? "target.gapBody" : "target.dataBody", params))}</p></div></div>`;
}

function niceCourse(name) {
  return name.split(" ").map((w) => (/^[A-Z]{2,}$/.test(w) && w.length > 3 ? w[0] + w.slice(1).toLowerCase() : w)).join(" ");
}

const UNI_GROUPS = [
  ["within_reach", "green", "checkCircle", true],
  ["close", "blue", "up", true],
  ["further", "orange", "down", false],
  ["no_cutoff", "", "info", false],
];

function uniList(rows) {
  return `<ul class="course-list">${rows.map((u) => `<li class="course"><div><div class="c-name">${esc(u.university)}</div>
    <div class="c-uni">${esc(u.course)}</div></div><div class="c-cut num">${u.cutoff === null ? "NQC" : fmt(u.cutoff, 4)}
    ${u.gap_from_best_guess === null || u.gap_from_best_guess === undefined ? "" : `<div class="small muted">${esc(t(u.gap_from_best_guess > 0 ? "target.uniToGo" : "target.uniAbove", { v: fmt(Math.abs(u.gap_from_best_guess)) }))}</div>`}</div></li>`).join("")}</ul>`;
}

function universitiesCard(g, target, district) {
  if (!g.universities) return "";
  const groups = UNI_GROUPS.filter(([key]) => g.universities[key].length);
  return `<section class="card" aria-labelledby="uni-title">
    <h2 id="uni-title">${icon("compass")} ${esc(t("target.uniTitle"))}</h2>
    <p class="card-sub small">${esc(t("target.uniSub", { target, district, year: g.cutoff_year }))}</p>
    ${groups.map(([key, cls, ic, open]) => `<details class="more" ${open ? "open" : ""}>
      <summary>${icon("chev", "icon chev")}<span class="chip ${cls}">${icon(ic, "icon icon-sm")}${esc(t(`target.uniGroup.${key}`))}</span>
        <span class="small muted">${esc(t("target.uniCount", { n: g.universities[key].length }))}</span></summary>
      <p class="small muted">${esc(t(`target.uniHelp.${key}`))}</p>${uniList(g.universities[key])}</details>`).join("")}
    ${g.universities.within_reach.length ? "" : `<p class="small">${esc(t("target.uniNoneYet"))}</p>`}
    <div class="note" style="margin-top:16px">${icon("info")}<span>${esc(t("target.uniNote"))}</span></div>
  </section>`;
}

function uniqueUniversities(rows) {
  return [...new Set(rows.map((u) => u.university))];
}

export async function render(root) {
  const head = pageHead(t("target.title"), t("target.sub"));
  if (!store.complete) { root.innerHTML = `<div class="page">${head}${needProfile()}</div>`; return; }
  root.innerHTML = `<div class="page">${head}${journey("target")}${loading()}</div>`;
  let g, p;
  try { [g, p] = await Promise.all([api.gap(store.answers), api.predict(store.answers)]); }
  catch (e) { root.innerHTML = `<div class="page">${head}${errorBox(e.status === 422 ? t("target.needTarget") : e.message, "#/target")}</div>`; return; }

  const target = label("cat", g.target_category || "");
  const district = label("district", g.district);
  const published = (g.courses || []).filter((c) => c.cutoff !== null);
  const marks = published.slice(0, 8).map((c, i) => ({ value: c.cutoff, label: i === 0 ? t("target.lowestCut", { v: fmt(c.cutoff) }) : "" }));
  const lo = Math.min(g.range[0], ...published.map((c) => c.cutoff)) - 0.15;
  const hi = Math.max(g.range[1], ...published.map((c) => c.cutoff)) + 0.15;

  const backups = (g.other_options || []).filter((o) => o.category !== g.target_category);
  const entrants = g.entrants || {};

  root.innerHTML = `<div class="page">${head}${journey("target")}${exampleBanner()}
    ${statusHero(g)}
    ${g.subject_check?.warning ? `<div class="note warn">${icon("alert")}<span>${esc(t("target.subjectWarn", { target }))}</span></div><br>` : ""}
    ${published.length ? `<section class="card"><h2>${icon("target")} ${esc(t("target.chartTitle"))}</h2>
      ${numberLine({ low: p.zscore.range_low, high: p.zscore.range_high, point: p.zscore.predicted, marks, min: Math.max(0, Math.floor(lo * 2) / 2), max: Math.ceil(hi * 2) / 2,
        label: `${t("target.chartTitle")}. ${t("prediction.range", { low: fmt(p.zscore.range_low), high: fmt(p.zscore.range_high) })}. ${t("target.cutoff")}: ${marks.map((m) => m.label).join(", ")}` })}
      <div class="legend"><span><span class="swatch" style="background:var(--c-primary-50);border:2px solid var(--c-primary)"></span>${esc(t("target.chartLegendRange"))}</span>
        <span><span class="swatch" style="background:var(--c-primary);border-radius:50%"></span>${esc(t("target.chartLegendYou"))}</span>
        <span><span class="swatch" style="background:var(--c-ink);width:3px"></span>${esc(t("target.chartLegendCut"))}</span>
        <span><span class="swatch" style="background:var(--c-ink-2);width:2px"></span>${esc(t("target.chartLegendOther"))}</span></div>

    </section>` : ""}

    ${universitiesCard(g, target, district)}
    <div class="grid-2">
      <section class="card"><h2>${icon("flag")} ${esc(t("target.backupTitle"))}</h2>
        <p class="small muted">${esc(t("target.backupSub"))}</p>
        ${backups.length ? `<ul class="course-list">${backups.map((o) => `<li class="course"><div><div class="c-name">${esc(label("cat", o.category))}</div>
          <div class="c-uni">${(() => { const u = uniqueUniversities(o.universities_reached || []); return esc(u.slice(0, 4).join(", ") + (u.length > 4 ? " " + t("target.andMore", { n: u.length - 4 }) : "")); })()}</div></div><div class="c-cut num">${fmt(o.lowest_cutoff)}</div>
          <div class="c-status"><span class="chip ${o.whole_range_above ? "green" : "blue"}">${icon(o.whole_range_above ? "checkCircle" : "up", "icon icon-sm")}
          ${esc(t(o.whole_range_above ? "target.backupWhole" : "target.backupBest"))}</span></div></li>`).join("")}</ul>`
          : `<p>${esc(t("target.backupNone"))}</p>`}
      </section>
      <section class="card"><h2>${icon("people")} ${esc(target ? t("target.entrantsTitle", { target }) : t("target.title"))}</h2>
        ${entrants.median_z !== undefined ? `<p>${esc(t("target.entrants", { target, q1: fmt(entrants.q1), q3: fmt(entrants.q3) }))}</p>` : ""}
        <div class="note">${icon("info")}<span>${esc(t("target.note1", { year: g.cutoff_year }))}</span></div><br>
        <div class="note">${icon("sparkle")}<span>${esc(t("target.note2"))}</span></div>
      </section>
    </div>
    ${nextStep(t("target.next"), "#/why")}
  </div>`;
}
