// Why This Result: question groups first; single answers only on request (progressive disclosure).
import { api } from "../api.js";
import { divergeList } from "../charts.js";
import { label, t } from "../i18n.js";
import { icon } from "../icons.js";
import { store } from "../store.js";
import { errorBox, esc, exampleBanner, journey, loading, needProfile, nextStep, pageHead } from "../ui.js";

export async function render(root) {
  const head = pageHead(t("why.title"), t("why.sub"));
  if (!store.complete) { root.innerHTML = `<div class="page">${head}${needProfile()}</div>`; return; }
  root.innerHTML = `<div class="page">${head}${journey("why")}${loading()}</div>`;
  let ex;
  try { ex = await api.explain(store.answers); } catch (e) { root.innerHTML = `<div class="page">${head}${errorBox(e.message, "#/why")}</div>`; return; }

  const z = ex.zscore, d = ex.degree_category;
  const groups = Object.entries(z.groups).filter(([, v]) => Math.abs(v) >= 0.005);
  const groupItems = groups.map(([g, v]) => ({ label: label("group", g), value: v }));
  const sentences = groups.map(([g, v]) => t(v > 0 ? "why.sentenceUp" : "why.sentenceDown", { group: label("group", g), v: Math.abs(v).toFixed(2) }));
  const details = z.items.slice(0, 10).map((i) => ({
    label: label("item", i.item), value: i.contribution,
    tag: i.changeable ? t("why.canChange") : null, tagClass: "green",
  }));
  const degName = label("cat", d.class_name);
  const degGroups = Object.entries(d.groups).filter(([, v]) => Math.abs(v) >= 0.005).map(([g, v]) => ({ label: label("group", g), value: v * 100 }));

  root.innerHTML = `<div class="page">${head}${journey("why")}${exampleBanner()}
    <section class="card"><h2>${icon("bulb")} ${esc(t("why.groupsTitle"))}</h2>
      <div class="legend"><span><span class="swatch" style="background:var(--c-primary)"></span>▲ ${esc(t("why.up"))}</span>
        <span><span class="swatch" style="background:var(--c-down)"></span>▼ ${esc(t("why.down"))}</span></div>
      ${divergeList(groupItems)}
      <ul>${sentences.map((s) => `<li>${esc(s)}</li>`).join("")}</ul>
      ${z.stable ? "" : `<div class="note">${icon("info")}<span>${esc(t("why.stability"))}</span></div>`}
      <details class="more"><summary>${icon("chev", "icon chev")}${esc(t("why.detailTitle"))}</summary>
        <p class="small muted">${esc(t("why.detailSub"))}</p>${divergeList(details)}</details>
    </section>

    <section class="card"><h2>${icon("compass")} ${esc(t("why.degreeTitle", { degree: degName }))}</h2>
      <p class="card-sub small">${esc(t("why.degreeSub", { degree: degName }))}</p>
      ${divergeList(degGroups, "pp")}
    </section>

    <div class="note">${icon("info")}<span>${esc(t("why.note"))}</span></div>
    ${nextStep(t("why.next"), "#/plan")}
  </div>`;
}
