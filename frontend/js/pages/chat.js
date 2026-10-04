// Ask the Chatbot: the support-tool notice is always visible above the conversation.
import { api } from "../api.js";
import { getLang, t } from "../i18n.js";
import { icon } from "../icons.js";
import { store } from "../store.js";
import { esc, exampleBanner, journey, needProfile, pageHead } from "../ui.js";

const KEY = "alora.chat";
function loadHistory() { try { return JSON.parse(sessionStorage.getItem(KEY)) || []; } catch { return []; } }
function saveHistory(h) { try { sessionStorage.setItem(KEY, JSON.stringify(h.slice(-20))); } catch { /* ignore */ } }

export async function render(root) {
  const head = pageHead(t("chat.title"), t("chat.sub"));
  if (!store.complete) { root.innerHTML = `<div class="page">${head}${needProfile()}</div>`; return; }
  let history = loadHistory();

  root.innerHTML = `<div class="page">${head}${journey("chat")}${exampleBanner()}
    <section class="card chat" aria-label="${esc(t("chat.title"))}">
      <div class="chat-notice" role="note">${icon("info")}<span><strong>${esc(t("chat.notice"))}</strong>
        ${getLang() !== "en" ? `<br>${esc(t("chat.englishOnly"))}` : ""}</span></div>
      <div class="chat-log" id="log" aria-live="polite" aria-relevant="additions"></div>
      <div class="chat-suggest" id="suggest">${t("chat.suggestions").map((s) => `<button type="button" lang="en">${esc(s)}</button>`).join("")}</div>
      <form class="chat-form" id="chat-form">
        <label for="chat-input" class="sr-only">${esc(t("chat.placeholder"))}</label>
        <input id="chat-input" autocomplete="off" maxlength="500" placeholder="${esc(t("chat.placeholder"))}">
        <button class="btn btn-primary" type="submit">${icon("send")}<span class="sr-only">${esc(t("chat.send"))}</span></button>
      </form>
    </section>
    <div class="actions"><button class="btn btn-quiet" id="clear">${icon("trash")} ${esc(t("chat.clear"))}</button></div>
  </div>`;

  const log = root.querySelector("#log");
  const add = (role, text, cls = "") => {
    const div = document.createElement("div");
    div.className = `msg ${role} ${cls}`;
    if (role === "bot") div.lang = "en";
    div.textContent = text;
    log.append(div);
    log.scrollTop = log.scrollHeight;
    return div;
  };
  const drawAll = () => {
    log.innerHTML = "";
    add("bot", t("chat.hello"));
    history.forEach((m) => add(m.role === "user" ? "user" : "bot", m.content, m.safe ? "safe" : ""));
  };
  drawAll();

  let busy = false;
  const ask = async (text) => {
    const message = text.trim();
    if (!message || busy) return;
    busy = true;
    add("user", message);
    const typing = add("bot", "");
    typing.innerHTML = `<span class="typing" aria-label="${esc(t("chat.thinking"))}"><i></i><i></i><i></i></span>`;
    try {
      const reply = await api.chat(store.answers, message, history.map(({ role, content }) => ({ role, content })));
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
      log.scrollTop = log.scrollHeight;
    }
  };

  root.querySelector("#chat-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = root.querySelector("#chat-input");
    ask(input.value);
    input.value = "";
  });
  root.querySelectorAll("#suggest button").forEach((b) => b.addEventListener("click", () => ask(b.textContent)));
  root.querySelector("#clear").addEventListener("click", () => { history = []; saveHistory(history); drawAll(); });
}
