// Lumi, the chatbot: its face and the chat conversation, shared by the floating chat window
// (on every page) and the "Ask the Chatbot" page. The support-tool notice is always visible
// above the conversation, and the answers come from the same checked chatbot service.
import { api } from "./api.js";
import { getLang, t } from "./i18n.js";
import { icon } from "./icons.js";
import { store } from "./store.js";
import { esc } from "./ui.js";

const KEY = "alora.chat";
export function loadHistory() { try { return JSON.parse(sessionStorage.getItem(KEY)) || []; } catch { return []; } }
function saveHistory(h) { try { sessionStorage.setItem(KEY, JSON.stringify(h.slice(-20))); } catch { /* ignore */ } }

let faceCount = 0;
/** Lumi's face: a small sunrise with blinking eyes. Decorative (the name is always written next to it). */
export function lumiFace(cls = "") {
  const id = `lumi-grad-${++faceCount}`;
  return `<svg class="lumi ${cls}" viewBox="0 0 64 64" aria-hidden="true" focusable="false">
    <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#FFD98A"/><stop offset="1" stop-color="#F08A4B"/></linearGradient></defs>
    <g class="lumi-rays" stroke="#F4A62A" stroke-width="3.2" stroke-linecap="round">
      <path d="M32 3v5"/><path d="M32 60v1"/><path d="M5 34h4"/><path d="M55 34h4"/>
      <path d="m12.5 14.5 3 3"/><path d="m48.5 17.5 3-3"/><path d="m12.5 53.5 3-3"/><path d="m48.5 50.5 3 3"/>
    </g>
    <circle cx="32" cy="34" r="20" fill="url(#${id})"/>
    <g class="lumi-eyes" fill="#143A6B">
      <ellipse cx="25" cy="31.5" rx="3.2" ry="4.2"/><ellipse cx="39" cy="31.5" rx="3.2" ry="4.2"/>
      <circle cx="26.1" cy="30" r="1.1" fill="#fff"/><circle cx="40.1" cy="30" r="1.1" fill="#fff"/>
    </g>
    <ellipse cx="20.5" cy="39" rx="3.6" ry="2.1" fill="#E8574A" opacity="0.4"/>
    <ellipse cx="43.5" cy="39" rx="3.6" ry="2.1" fill="#E8574A" opacity="0.4"/>
    <path d="M26.5 40.5q5.5 5.2 11 0" fill="none" stroke="#143A6B" stroke-width="2.6" stroke-linecap="round"/>
  </svg>`;
}

/**
 * Draws a conversation with Lumi into `box`.
 * ids: element ids, so the page keeps its existing ids (#log, #suggest, #chat-form, #chat-input).
 * Returns { clear, focus }.
 */
export function mountChat(box, ids) {
  const name = t("chat.name");
  const ready = store.complete;
  const suggestions = t(ready ? "chat.suggestions" : "chat.generalSuggestions");
  box.innerHTML = `
    <div class="chat-notice" role="note">${icon("info")}<span><strong>${esc(t("chat.notice"))}</strong>
      ${getLang() !== "en" ? `<br>${esc(t("chat.englishOnly"))}` : ""}</span></div>
    <div class="chat-log" id="${ids.log}" aria-live="polite" aria-relevant="additions"></div>
    ${ready ? "" : `<div class="chat-tip"><a href="#/profile">${icon("user", "icon icon-sm")} ${esc(t("chat.needProfileBtn"))}</a></div>`}
    <div class="chat-suggest" id="${ids.suggest}">${suggestions.map((s) => `<button type="button" lang="en">${esc(s)}</button>`).join("")}</div>
    <form class="chat-form" id="${ids.form}">
      <label for="${ids.input}" class="sr-only">${esc(t("chat.placeholder"))}</label>
      <input id="${ids.input}" autocomplete="off" maxlength="500" placeholder="${esc(t("chat.placeholder"))}">
      <button class="btn btn-primary" type="submit">${icon("send")}<span class="sr-only">${esc(t("chat.send"))}</span></button>
    </form>`;

  const log = box.querySelector(`#${ids.log}`);
  const add = (role, text, cls = "", english = true) => {
    const row = document.createElement("div");
    row.className = `msg-row ${role}`;
    if (role === "bot") row.innerHTML = lumiFace("lumi-xs");
    const div = document.createElement("div");
    div.className = `msg ${role} ${cls}`;
    if (role === "bot" && english) div.lang = "en";
    div.textContent = text;
    row.append(div);
    log.append(row);
    log.scrollTop = log.scrollHeight;
    return div;
  };

  let history = loadHistory();
  const drawAll = () => {
    log.innerHTML = "";
    add("bot", t("chat.hello", { name }), "", getLang() === "en");
    if (!ready) add("bot", t("chat.needProfile", { page: t("nav.profile") }), "", getLang() === "en");
    history.forEach((m) => add(m.role === "user" ? "user" : "bot", m.content, m.safe ? "safe" : ""));
  };
  drawAll();

  const input = box.querySelector(`#${ids.input}`);
  {
    let busy = false;
    const ask = async (text) => {
      const message = text.trim();
      if (!message || busy) return;
      busy = true;
      add("user", message);
      const typing = add("bot", "");
      typing.innerHTML = `<span class="typing" aria-label="${esc(t("chat.thinking"))}"><i></i><i></i><i></i></span>`;
      box.classList.add("is-thinking");
      try {
        const past = history.map(({ role, content }) => ({ role, content }));
        // With a profile: answers about the student's own results; before it: general questions about the app.
        const reply = ready ? await api.chat(store.answers, message, past) : await api.chatGeneral(message, past);
        typing.textContent = reply.reply;
        const safe = ["guard", "out_of_scope"].includes(reply.source);
        if (safe) typing.classList.add("safe");
        history = [...history, { role: "user", content: message }, { role: "assistant", content: reply.reply, safe }];
        saveHistory(history);
      } catch {
        typing.textContent = t("chat.unavailable");
        typing.classList.add("safe");
      } finally {
        busy = false;
        box.classList.remove("is-thinking");
        log.scrollTop = log.scrollHeight;
      }
    };
    box.querySelector(`#${ids.form}`).addEventListener("submit", (e) => {
      e.preventDefault();
      ask(input.value);
      input.value = "";
    });
    box.querySelectorAll(`#${ids.suggest} button`).forEach((b) => b.addEventListener("click", () => ask(b.textContent)));
  }

  return {
    clear() { history = []; saveHistory(history); drawAll(); },
    focus() { input.focus(); },
  };
}
