// Talks to the Phase 9 backend. Results are kept in memory for the current profile only.
// Every request carries this browser's random visit code; the server saves answers and results
// under it in the app database (backend/storage.py), and deletes them on request (forget()).

const cache = new Map();
const SESSION = "alora.session";
const LANG = "alora.lang";
let memorySession = null;  // used when localStorage is blocked (private mode)

function newCode() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

function session() {
  try {
    let code = localStorage.getItem(SESSION);
    if (!code) { code = newCode(); localStorage.setItem(SESSION, code); }
    return code;
  } catch {
    memorySession ??= newCode();
    return memorySession;
  }
}

function headers() {
  let lang = "en";
  try { lang = JSON.parse(localStorage.getItem(LANG)) || "en"; } catch { /* ignore */ }
  return { "X-Alora-Session": session(), "X-Alora-Lang": lang };
}

async function request(path, body, method) {
  const options = body
    ? { method: "POST", headers: { "Content-Type": "application/json", ...headers() }, body: JSON.stringify(body) }
    : { method: method || "GET", headers: headers() };
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = "";
    try { detail = (await response.json()).detail; } catch { /* ignore */ }
    const error = new Error(typeof detail === "string" ? detail : `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function cached(key, make) {
  if (!cache.has(key)) {
    const promise = make().catch((err) => { cache.delete(key); throw err; });
    cache.set(key, promise);
  }
  return cache.get(key);
}

export const api = {
  questions: () => cached("questions", () => request("/api/questions")),
  examples: () => cached("examples", () => request("/api/examples")),
  stats: () => cached("stats", () => request("/api/stats")),
  predict: (profile) => cached("predict" + JSON.stringify(profile), () => request("/api/predict", { profile })),
  gap: (profile) => cached("gap" + JSON.stringify(profile), () => request("/api/gap", { profile })),
  recommend: (profile) => cached("rec" + JSON.stringify(profile), () => request("/api/recommend", { profile })),
  explain: (profile) => cached("why" + JSON.stringify(profile), () => request("/api/explain", { profile, include_degree: true })),
  chat: (profile, message, history) => request("/api/chat", { profile, message, history }),
  // Before the profile is filled in: general questions about the app (same safety checks).
  chatGeneral: (message, history) => request("/api/chat/general", { message, history }),
  // Delete everything the server stored for this browser, then start a new visit code.
  forget: async () => {
    try { await request("/api/my-data", null, "DELETE"); } finally {
      try { localStorage.removeItem(SESSION); } catch { /* ignore */ }
      memorySession = null;
    }
  },
  clear: () => { for (const key of [...cache.keys()]) if (!["questions", "examples", "stats"].includes(key)) cache.delete(key); },
};
