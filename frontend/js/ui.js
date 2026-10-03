// Small shared building blocks for the pages.
import { icon } from "./icons.js";
import { t } from "./i18n.js";
import { store } from "./store.js";

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function pageHead(title, sub, eyebrow = "") {
  return `<header class="page-head">
    ${eyebrow ? `<div class="eyebrow">${esc(eyebrow)}</div>` : ""}
    <h1 tabindex="-1">${esc(title)}</h1>
    ${sub ? `<p>${esc(sub)}</p>` : ""}
  </header>`;
}

const JOURNEY = ["prediction", "target", "why", "plan", "chat"];

export function journey(current) {
  return `<nav aria-label="${esc(t("journey.label"))}"><ol class="journey">
    ${JOURNEY.map((page, i) => `<li><a href="#/${page}" ${page === current ? 'aria-current="step"' : ""}>
      <span class="step-no">${i + 1}</span>${esc(t(`journey.${page}`))}</a></li>`).join("")}
  </ol></nav>`;
}

export function nextStep(text, href, iconName = "right") {
  return `<div class="next-step"><p>${esc(text)}</p>
    <a class="btn btn-primary" href="${href}">${esc(t("common.next"))} ${icon(iconName)}</a></div>`;
}

export function exampleBanner() {
  if (!store.example) return "";
  return `<div class="note warn" role="note">${icon("info")}
    <span>${esc(t("common.exampleBanner"))} <a href="#/profile" data-use-mine>${esc(t("common.exampleUseMine"))}</a></span></div><br>`;
}

export function needProfile() {
  return `<div class="card empty">${icon("user", "icon-lg")}
    <h2>${esc(t("common.needProfileTitle"))}</h2>
    <p class="muted">${esc(t("common.needProfileBody"))}</p>
    <a class="btn btn-primary btn-lg" href="#/profile">${esc(t("common.needProfileBtn"))} ${icon("right")}</a></div>`;
}

export function loading() {
  return `<div class="card" aria-busy="true"><div class="loading-card"><span class="spinner" aria-hidden="true"></span>
    <span>${esc(t("common.loading"))}</span></div>
    <div class="skeleton" style="height:28px;margin-top:24px;width:60%"></div>
    <div class="skeleton" style="height:120px;margin-top:16px"></div></div>`;
}

export function errorBox(message, retryHash) {
  return `<div class="card empty" role="alert">${icon("alert", "icon-lg")}
    <h2>${esc(t("common.error"))}</h2><p class="muted">${esc(message || "")}</p>
    <a class="btn btn-secondary" href="${retryHash}" data-retry>${esc(t("common.retry"))}</a></div>`;
}

export function trustBox(level) {
  const iconName = level === "reliable" ? "checkCircle" : level === "rough" ? "info" : "alert";
  return `<div class="trust ${level}">${icon(iconName, "icon icon-sm")}<span>${esc(t(`prediction.trust.${level}`))}</span></div>`;
}

export function toast(message) {
  const el = document.createElement("div");
  el.className = "toast";
  el.setAttribute("role", "status");
  el.textContent = message;
  document.body.append(el);
  setTimeout(() => el.remove(), 2600);
}

export function announce(message) {
  const live = document.getElementById("live");
  live.textContent = "";
  setTimeout(() => { live.textContent = message; }, 50);
}

export function pct(p) { return Math.round(p * 100); }
