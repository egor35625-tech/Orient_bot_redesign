const SECTIONS = ['market', 'shops', 'favs', 'orders', 'myads', 'profile', 'settings', 'info'];

function showSection(name) {
  SECTIONS.forEach((t) => {
    document.getElementById('tab-' + t)?.classList.toggle('hidden', t !== name);
  });
  document.querySelectorAll('[data-nav]').forEach((b) => b.classList.toggle('active', b.dataset.nav === name));
  document.getElementById('itemDetailModal')?.classList.add('hidden');
  window.scrollTo({ top: 0, behavior: 'instant' });
}

function currentSection() {
  return SECTIONS.find((t) => !document.getElementById('tab-' + t)?.classList.contains('hidden'));
}

function navigate(name) {
  closeDrawer();
  showSection(name);
  if (name === 'market') loadMarket(true);
  else if (name === 'shops') { closeShopItems(); loadShops(); }
  else if (name === 'favs') renderFavs();
  else if (name === 'orders') loadPurchases();
  else if (name === 'myads') loadMyAds();
  else if (name === 'profile') loadProfile();
}
const activateTab = navigate; // совместимость со старым кодом

document.querySelectorAll('[data-nav]').forEach((btn) => {
  btn.addEventListener('click', () => navigate(btn.dataset.nav));
});

/* ---------- Боковое меню ---------- */
function updateDrawerProfile() {
  const u = tg?.initDataUnsafe?.user || {};
  const name = [u.first_name, u.last_name].filter(Boolean).join(' ') || me.first_name || 'Гость';
  const handle = me.tg_username || me.telegram_username || u.username;
  document.getElementById('drawerName').textContent = name;
  document.getElementById('drawerHandle').textContent = handle ? '@' + handle : '';
  const av = document.getElementById('drawerAvatar');
  if (u.photo_url) av.innerHTML = `<img src="${esc(u.photo_url)}" alt="">`;
  else av.textContent = (name.trim()[0] || 'G').toUpperCase();
}

function openDrawer() {
  updateDrawerProfile();
  document.getElementById('drawer').classList.add('open');
  document.getElementById('drawer').setAttribute('aria-hidden', 'false');
  document.getElementById('drawerOverlay').classList.add('open');
  document.body.classList.add('drawer-open');
}
function closeDrawer() {
  document.getElementById('drawer')?.classList.remove('open');
  document.getElementById('drawer')?.setAttribute('aria-hidden', 'true');
  document.getElementById('drawerOverlay')?.classList.remove('open');
  document.body.classList.remove('drawer-open');
}
document.getElementById('menuBtn')?.addEventListener('click', openDrawer);
document.getElementById('brandBtn')?.addEventListener('click', openDrawer);
document.getElementById('drawerClose')?.addEventListener('click', closeDrawer);
document.getElementById('drawerOverlay')?.addEventListener('click', closeDrawer);
document.getElementById('drawerExit')?.addEventListener('click', () => {
  closeDrawer();
  if (tg && tg.close) tg.close();
});

/* ---------- Поиск ---------- */
document.getElementById('searchToggle')?.addEventListener('click', () => {
  if (currentSection() === 'shops') { document.getElementById('shopSearchInput')?.focus(); return; }
  if (currentSection() !== 'market') navigate('market');
  const bar = document.getElementById('searchBar');
  const show = bar.classList.contains('hidden');
  bar.classList.toggle('hidden', !show);
  if (show) document.getElementById('searchInput').focus();
});

document.getElementById('themeSelect')?.addEventListener('change', (e) => {
  const theme = e.target.value;
  try { localStorage.setItem('theme', theme); } catch (err) { /* ignore */ }
  applyTheme(theme);
});

/* Контакты: открыть Telegram-профиль продавца */
function openTelegramUser(username) {
  if (!username) return;
  const url = `https://t.me/${encodeURIComponent(username)}`;
  if (tg && tg.openTelegramLink) tg.openTelegramLink(url);
  else window.open(url, '_blank');
}

function externalLink(raw) {
  if (!raw) return '';
  const s = String(raw).trim();
  if (/^https?:\/\//i.test(s)) return s;
  return 'https://' + s.replace(/^@+/, '');
}
