// Home: one main action ("Start now"), a 3-step explanation, and trust notes.
import { api } from "../api.js";
import { t } from "../i18n.js";
import { icon } from "../icons.js";
import { store } from "../store.js";
import { esc } from "../ui.js";

const ART = `<svg class="hero-art" viewBox="0 0 320 240" aria-hidden="true">
  <defs><clipPath id="dawn-window"><circle cx="160" cy="120" r="116"/></clipPath>
    <linearGradient id="dawn-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2B6CB8"/><stop offset="1" stop-color="#F3B26A"/></linearGradient></defs>
  <g clip-path="url(#dawn-window)">
  <rect width="320" height="240" fill="url(#dawn-sky)"/>
  <!-- sunrise: the sun rising behind the hills, a path leading from the start (book) to the goal (flag) -->
  <g stroke="#FFE3A8" stroke-width="5" stroke-linecap="round" opacity=".9">
    <path d="M200 50v18"/><path d="M154 70l12 12"/><path d="M246 70l-12 12"/><path d="M134 116h16"/><path d="M250 116h16"/>
  </g>
  <circle cx="200" cy="128" r="42" fill="#F7B850"/>
  <circle cx="200" cy="128" r="42" fill="none" stroke="#FFE3A8" stroke-width="3" opacity=".6"/>
  <path d="M0 150 C60 120 120 160 180 140 C230 124 280 132 320 120 V240 H0 Z" fill="#163E73"/>
  <path d="M0 190 C70 165 140 200 210 180 C260 166 290 172 320 165 V240 H0 Z" fill="#102F57"/>
  <path d="M124 198 C135 192 110 180 150 172 C190 164 205 150 228 146" fill="none" stroke="#FFFFFF" stroke-opacity=".8" stroke-width="4" stroke-linecap="round" stroke-dasharray="1 11"/>
  <rect x="96" y="188" width="26" height="19" rx="3" fill="#FFFFFF"/><path d="M109 188v19" stroke="#1F5FAD" stroke-width="2"/>
  <rect x="228" y="112" width="4" height="36" rx="2" fill="#FFFFFF"/><path d="M232 113 L252 121 L232 129 Z" fill="#F08A4B"/>
  </g>
  <circle cx="160" cy="120" r="116" fill="none" stroke="#FFFFFF" stroke-opacity=".35" stroke-width="3"/>
</svg>`;

export async function render(root, { go }) {
  const primary = store.complete
    ? `<a class="btn btn-primary btn-lg" href="#/prediction">${esc(t("home.results"))} ${icon("right")}</a>`
    : store.started
      ? `<a class="btn btn-primary btn-lg" href="#/profile">${esc(t("home.resume"))} ${icon("right")}</a>`
      : `<a class="btn btn-primary btn-lg" href="#/profile">${esc(t("home.start"))} ${icon("right")}</a>`;

  root.innerHTML = `<div class="page">
    <section class="hero">
      <div>
        <div class="hero-tag">${icon("sparkle", "icon icon-sm")}${esc(t("app.name"))} · ${esc(t("app.tagline"))}</div>
        <h1 tabindex="-1">${esc(t("home.title"))}</h1>
        <p>${esc(t("home.sub"))}</p>
        <div class="actions">${primary}
          <button class="btn btn-secondary" id="try-example">${icon("people")} ${esc(t("home.example"))}</button></div>
      </div>${ART}
    </section>

    <h2>${esc(t("home.howTitle"))}</h2>
    <div class="grid-3 steps-3">
      ${[1, 2, 3].map((n) => `<div class="card step-card"><span class="badge-no">${n}</span>
        ${icon(["user", "chart", "list"][n - 1], "icon-lg")}
        <h3>${esc(t(`home.s${n}t`))}</h3><p class="muted">${esc(t(`home.s${n}b`))}</p></div>`).join("")}
    </div>
    <div class="trust-row">
      ${[["lock", 1], ["shield", 2], ["heart", 3]].map(([ic, n]) => `<div class="trust-item">${icon(ic)}
        <div><strong>${esc(t(`home.t${n}t`))}</strong><br><span class="muted small">${esc(t(`home.t${n}b`))}</span></div></div>`).join("")}
    </div>

    <dialog class="modal" id="example-dialog" aria-labelledby="ex-title">
      <h2 id="ex-title">${esc(t("home.exTitle"))}</h2>
      <p class="muted">${esc(t("home.exBody"))}</p>
      <div class="options col" role="list">
        ${["strong", "average", "weak"].map((k) => {
          const key = { strong: "exStrong", average: "exAverage", weak: "exWeak" }[k];
          return `<button class="btn btn-secondary" style="justify-content:flex-start;border-radius:12px;min-height:64px;text-align:left" data-example="${k}">
            ${icon("user")}<span><strong>${esc(t(`home.${key}`))}</strong><br><span class="small muted">${esc(t(`home.${key}B`))}</span></span></button>`;
        }).join("")}
      </div>
      <div class="actions"><button class="btn btn-quiet" id="ex-close">${esc(t("common.close"))}</button></div>
    </dialog>
  </div>`;

  const dialog = root.querySelector("#example-dialog");
  root.querySelector("#try-example").addEventListener("click", () => dialog.showModal());
  root.querySelector("#ex-close").addEventListener("click", () => dialog.close());
  root.querySelectorAll("[data-example]").forEach((button) => button.addEventListener("click", async () => {
    const examples = await api.examples();
    store.load(examples[button.dataset.example], button.dataset.example);
    dialog.close();
    go("prediction");
  }));
}
