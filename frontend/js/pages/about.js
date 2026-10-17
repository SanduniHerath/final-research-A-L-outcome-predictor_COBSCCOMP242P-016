// About and Help: what the app is, how to use it, questions and answers, where to get help.
import { t } from "../i18n.js";
import { api } from "../api.js";
import { icon } from "../icons.js";
import { store } from "../store.js";
import { esc, pageHead, toast } from "../ui.js";

export async function render(root) {
  root.innerHTML = `<div class="page">${pageHead(t("about.title"), t("about.sub"))}
    <section class="card"><h2>${icon("compass")} ${esc(t("about.whatTitle"))}</h2><p>${esc(t("about.whatBody"))}</p>
      <h3>${esc(t("about.partsTitle"))}</h3>
      <div class="grid-3">${t("about.parts").map(([name, body], i) => `<div><strong>${icon(["chart", "target", "list", "bulb", "chat"][i], "icon icon-sm")} ${esc(name)}</strong>
        <p class="small muted">${esc(body)}</p></div>`).join("")}</div></section>

    <div class="grid-2">
      <section class="card"><h2>${icon("list")} ${esc(t("about.howTitle"))}</h2>
        <ol>${t("about.how").map((s) => `<li>${esc(s)}</li>`).join("")}</ol></section>
      <section class="card"><h2>${icon("info")} ${esc(t("about.limitsTitle"))}</h2>
        <ul>${t("about.limits").map((s) => `<li class="small">${esc(s)}</li>`).join("")}</ul></section>
    </div><br>

    <section class="card faq"><h2>${esc(t("about.faqTitle"))}</h2>
      ${t("about.faq").map(([q, a]) => `<details><summary>${icon("chev", "icon chev")}${esc(q)}</summary><div><p>${esc(a)}</p></div></details>`).join("")}
    </section>

    <div class="grid-2">
      <section class="card"><h2>${icon("people")} ${esc(t("about.helpTitle"))}</h2><p>${esc(t("about.helpBody"))}</p>
        <h3>${icon("heart")} ${esc(t("about.feelTitle"))}</h3><p>${esc(t("about.feelBody"))}</p>
        <a class="btn btn-secondary" href="tel:1926">${icon("phone")} 1926</a></section>
      <section class="card"><h2>${icon("trash")} ${esc(t("about.deleteTitle"))}</h2><p>${esc(t("about.deleteBody"))}</p>
        <button class="btn btn-danger" id="delete">${icon("trash")} ${esc(t("profile.reset"))}</button></section>
    </div>
  </div>`;
  root.querySelector("#delete").addEventListener("click", async () => {
    if (!window.confirm(t("profile.resetConfirm"))) return;
    let ok = true;
    try { await api.forget(); } catch { ok = false; }  // also delete what the server stored
    store.reset();
    try { sessionStorage.clear(); } catch { /* ignore */ }
    toast(t(ok ? "profile.deleted" : "profile.deleteFailed"));
  });
}
