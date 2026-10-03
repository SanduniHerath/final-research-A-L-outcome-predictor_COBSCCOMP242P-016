// Talks to the Phase 9 backend. Results are kept in memory for the current profile only.

const cache = new Map();

async function request(path, body) {
  const options = body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : {};
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
  clear: () => { for (const key of [...cache.keys()]) if (!["questions", "examples", "stats"].includes(key)) cache.delete(key); },
};
