// Ask the Chatbot: the full-page conversation with Lumi (the same chat as the floating window).
import { t } from "../i18n.js";
import { icon } from "../icons.js";
import { lumiFace, mountChat } from "../lumi.js";
import { store } from "../store.js";
import { esc, exampleBanner, journey, needProfile, pageHead } from "../ui.js";

export async function render(root) {
  const head = pageHead(t("chat.title"), t("chat.sub"));
  if (!store.complete) { root.innerHTML = `<div class="page">${head}${needProfile()}</div>`; return; }

  root.innerHTML = `<div class="page">${head}${journey("chat")}${exampleBanner()}
    <section class="card chat" aria-label="${esc(t("chat.title"))}">
      <div class="chat-head">${lumiFace("lumi-md")}<div><div class="chat-name">${esc(t("chat.name"))}</div>
        <div class="chat-role"><span class="dot" aria-hidden="true"></span>${esc(t("chat.role"))}</div></div></div>
      <div class="chat-body" id="chat-body"></div>
    </section>
    <div class="actions"><button class="btn btn-quiet" id="clear">${icon("trash")} ${esc(t("chat.clear"))}</button></div>
  </div>`;

  const chat = mountChat(root.querySelector("#chat-body"), { log: "log", suggest: "suggest", form: "chat-form", input: "chat-input" });
  root.querySelector("#clear").addEventListener("click", () => chat.clear());
}
