// My Prediction: the Z-score as a range, the band, degree areas and (as a very rough guide) region.
import { api } from "../api.js";
import { barList, numberLine } from "../charts.js";
import { fmt, label, t } from "../i18n.js";
import { icon } from "../icons.js";
import { store } from "../store.js";
import { errorBox, esc, exampleBanner, journey, loading, needProfile, nextStep, pageHead, pct, trustBox } from "../ui.js";

const BAND_KEYS = { "Band 1": "band1", "Band 2": "band2", "Band 3": "band3" };

export async function render(root) {
  const head = pageHead(t("prediction.title"), t("prediction.sub"));
  if (!store.complete) { root.innerHTML = `<div class="page">${head}${needProfile()}</div>`; return; }
  root.innerHTML = `<div class="page">${head}${journey("prediction")}${loading()}</div>`;
  let p;
  try { p = await api.predict(store.answers); } catch (e) { root.innerHTML = `<div class="page">${head}${errorBox(e.message, "#/prediction")}</div>`; return; }

  const z = p.zscore, band = p.zscore_band, deg = p.degree_category, uni = p.university_group;
  const [e1, e2] = band.band_edges;
  const bandRange = { "Band 1": t("prediction.below", { a: fmt(e1) }), "Band 2": t("prediction.between", { a: fmt(e1), b: fmt(e2) }), "Band 3": t("prediction.above", { a: fmt(e2) }) };
  const degItems = Object.entries(deg.probabilities).map(([k, v], i) => ({ label: label("cat", k), value: v, text: `${pct(v)}%`, top: i === 0 }));
  const lineLabel = `${t("prediction.zTitle")}: ${fmt(z.predicted)}. ${t("prediction.range", { low: fmt(z.range_low), high: fmt(z.range_high) })}`;

  root.innerHTML = `<div class="page">${head}${journey("prediction")}${exampleBanner()}
    <section class="card" aria-labelledby="z-title">
      <h2 id="z-title">${icon("chart")} ${esc(t("prediction.zTitle"))}</h2>
      <div style="display:flex;gap:24px;align-items:baseline;flex-wrap:wrap">
        <div><span class="muted">${esc(t("prediction.about"))}</span> <span class="big-number num">${fmt(z.predicted)}</span></div>
        <div class="range-text num">${esc(t("prediction.range", { low: fmt(z.range_low), high: fmt(z.range_high) }))}</div>
      </div>
      ${numberLine({ low: z.range_low, high: z.range_high, point: z.predicted, bandEdges: band.band_edges, label: lineLabel })}
      <div class="legend"><span><span class="swatch" style="background:var(--c-primary-50);border:2px solid var(--c-primary)"></span>${esc(t("prediction.rangeWord"))}</span>
        <span><span class="swatch" style="background:var(--c-primary);border-radius:50%"></span>${esc(t("prediction.you"))}</span></div>
      <p class="muted">${esc(t("prediction.rangeExplain"))}</p>
      ${z.below_data_range ? `<div class="note warn">${icon("alert")}<span>${esc(t("prediction.lowWarning"))}</span></div>` : ""}
      <details class="more"><summary>${icon("chev", "icon chev")}${esc(t("prediction.whatIsZ"))}</summary><p>${esc(t("prediction.whatIsZBody"))}</p></details>
    </section>

    <div class="grid-2">
      <section class="card" aria-labelledby="band-title">
        <h2 id="band-title">${esc(t("prediction.bandTitle"))}</h2>
        <p class="card-sub small">${esc(t("prediction.bandExplain"))}</p>
        <div class="band-strip">${["Band 1", "Band 2", "Band 3"].map((b) => `
          <div class="band-cell ${b === band.most_likely ? "top" : ""}">
            <div class="band-name">${esc(t(`prediction.${BAND_KEYS[b]}`))}</div>
            <div class="band-range num">${esc(bandRange[b])}</div>
            <div class="band-pct num">${pct(band.probabilities[b])}%</div></div>`).join("")}</div>
        ${trustBox(band.calibration)}
      </section>

      <section class="card" aria-labelledby="deg-title">
        <h2 id="deg-title">${esc(t("prediction.degreeTitle"))}</h2>
        <p class="card-sub small">${esc(t("prediction.degreeSub"))}</p>
        ${barList(degItems.slice(0, 3), 1)}
        <details class="more"><summary>${icon("chev", "icon chev")}${esc(t("prediction.showAll"))}</summary>${barList(degItems.slice(3), 1)}</details>
        ${trustBox(deg.calibration)}
      </section>
    </div>

    <details class="card more" style="padding-top:8px">
      <summary>${icon("chev", "icon chev")}${esc(t("prediction.uniTitle"))} <span class="chip orange">${esc(t("prediction.uniTag"))}</span></summary>
      <p>${esc(t("prediction.uniSub"))}</p>
      <div class="chips">${uni.top_k.map((r) => `<span class="chip blue">${icon("compass", "icon icon-sm")}${esc(label("uni", r))}</span>`).join("")}</div>
      ${trustBox(uni.calibration)}
    </details>

    ${nextStep(t("prediction.next"), "#/target")}
  </div>`;
}
