// 工具栏只使用这一组 24×24 线性图标，颜色与线宽由统一样式控制
const drawings = {
  book: '<path d="M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-3H4z"/><path d="M20 4h-4a3 3 0 0 0-3 3v14a4 4 0 0 1 4-3h3z"/>',
  directory: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16m4-11h4m-4 5h4"/>',
  source: '<path d="M8 4H4v16h4m8-16h4v16h-4M10 9l-3 3 3 3m4-6 3 3-3 3"/>',
  glossary: '<path d="M4 5h8v14H4zM12 5h8v14h-8M7 9h2m-2 4h2m6-4h2m-2 4h2"/>',
  focus: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5M8 8h8v8H8z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
  moon: '<path d="M20 15a8.5 8.5 0 0 1-11-11 8.5 8.5 0 1 0 11 11Z"/>',
  settings: '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="8" cy="18" r="2"/>',
  close: '<path d="m6 6 12 12M18 6 6 18"/>',
  reset: '<path d="M4 10a8 8 0 1 1 1 8M4 4v6h6"/>',
  minus: '<path d="M5 12h14"/>',
  plus: '<path d="M5 12h14M12 5v14"/>',
  expand: '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
  pin: '<path d="m16 3 5 5-3 1-4 4v4l-3-3-6 6m6-9-3-3h4l4-4z"/>',
  fit: '<rect x="4" y="6" width="16" height="12" rx="1"/><path d="M2 12h5m10 0h5M12 3v5m0 8v5"/>',
  notes: '<path d="M4 4h16v12H9l-5 4zM8 8h8m-8 4h5"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  external: '<path d="M14 3h7v7m0-7L10 14M10 4H4v16h16v-6"/>',
  play: '<path d="m8 4 12 8-12 8z"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  previous: '<path d="m14 6-6 6 6 6"/>',
  next: '<path d="m10 6 6 6-6 6"/>',
  target: '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3"/>'
};
window.uiIcon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${drawings[name] || drawings.book}</svg>`;
