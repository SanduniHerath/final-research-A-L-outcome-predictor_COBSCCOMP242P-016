// Checks that si.js and ta.js have the same text keys as en.js.
// Usage: node frontend/tools/check_i18n.mjs   (exit code 1 if a key is missing or misspelled)
import en from "../i18n/en.js";
import si from "../i18n/si.js";
import ta from "../i18n/ta.js";

// Keys deliberately left to the English fallback.
const ALLOWED_MISSING = new Set([
  "chat.suggestions",      // the chatbot answers in English, so its suggested questions stay English
  "chat.generalSuggestions",
  "opt.al_district",       // empty in every language (districts are under "district")
  "district",              // English shows the district names as they are
]);

function flatten(obj, prefix = "") {
  const out = new Map();
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v)) {
      for (const [kk, vv] of flatten(v, key)) out.set(kk, vv);
      if (Object.keys(v).length === 0) out.set(key, v);
    } else out.set(key, v);
  }
  return out;
}

const base = flatten(en);
let failed = false;
for (const [name, dict] of [["si", si], ["ta", ta]]) {
  const keys = flatten(dict);
  const missing = [...base.keys()].filter((k) => !keys.has(k) && ![...ALLOWED_MISSING].some((a) => k === a || k.startsWith(a + ".")));
  const extra = [...keys.keys()].filter((k) => !base.has(k) && !k.startsWith("district."));
  const arrays = [...base.entries()].filter(([k, v]) => Array.isArray(v) && keys.has(k) && keys.get(k).length !== v.length).map(([k]) => k);
  console.log(`${name}: ${keys.size} keys, missing ${missing.length}, unknown ${extra.length}, list-length mismatches ${arrays.length}`);
  for (const k of missing) console.log(`  missing: ${k}`);
  for (const k of extra) console.log(`  unknown: ${k}`);
  for (const k of arrays) console.log(`  list length differs: ${k}`);
  failed ||= missing.length > 0 || extra.length > 0 || arrays.length > 0;
}
process.exit(failed ? 1 : 0);
