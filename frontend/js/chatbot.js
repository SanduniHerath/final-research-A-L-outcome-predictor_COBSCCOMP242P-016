// The floating chatbot: Lumi waits in the corner of every page and opens a small chat window.
// On the "Ask the Chatbot" page the full-size chat is shown instead, so the corner button hides there.
import { getLang, t } from "./i18n.js";
import { icon } from "./icons.js";
import { lumiFace, mountChat } from "./lumi.js";
import { store } from "./store.js";
import { esc } from "./ui.js";

const SEEN = "alora.lumi.seen";   // this browser session: the greeting has been opened once
const ids = { log: "lumi-log", suggest: "lumi-suggest", form: "lumi-form", input: "lumi-input" };

let root, launcher, panel, body, teaser, chat;
let drawnFor = "";   // language and profile state the window was drawn for
let teaserTimer;

function seen() { try { return sessionStorage.getItem(SEEN) === "1"; } catch { return true; } }
function markSeen() { try { sessionStorage.setItem(SEEN, "1"); } catch { /* ignore */ } }

function isOpen() { return !panel.hidden; }

function draw() {
  drawnFor = `${getLang()}|${store.complete}`;
  launcher.setAttribute("aria-label", t("chat.open", { name: t("chat.name") }));
  launcher.title = t("chat.open", { name: t("chat.name") });
  panel.setAttribute("aria-label", t("chat.open", { name: t("chat.name") }));
  panel.querySelector(".lumi-title").innerHTML = `${lumiFace("lumi-md")}
    <div><div class="chat-name" id="lumi-name">${esc(t("chat.name"))}</div>
      <div class="chat-role"><span class="dot" aria-hidden="true"></span>${esc(t("chat.role"))}</div></div>`;
  const [newChat, close] = panel.querySelectorAll(".lumi-tools > *");
  newChat.title = t("chat.clear"); newChat.setAttribute("aria-label", t("chat.clear"));
  close.title = t("chat.close"); close.setAttribute("aria-label", t("chat.close"));
  teaser.querySelector(".lumi-teaser-text").textContent = t("chat.teaser", { name: t("chat.name") });
  teaser.querySelector(".lumi-teaser-close").setAttribute("aria-label", t("chat.teaserClose"));
  chat = mountChat(body, ids);
}

function hideTeaser() { clearTimeout(teaserTimer); teaser.hidden = true; }

function open() {
  hideTeaser();
  markSeen();
  root.classList.remove("has-news");
  panel.hidden = false;
  launcher.setAttribute("aria-expanded", "true");
  root.classList.add("is-open");
  const log = body.querySelector(".chat-log");
  if (log) log.scrollTop = log.scrollHeight;
  chat.focus();
}

function close(returnFocus = true) {
  panel.hidden = true;
  launcher.setAttribute("aria-expanded", "false");
  root.classList.remove("is-open");
  if (returnFocus) launcher.focus();
}

export function setupChatbot() {
  root = document.createElement("div");
  root.className = "lumi-root";
  root.innerHTML = `
    <section class="lumi-panel" id="lumi-panel" role="dialog" aria-labelledby="lumi-name" hidden>
      <header class="lumi-head">
        <div class="lumi-title"></div>
        <div class="lumi-tools">
          <button type="button" class="lumi-tool" data-act="new">${icon("trash")}</button>
          <button type="button" class="lumi-tool" data-act="close">${icon("close")}</button>
        </div>
      </header>
      <div class="chat-body lumi-body"></div>
    </section>
    <div class="lumi-teaser" hidden>
      <button type="button" class="lumi-teaser-text"></button>
      <button type="button" class="lumi-teaser-close">${icon("close", "icon icon-sm")}</button>
    </div>
    <button type="button" class="lumi-launcher" aria-expanded="false" aria-controls="lumi-panel">
      ${lumiFace("lumi-lg")}<span class="lumi-badge" aria-hidden="true">1</span>
    </button>`;
  document.body.append(root);
  launcher = root.querySelector(".lumi-launcher");
  panel = root.querySelector(".lumi-panel");
  body = root.querySelector(".lumi-body");
  teaser = root.querySelector(".lumi-teaser");

  launcher.addEventListener("click", () => (isOpen() ? close() : open()));
  panel.querySelector('[data-act="close"]').addEventListener("click", () => close());
  panel.querySelector('[data-act="new"]').addEventListener("click", () => chat.clear());
  panel.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } });
  teaser.querySelector(".lumi-teaser-text").addEventListener("click", open);
  teaser.querySelector(".lumi-teaser-close").addEventListener("click", () => { hideTeaser(); markSeen(); root.classList.remove("has-news"); });

  draw();
  if (!seen()) {
    root.classList.add("has-news");
    // A friendly "hello" bubble shortly after the first visit in this session; it goes away by itself.
    teaserTimer = setTimeout(() => {
      if (isOpen() || root.hidden) return;
      teaser.hidden = false;
      teaserTimer = setTimeout(hideTeaser, 9000);
    }, 1800);
  }
}

/** Called after every page change and language change. */
export function updateChatbot(page) {
  if (!root) return;
  const onChatPage = page === "chat";
  root.hidden = onChatPage;
  if (onChatPage) {
    // The full-page chat is the only conversation on that page (one live region, unique ids).
    if (isOpen()) close(false);
    hideTeaser();
    body.innerHTML = "";
    drawnFor = "";
    return;
  }
  if (`${getLang()}|${store.complete}` !== drawnFor) draw();
}
