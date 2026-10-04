// Text lookup for English, Sinhala and Tamil. Missing keys fall back to English.
import en from "../i18n/en.js";
import si from "../i18n/si.js";
import ta from "../i18n/ta.js";

const DICTS = { en, si, ta };
let current = "en";

function lookup(dict, key) {
  return key.split(".").reduce((node, part) => (node == null ? undefined : node[part]), dict);
}

export function setLang(lang) {
  current = DICTS[lang] ? lang : "en";
  document.documentElement.lang = current;
}
export function getLang() { return current; }

export function t(key, params = {}) {
  let value = lookup(DICTS[current], key);
  if (value === undefined || value === "") value = lookup(en, key);
  if (value === undefined) return key;
  if (typeof value !== "string") return value;
  return value.replace(/\{(\w+)\}/g, (match, name) => (params[name] ?? match));
}

// Answer options and names whose keys contain dots or spaces: direct map lookup.
export function label(group, value, field = null) {
  const path = field ? [group, field] : [group];
  const pick = (dict) => path.reduce((node, part) => node?.[part], dict)?.[value];
  return pick(DICTS[current]) || pick(en) || value;
}

export function applyStatic(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  root.querySelectorAll("[data-i18n-aria]").forEach((el) => { el.setAttribute("aria-label", t(el.dataset.i18nAria)); });
}

export function fmt(x, digits = 2) {
  return Number(x).toFixed(digits);
}
