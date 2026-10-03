// Runs before the page is drawn (plain script in <head>), so a dark-mode student never sees a white flash.
// The student's own choice wins; otherwise Alora follows the device setting (light or dark).
(function () {
  var saved = null;
  try { saved = JSON.parse(localStorage.getItem("alora.theme")); } catch (e) { /* private mode */ }
  var dark = saved ? saved === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = dark ? "dark" : "light";
})();
