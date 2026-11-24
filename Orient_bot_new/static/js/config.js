const THEMES = {
  default: { bg: '#FFF5E1', card: '#FFFBF1', surface: '#F8EBD2', text: '#3a0510', muted: '#8a6a6e', accent: '#800020', accentText: '#FFF5E1', border: 'rgba(128,0,32,0.14)' },
  light:   { bg: '#ffffff', card: '#fbfbfb', surface: '#f2f0ee', text: '#1d0a0e', muted: '#7d6d70', accent: '#800020', accentText: '#FFF5E1', border: 'rgba(128,0,32,0.14)' },
  dark:    { bg: '#1c0a10', card: '#2a1119', surface: '#3a1823', text: '#FFF5E1', muted: '#b99ca2', accent: '#b0173d', accentText: '#FFF5E1', border: 'rgba(255,245,225,0.12)' },
};

function applyTheme(themeName) {
  const t = THEMES[themeName] || THEMES.default;
  const root = document.documentElement.style;
  root.setProperty('--bg', t.bg);
  root.setProperty('--bg-card', t.card);
  root.setProperty('--surface', t.surface);
  root.setProperty('--text', t.text);
  root.setProperty('--text-muted', t.muted);
  root.setProperty('--accent', t.accent);
  root.setProperty('--accent-text', t.accentText);
  root.setProperty('--border', t.border);
  try {
    const tgw = window.Telegram && window.Telegram.WebApp;
    if (tgw && tgw.setHeaderColor) { tgw.setHeaderColor(t.bg); tgw.setBackgroundColor(t.bg); }
    if (tgw && tgw.setBottomBarColor) tgw.setBottomBarColor(t.card);
  } catch (e) { /* старые версии Telegram */ }
}

function loadSavedTheme() {
  let theme = 'default';
  try { theme = localStorage.getItem('theme') || 'default'; } catch (e) { /* storage недоступен */ }
  if (!THEMES[theme]) theme = 'default';
  applyTheme(theme);
  const sel = document.getElementById('themeSelect');
  if (sel) sel.value = theme;
}
