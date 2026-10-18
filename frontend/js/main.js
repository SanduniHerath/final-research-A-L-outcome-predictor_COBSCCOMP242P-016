// App start-up: navigation, language, routing. One page per function (Phase 10 brief).
import { api } from "./api.js";
import { setupChatbot, updateChatbot } from "./chatbot.js";
import { applyStatic, getLang, setLang, t } from "./i18n.js";
import { fillIcons, icon } from "./icons.js";
import { store } from "./store.js";
import { announce, esc } from "./ui.js";

import * as about from "./pages/about.js";
import * as chat from "./pages/chat.js";
import * as home from "./pages/home.js";
import * as prediction from "./pages/prediction.js";
import * as profile from "./pages/profile.js";
import * as plan from "./pages/plan.js";
import * as target from "./pages/target.js";
import * as why from "./pages/why.js";

const PAGES = { home, profile, prediction, target, why, plan, chat, about };
// Navigation grouped into four short groups (Hick's law, Miller's law, Gestalt proximity).
const NAV = [
  ["start", [["home", "home"], ["profile", "user"]]],
  ["results", [["prediction", "chart"], ["target", "target"], ["why", "bulb"]]],
  ["plan", [["plan", "list"], ["chat", "chat"]]],
  ["more", [["about", "info"]]],
];
const NEEDS_PROFILE = new Set(["prediction", "target", "why", "plan", "chat"]);

function currentPage() {
  const name = (location.hash.replace(/^#\/?/, "").split("?")[0] || "home");
  return PAGES[name] ? name : "home";
}

function renderNav(active) {
  const nav = document.getElementById("sidenav");
  nav.innerHTML = NAV.map(([group, items]) => `
    <div class="nav-group"><div class="nav-group-title">${esc(t(`nav.groups.${group}`))}</div>
      ${items.map(([page, ic]) => {
        const locked = NEEDS_PROFILE.has(page) && !store.complete;
        return `<a class="nav-link" href="#/${page}" ${page === active ? 'aria-current="page"' : ""}
          ${locked ? `title="${esc(t("nav.locked"))}"` : ""}>${icon(ic)}<span>${esc(t(`nav.${page}`))}</span>
          ${locked ? `<span class="lock">${icon("lock", "icon icon-sm")}<span class="sr-only">${esc(t("nav.locked"))}</span></span>` : ""}</a>`;
      }).join("")}
    </div>`).join("");
}

function closeMenu() {
  document.getElementById("sidenav").classList.remove("open");
  document.getElementById("scrim").hidden = true;
  document.getElementById("menu-btn").setAttribute("aria-expanded", "false");
}

async function route() {
  const name = currentPage();
  const main = document.getElementById("main");
  renderNav(name);
  closeMenu();
  updateChatbot(name);
  document.title = `${t(`nav.${name}`)} – ${t("app.name")}`;
  main.innerHTML = "";
  try {
    await PAGES[name].render(main, { go: (page) => { location.hash = `#/${page}`; } });
  } catch (error) {
    console.error(error);
    main.innerHTML = `<div class="page"><div class="card" role="alert">${esc(t("common.error"))}</div></div>`;
  }
  const heading = main.querySelector("h1");
  if (heading && document.activeElement !== document.body) heading.focus({ preventScroll: true });
  window.scrollTo(0, 0);
  announce(t(`nav.${name}`));
}

// Light / dark theme. The button shows what you will switch TO (moon = go dark, sun = go light).
const DARK = window.matchMedia("(prefers-color-scheme: dark)");

function applyTheme(theme) {
  const dark = theme === "dark";
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]').content = dark ? "#0A2140" : "#143A6B";
  const btn = document.getElementById("theme-btn");
  btn.setAttribute("aria-pressed", String(dark));
  btn.title = t(dark ? "theme.toLight" : "theme.toDark");
  btn.innerHTML = icon(dark ? "sun" : "moon");
}

function setupTheme() {
  applyTheme(store.theme || (DARK.matches ? "dark" : "light"));
  document.getElementById("theme-btn").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    store.theme = next;
    applyTheme(next);
    announce(t(next === "dark" ? "theme.nowDark" : "theme.nowLight"));
  });
  // Until the student chooses, follow the device when it changes (e.g. night mode at sunset).
  DARK.addEventListener("change", (e) => { if (!store.theme) applyTheme(e.matches ? "dark" : "light"); });
}

function setLanguage(lang) {
  setLang(lang);
  store.lang = lang;
  document.querySelectorAll(".lang-switch button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  applyStatic();
  applyTheme(document.documentElement.dataset.theme);
  route();
}

async function loadDemoFromUrl() {
  // ?demo=strong|average|weak loads a made-up example student (used for user testing and screenshots).
  const match = location.search.match(/demo=(strong|average|weak)/);
  if (!match) return;
  const examples = await api.examples();
  store.load(examples[match[1]], match[1]);
}

async function start() {
  fillIcons();
  setLang(store.lang);
  const langParam = location.search.match(/lang=(en|si|ta)/);
  if (langParam) { setLang(langParam[1]); store.lang = langParam[1]; }
  document.querySelectorAll(".lang-switch button").forEach((b) => {
    b.setAttribute("aria-pressed", String(b.dataset.lang === getLang()));
    b.addEventListener("click", () => setLanguage(b.dataset.lang));
  });
  applyStatic();
  setupTheme();
  const menu = document.getElementById("menu-btn");
  menu.addEventListener("click", () => {
    const nav = document.getElementById("sidenav");
    const open = !nav.classList.contains("open");
    nav.classList.toggle("open", open);
    document.getElementById("scrim").hidden = !open;
    menu.setAttribute("aria-expanded", String(open));
  });
  document.getElementById("scrim").addEventListener("click", closeMenu);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeMenu(); });
  document.addEventListener("click", (e) => {
    if (e.target.closest("[data-use-mine]")) { store.reset(); }
  });
  await loadDemoFromUrl().catch(() => {});
  setupChatbot();
  window.addEventListener("hashchange", route);
  route();
}

start();
