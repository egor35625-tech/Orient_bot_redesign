let me = { loaded: false, is_registered: false, is_admin: false, tg_username: null, telegram_username: null, city: null, default_address: null, first_name: null };
let _regResolver = null;

async function refreshMe() {
  const data = await apiGet('/api/profile');
  if (isError(data)) return me;
  me = { ...data, loaded: true };
  document.getElementById('adminLinkCard')?.classList.toggle('hidden', !me.is_admin);
  return me;
}

function showRegModal() {
  const input = document.getElementById('regUsername');
  input.value = me.tg_username ? '@' + me.tg_username : (me.telegram_username ? '@' + me.telegram_username : '');
  document.getElementById('regError').classList.add('hidden');
  document.getElementById('regModal').classList.remove('hidden');
}

function hideRegModal(result) {
  document.getElementById('regModal').classList.add('hidden');
  if (_regResolver) { _regResolver(result); _regResolver = null; }
}

/* Для действий, требующих регистрации: true — можно продолжать. */
function requireRegistered() {
  if (me.is_registered) return Promise.resolve(true);
  return new Promise((resolve) => { _regResolver = resolve; showRegModal(); });
}

document.getElementById('regSubmitBtn')?.addEventListener('click', async () => {
  const errBox = document.getElementById('regError');
  const username = document.getElementById('regUsername').value.trim();
  if (!username) {
    errBox.textContent = 'Укажите ваш @username в Telegram';
    errBox.classList.remove('hidden');
    return;
  }
  const res = await apiPut('/api/profile', { tg_username: username });
  if (isError(res)) {
    errBox.textContent = res.detail;
    errBox.classList.remove('hidden');
    return;
  }
  me = { ...res, loaded: true };
  document.getElementById('adminLinkCard')?.classList.toggle('hidden', !me.is_admin);
  hideRegModal(true);
  notify('Регистрация завершена!');
});

document.getElementById('regCancelBtn')?.addEventListener('click', () => hideRegModal(false));

async function loadProfile() {
  await refreshMe();
  const u = document.getElementById('profileUsername');
  if (u) u.value = me.tg_username ? '@' + me.tg_username : (me.telegram_username ? '@' + me.telegram_username : '');
  const c = document.getElementById('profileCity');
  if (c) c.value = me.city || '';
  const a = document.getElementById('profileAddress');
  if (a) a.value = me.default_address || '';
  await checkShopStatus();
}

document.getElementById('saveProfileBtn')?.addEventListener('click', async () => {
  const username = document.getElementById('profileUsername').value.trim();
  if (!username) { notify('Укажите ваш @username в Telegram'); return; }
  const res = await apiPut('/api/profile', {
    tg_username: username,
    city: document.getElementById('profileCity').value.trim(),
    default_address: document.getElementById('profileAddress').value.trim(),
  });
  if (isError(res)) { notify(res.detail); return; }
  me = { ...res, loaded: true };
  notify('Профиль сохранён!');
});

document.getElementById('openAdminBtn')?.addEventListener('click', () => { window.location.href = '/admin'; });
