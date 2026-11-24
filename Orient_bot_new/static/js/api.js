const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }
const headers = { 'X-Telegram-Init-Data': tg?.initData || '' };
const jsonHeaders = { ...headers, 'Content-Type': 'application/json' };

/* Экранирование пользовательских данных перед вставкой в innerHTML (защита от XSS). */
function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function mediaUrl(path) {
  if (!path) return '';
  if (/^https?:\/\//i.test(path)) return path;
  return '/' + String(path).replace(/^\/+/, '');
}

function fmtDate(iso) {
  if (!iso) return '';
  const hasTz = /([zZ]|[+-]\d\d:?\d\d)$/.test(iso);
  const d = new Date(hasTz ? iso : iso + 'Z');
  return isNaN(d) ? '' : d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function notify(message) {
  if (tg && tg.showAlert) tg.showAlert(String(message));
  else alert(message);
}

function askConfirm(message) {
  return new Promise((resolve) => {
    if (tg && tg.showConfirm) tg.showConfirm(message, (ok) => resolve(!!ok));
    else resolve(window.confirm(message));
  });
}

let _authWarned = false;
async function apiRequest(url, options = {}) {
  let response;
  try {
    response = await fetch(url, { ...options, headers: { ...headers, ...(options.headers || {}) } });
  } catch (e) {
    return { __error: true, detail: 'Нет соединения с сервером', status: 0 };
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401 && !_authWarned) {
      _authWarned = true;
      notify('Сессия устарела или приложение открыто вне Telegram. Закройте и откройте мини-приложение заново.');
    }
    let detail = data.detail;
    if (Array.isArray(detail)) detail = 'Проверьте заполнение полей';
    return { __error: true, detail: detail || `Ошибка запроса (${response.status})`, status: response.status };
  }
  return data;
}
const isError = (r) => !r || r.__error === true;
async function apiGet(url) { return apiRequest(url); }
async function apiPost(url, body) { return apiRequest(url, { method: 'POST', headers: jsonHeaders, body: JSON.stringify(body ?? {}) }); }
async function apiPut(url, body) { return apiRequest(url, { method: 'PUT', headers: jsonHeaders, body: JSON.stringify(body ?? {}) }); }
async function apiForm(url, method, formData) { return apiRequest(url, { method, body: formData }); }
async function apiDelete(url) { return apiRequest(url, { method: 'DELETE' }); }
