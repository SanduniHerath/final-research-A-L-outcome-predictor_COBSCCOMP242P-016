// Small SVG charts, drawn without libraries so the app works offline.
// Each chart has a text alternative (role="img" + aria-label), and meaning never depends on colour alone.
import { esc } from "./ui.js";

// Colours are CSS variables from tokens.css, so charts follow the light / dark theme.
// SVG attributes cannot read CSS variables, so colours are always set through style="".
const COL = {
  ink: "var(--c-ink)", ink2: "var(--c-ink-2)", border: "var(--c-border)", surface: "var(--c-surface)", surface2: "var(--c-surface-2)",
  primary: "var(--c-primary)", primary50: "var(--c-primary-50)", accent: "var(--c-accent)", down: "var(--c-down)", growth: "var(--c-growth)",
};

/** Number line with the student's range, best guess, band edges and cut-off ticks. */
export function numberLine({ low, high, point, marks = [], bandEdges = [], min = 0.5, max = 3.0, label = "" }) {
  const W = 640, H = marks.length ? 128 : 92, L = 24, R = 24, Y = 52;
  const x = (v) => L + ((Math.min(Math.max(v, min), max) - min) / (max - min)) * (W - L - R);
  const ticks = [];
  for (let v = Math.ceil(min * 2) / 2; v <= max + 1e-9; v += 0.5) ticks.push(v);
  const bands = bandEdges.map((e) => `<line x1="${x(e)}" x2="${x(e)}" y1="${Y - 26}" y2="${Y + 10}" style="stroke:${COL.border}" stroke-width="2" stroke-dasharray="4 4"/>`).join("");
  // Only the first mark is labelled (the lowest cut-off); the others are thin ticks, so labels never overlap.
  const markSvg = marks.map((m, i) => {
    const mx = x(m.value);
    if (!m.label) return `<line x1="${mx}" x2="${mx}" y1="${Y - 16}" y2="${Y + 16}" style="stroke:${COL.ink2}" stroke-width="1.5"/>`;
    return `<g><line x1="${mx}" x2="${mx}" y1="${Y - 18}" y2="${Y + 30}" style="stroke:${COL.ink}" stroke-width="2.5"/>
      <path d="M${mx - 6} ${Y - 25} h12 l-6 8 z" style="fill:${COL.ink}"/>
      <text x="${mx}" y="${Y + 48}" text-anchor="middle" style="font-weight:700;fill:${COL.ink}">${esc(m.label)}</text></g>`;
  }).join("");
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">
    <line x1="${L}" x2="${W - R}" y1="${Y}" y2="${Y}" style="stroke:${COL.border}" stroke-width="6" stroke-linecap="round"/>
    ${bands}
    <rect x="${x(low)}" y="${Y - 14}" width="${Math.max(x(high) - x(low), 4)}" height="28" rx="14" style="fill:${COL.primary50};stroke:${COL.primary}" stroke-width="2"/>
    ${markSvg}
    <circle cx="${x(point)}" cy="${Y}" r="11" style="fill:${COL.primary};stroke:${COL.surface}" stroke-width="3"/>
    ${ticks.map((v) => `<text x="${x(v)}" y="${Y - 30}" text-anchor="middle">${v.toFixed(1)}</text>`).join("")}
  </svg>`;
}

/** Vertical bar histogram. */
export function histogram(bins, label) {
  const W = 640, H = 220, L = 40, B = 36, T = 12;
  const maxC = Math.max(...bins.map((b) => b.count)) || 1;
  const bw = (W - L - 8) / bins.length;
  const bars = bins.map((b, i) => {
    const h = ((H - B - T) * b.count) / maxC;
    const xx = L + i * bw + 4;
    return `<rect x="${xx}" y="${H - B - h}" width="${bw - 8}" height="${h}" rx="4" style="fill:${COL.primary}"/>
      <text x="${xx + (bw - 8) / 2}" y="${H - B - h - 4}" text-anchor="middle" style="font-weight:600;fill:${COL.ink}">${b.count}</text>
      <text x="${xx + (bw - 8) / 2}" y="${H - B + 16}" text-anchor="middle">${b.from.toFixed(2)}–${b.to.toFixed(2)}</text>`;
  }).join("");
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}">
    <line x1="${L}" x2="${W}" y1="${H - B}" y2="${H - B}" style="stroke:${COL.border}" stroke-width="2"/>${bars}</svg>`;
}

/** HTML bar list (accessible text + bars). items: {label, value (0..1 or count), text, top}. */
export function barList(items, max = null) {
  const top = max ?? Math.max(...items.map((i) => i.value)) ?? 1;
  return `<ul class="bar-list">${items.map((i) => `
    <li class="bar-item ${i.top ? "top" : ""}">
      <span class="label">${esc(i.label)}</span>
      <span class="bar-track" aria-hidden="true"><span class="bar-fill" style="width:${Math.max((i.value / (top || 1)) * 100, 1)}%;${i.color ? `background:${i.color}` : ""}"></span></span>
      <span class="pct num">${esc(i.text)}</span>
    </li>`).join("")}</ul>`;
}

/** Diverging bars for explanations: blue up (with ▲), orange down (with ▼). */
export function divergeList(items, unit = "") {
  const maxAbs = Math.max(...items.map((i) => Math.abs(i.value)), 1e-6);
  return `<ul class="diverge">${items.map((i) => {
    const up = i.value >= 0, w = (Math.abs(i.value) / maxAbs) * 50;
    return `<li><span>${esc(i.label)}${i.tag ? ` <span class="chip ${i.tagClass || ""}" style="font-size:12px">${esc(i.tag)}</span>` : ""}</span>
      <span class="axis" aria-hidden="true"><span class="bar ${up ? "up" : "down"}" style="width:${w}%"></span></span>
      <span class="val ${up ? "up" : "down"} num">${up ? "▲ +" : "▼ −"}${Math.abs(i.value).toFixed(unit === "pp" ? 0 : 2)}${unit === "pp" ? "" : ""}</span></li>`;
  }).join("")}</ul>`;
}

export { COL };
