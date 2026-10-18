// Simple line icons (24 x 24, drawn for this app). Icons always come with a text label:
// meaning is never carried by an icon or a colour alone.
const P = {
  home: '<path d="M3 11 12 4l9 7"/><path d="M5 10v10h5v-6h4v6h5V10"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
  chart: '<path d="M4 20V4"/><path d="M4 20h16"/><rect x="7" y="12" width="3" height="5" rx="1"/><rect x="12" y="8" width="3" height="9" rx="1"/><rect x="17" y="5" width="3" height="12" rx="1"/>',
  target: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1" fill="currentColor"/>',
  bulb: '<path d="M9 18h6"/><path d="M10 21h4"/><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z"/>',
  list: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="m3 6 1.5 1.5L7 5M3 12l1.5 1.5L7 11M3 18l1.5 1.5L7 17"/>',
  chat: '<path d="M4 5h16v11H9l-5 4z"/><path d="M8 9h8M8 12h5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6"/><circle cx="12" cy="7.5" r="1" fill="currentColor"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  right: '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
  left: '<path d="M19 12H5"/><path d="m11 6-6 6 6 6"/>',
  chev: '<path d="m9 6 6 6-6 6"/>',
  check: '<path d="m5 12 4.5 4.5L19 7"/>',
  checkCircle: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  alert: '<path d="M12 3 2 20h20z"/><path d="M12 10v4"/><circle cx="12" cy="17" r="1" fill="currentColor"/>',
  up: '<path d="M12 19V5"/><path d="m6 11 6-6 6 6"/>',
  down: '<path d="M12 5v14"/><path d="m6 13 6 6 6-6"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  shield: '<path d="M12 3 4 6v6c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V6z"/><path d="m9 12 2 2 4-4"/>',
  heart: '<path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5z"/>',
  send: '<path d="M4 12 20 4l-6 16-3-7z"/>',
  trash: '<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/>',
  sparkle: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 19V5"/>',
  people: '<circle cx="9" cy="9" r="3.2"/><circle cx="17" cy="10" r="2.5"/><path d="M3 20c.8-3.3 3.2-5 6-5s5.2 1.7 6 5"/><path d="M15 15.5c2.6-.4 4.6.9 5.5 3.5"/>',
  flag: '<path d="M5 21V4"/><path d="M5 4h12l-2 4 2 4H5"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 3 2.5 15 0 18M12 3c-2.5 3-2.5 15 0 18"/>',
  phone: '<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a1 1 0 0 1-1 1A16 16 0 0 1 4 5a1 1 0 0 1 1-1z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M18.7 5.3l-1.8 1.8M7.1 16.9l-1.8 1.8"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
};

export function icon(name, cls = "icon") {
  return `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${P[name] || ""}</svg>`;
}

export function fillIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((el) => {
    el.outerHTML = icon(el.dataset.icon);
  });
}
