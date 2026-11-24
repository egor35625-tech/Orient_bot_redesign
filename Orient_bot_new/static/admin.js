const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }
const headers = { 'X-Telegram-Init-Data': tg?.initData || '', 'Content-Type': 'application/json' };

let stagesCache = [];

// Tabs
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    ['shops', 'orders', 'kanban', 'stages', 'reviews'].forEach(t => {
      document.getElementById('atab-' + t).classList.toggle('hidden', t !== btn.dataset.atab);
    });
    if (btn.dataset.atab === 'shops') loadShopModeration();
    if (btn.dataset.atab === 'orders') { loadStats(); loadOrders(); }
    if (btn.dataset.atab === 'kanban') loadKanban();
    if (btn.dataset.atab === 'stages') loadStagesAdmin();
    if (btn.dataset.atab === 'reviews') loadAdminReviews();
  });
});

function showModal(title, placeholder = '', multiline = false) {
  return new Promise((resolve) => {
    const modal = document.getElementById('modal');
    const input = document.getElementById('modalInput');
    document.getElementById('modalTitle').textContent = title;
    input.value = '';
    input.placeholder = placeholder;
    input.style.minHeight = multiline ? '120px' : '44px';
    modal.classList.remove('hidden');
    const close = (value) => {
      modal.classList.add('hidden');
      document.getElementById('modalOk').onclick = null;
      document.getElementById('modalCancel').onclick = null;
      resolve(value);
    };
    document.getElementById('modalOk').onclick = () => close(input.value.trim());
    document.getElementById('modalCancel').onclick = () => close(null);
  });
}

async function loadStages() {
  const resp = await fetch('/api/admin/stages', { headers });
  if (resp.ok) stagesCache = await resp.json();
  return stagesCache;
}

async function loadStats() {
  const resp = await fetch('/api/admin/stats', { headers });
  if (!resp.ok) return;
  const data = await resp.json();
  const el = document.getElementById('stats');
  el.innerHTML = '';
  [['Всего', data.total], ['Активные', data.active], ['Выполненные', data.completed], ['Отклонённые', data.rejected]].forEach(([k, v]) => {
    const p = document.createElement('p');
    p.textContent = `${k}: ${v}`;
    el.appendChild(p);
  });
}

async function loadOrders() {
  const status = document.getElementById('statusFilter').value;
  const q = document.getElementById('search').value;
  const promo = document.getElementById('promoFilter').checked;
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  if (q) params.append('q', q);
  if (promo) params.append('promo', '1');
  const [resp] = await Promise.all([fetch('/api/admin/orders?' + params, { headers }), loadStages()]);
  if (!resp.ok) return;
  const orders = await resp.json();
  const container = document.getElementById('orders');
  container.innerHTML = '';
  orders.forEach(o => container.appendChild(renderOrderCard(o)));
}

function renderOrderCard(o) {
  const div = document.createElement('div');
  div.className = 'order-card';

  const h3 = document.createElement('h3');
  h3.textContent = `#${o.id} — ${o.current_stage?.label || o.status}`;
  div.appendChild(h3);

  const rows = [
    ['📝', o.description],
    ['💬', o.additional_comment],
    ['📞', o.phone],
    ['✉️', o.email],
    ['📍', o.delivery_address],
    ['🎁', o.promo_code],
    ['💰', o.price ? `${o.price} ${o.currency}` : null],
    ['👤', o.user ? `${o.user.first_name || '—'} @${o.user.username || '—'}` : null],
  ];
  rows.forEach(([icon, val]) => {
    if (!val) return;
    const p = document.createElement('p');
    p.textContent = `${icon} ${val}`;
    div.appendChild(p);
  });

  if (o.messages && o.messages.length) {
    const hist = document.createElement('div');
    hist.className = 'history';
    o.messages.slice(-10).forEach(m => {
      const line = document.createElement('div');
      line.textContent = `${m.sender_id === o.user?.telegram_id ? '👤' : '👨‍💼'} ${m.message_text}`;
      hist.appendChild(line);
    });
    div.appendChild(hist);
  }

  const actions = document.createElement('div');
  actions.className = 'actions';
  const addBtn = (text, fn) => {
    const b = document.createElement('button');
    b.textContent = text;
    b.onclick = fn;
    actions.appendChild(b);
  };

  addBtn('◀', async () => {
    await fetch(`/api/admin/orders/${o.id}/stage/prev`, { method: 'POST', headers });
    loadOrders();
  });
  addBtn('▶', async () => {
    await fetch(`/api/admin/orders/${o.id}/stage/next`, { method: 'POST', headers });
    loadOrders();
  });
  addBtn('💰 Цена', async () => {
    const price = await showModal('Введите стоимость', '35 €');
    if (!price) return;
    await fetch(`/api/admin/orders/${o.id}/price`, { method: 'POST', headers, body: JSON.stringify({ price, currency: '€' }) });
    loadOrders();
  });
  addBtn('💬 Ответить', async () => {
    const text = await showModal('Сообщение клиенту', 'Текст...', true);
    if (!text) return;
    await fetch(`/api/admin/orders/${o.id}/reply`, { method: 'POST', headers, body: JSON.stringify({ text }) });
    loadOrders();
  });
  addBtn('✅ Завершить', async () => {
    await fetch(`/api/admin/orders/${o.id}/complete`, { method: 'POST', headers });
    loadOrders();
  });
  addBtn('❌ Отклонить', async () => {
    await fetch(`/api/admin/orders/${o.id}/reject`, { method: 'POST', headers });
    loadOrders();
  });
  div.appendChild(actions);
  return div;
}

async function loadKanban() {
  const [ordersResp, stages] = await Promise.all([
    fetch('/api/admin/orders', { headers }),
    loadStages(),
  ]);
  if (!ordersResp.ok) return;
  const orders = await ordersResp.json();
  const container = document.getElementById('kanban');
  container.innerHTML = '';
  stages.forEach(stage => {
    const col = document.createElement('div');
    col.className = 'kanban-col';
    const title = document.createElement('h3');
    title.textContent = `${stage.label}`;
    col.appendChild(title);
    const stageOrders = orders.filter(o => o.current_stage?.id === stage.id);
    const count = document.createElement('p');
    count.className = 'hint';
    count.textContent = `${stageOrders.length} заказов`;
    col.appendChild(count);
    stageOrders.forEach(o => {
      const card = document.createElement('div');
      card.className = 'kanban-card';
      card.textContent = `#${o.id} — ${o.description.slice(0, 40)}`;
      col.appendChild(card);
    });
    container.appendChild(col);
  });
}

async function loadStagesAdmin() {
  const stages = await loadStages();
  const list = document.getElementById('stagesList');
  list.innerHTML = '';
  stages.forEach((s, i) => {
    const row = document.createElement('div');
    row.className = 'stage-row';
    const label = document.createElement('span');
    label.textContent = `${s.position}. ${s.label}${s.is_final ? ' (финал)' : ''}${s.is_rejected ? ' (отклонён)' : ''}`;
    row.appendChild(label);
    const actions = document.createElement('div');
    actions.className = 'actions';
    const up = document.createElement('button');
    up.textContent = '↑';
    up.onclick = () => reorderStages(i, i - 1);
    actions.appendChild(up);
    const down = document.createElement('button');
    down.textContent = '↓';
    down.onclick = () => reorderStages(i, i + 1);
    actions.appendChild(down);
    const edit = document.createElement('button');
    edit.textContent = '✏️';
    edit.onclick = async () => {
      const newLabel = await showModal('Название этапа', s.label);
      if (newLabel) {
        await fetch(`/api/admin/stages/${s.id}`, { method: 'PATCH', headers, body: JSON.stringify({ label: newLabel }) });
        loadStagesAdmin();
      }
    };
    actions.appendChild(edit);
    const del = document.createElement('button');
    del.textContent = '🗑';
    del.onclick = async () => {
      const resp = await fetch(`/api/admin/stages/${s.id}`, { method: 'DELETE', headers });
      if (!resp.ok) {
        const err = await resp.json();
        alert(err.detail || 'Не удалось удалить');
      }
      loadStagesAdmin();
    };
    actions.appendChild(del);
    row.appendChild(actions);
    list.appendChild(row);
  });
}

async function reorderStages(from, to) {
  if (to < 0 || to >= stagesCache.length) return;
  const ids = stagesCache.map(s => s.id);
  [ids[from], ids[to]] = [ids[to], ids[from]];
  await fetch('/api/admin/stages/reorder', { method: 'POST', headers, body: JSON.stringify({ ids }) });
  loadStagesAdmin();
}

document.getElementById('addStage').onclick = async () => {
  const label = document.getElementById('newStageLabel').value.trim();
  if (!label) return;
  await fetch('/api/admin/stages', { method: 'POST', headers, body: JSON.stringify({ label }) });
  document.getElementById('newStageLabel').value = '';
  loadStagesAdmin();
};

async function loadAdminReviews() {
  const resp = await fetch('/api/admin/reviews', { headers });
  if (!resp.ok) return;
  const reviews = await resp.json();
  const container = document.getElementById('adminReviews');
  container.innerHTML = '';
  reviews.forEach(r => {
    const div = document.createElement('div');
    div.className = 'order-card';
    const stars = document.createElement('p');
    stars.textContent = '★'.repeat(r.rating) + '☆'.repeat(5 - r.rating);
    div.appendChild(stars);
    const author = document.createElement('p');
    author.textContent = `Автор: ${r.author_name || '—'} · Заказ: ${r.order_id ? '#' + r.order_id : '—'} · ${r.status}`;
    div.appendChild(author);
    const text = document.createElement('p');
    text.textContent = r.text;
    div.appendChild(text);
    const actions = document.createElement('div');
    actions.className = 'actions';
    if (r.status !== 'published') {
      const pub = document.createElement('button');
      pub.textContent = '✅ Опубликовать';
      pub.onclick = async () => { await fetch(`/api/admin/reviews/${r.id}/publish`, { method: 'POST', headers }); loadAdminReviews(); };
      actions.appendChild(pub);
    }
    if (r.status !== 'hidden') {
      const hide = document.createElement('button');
      hide.textContent = '❌ Скрыть';
      hide.onclick = async () => { await fetch(`/api/admin/reviews/${r.id}/hide`, { method: 'POST', headers }); loadAdminReviews(); };
      actions.appendChild(hide);
    }
    div.appendChild(actions);
    container.appendChild(div);
  });
}

document.getElementById('search').addEventListener('input', loadOrders);
document.getElementById('statusFilter').addEventListener('change', loadOrders);
document.getElementById('promoFilter').addEventListener('change', loadOrders);

loadShopModeration();

// ---------- Модерация магазинов ----------
let shopSub = 'apps';

function mkEl(tag, text, cls) {
  const el = document.createElement(tag);
  if (text !== undefined && text !== null) el.textContent = text;
  if (cls) el.className = cls;
  return el;
}

function mkBtn(text, fn, cls) {
  const b = mkEl('button', text, cls);
  b.onclick = fn;
  return b;
}

function askConfirm(msg) {
  return new Promise((resolve) => {
    if (tg && tg.showConfirm) tg.showConfirm(msg, (ok) => resolve(!!ok));
    else resolve(window.confirm(msg));
  });
}

async function apiCall(url, method, body) {
  const resp = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined });
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) { alert(data.detail || 'Ошибка запроса'); return null; }
  return data;
}

document.querySelectorAll('[data-shopsub]').forEach((chip) => {
  chip.addEventListener('click', () => {
    shopSub = chip.dataset.shopsub;
    document.querySelectorAll('[data-shopsub]').forEach((c) => c.classList.toggle('active', c === chip));
    loadShopModeration();
  });
});
document.getElementById('shopSearch').addEventListener('input', () => {
  clearTimeout(window._shopQ);
  window._shopQ = setTimeout(loadShopModeration, 350);
});

async function loadShopModeration() {
  document.getElementById('shopApps').classList.toggle('hidden', shopSub !== 'apps');
  document.getElementById('shopList').classList.toggle('hidden', shopSub !== 'list');
  if (shopSub === 'apps') await loadShopApps(); else await loadShopList();
}

function fieldRows(card, data, current) {
  const rows = [
    ['Название', 'shop_name', 'name'], ['Описание', 'description', 'description'], ['Город', 'city', 'city'],
    ['Телефон', 'phone', 'phone'], ['Связь', 'contact_mode', 'contact_mode'],
    ['Менеджер', 'manager_username', 'manager_username'], ['ID менеджера', 'manager_telegram_id', 'manager_telegram_id'],
    ['Instagram', 'instagram_url', 'instagram_url'], ['TikTok', 'tiktok_url', 'tiktok_url'],
    ['Доставка', 'delivery_methods', 'delivery_methods'], ['Самовывоз', 'pickup_address', 'pickup_address'],
  ];
  rows.forEach(([label, key, curKey]) => {
    const val = data[key] ?? '';
    const old = current ? (current[curKey] ?? '') : null;
    const changed = current && String(val) !== String(old);
    if (!val && !changed) return;
    const p = mkEl('p', `${label}: ${val || '—'}${changed ? `   (было: ${old || '—'})` : ''}`);
    if (changed) p.style.fontWeight = '700';
    card.appendChild(p);
  });
  if (data.logo === '') card.appendChild(mkEl('p', 'Аватар: удалить', ''));
  else if (data.logo) {
    const img = document.createElement('img');
    img.src = '/' + data.logo.replace(/^\/+/, '');
    img.style.cssText = 'width:80px;height:80px;object-fit:cover;border-radius:12px;margin-top:6px;';
    card.appendChild(mkEl('p', 'Новый аватар:'));
    card.appendChild(img);
  }
}

async function loadShopApps() {
  const resp = await fetch('/api/admin/shop-applications?status=pending', { headers });
  const box = document.getElementById('shopApps');
  box.innerHTML = '';
  if (!resp.ok) { box.appendChild(mkEl('p', 'Нет доступа', 'hint')); return; }
  const apps = await resp.json();
  if (!apps.length) { box.appendChild(mkEl('p', 'Новых заявок нет', 'hint')); return; }
  apps.forEach((a) => {
    const card = mkEl('div', null, 'card');
    card.appendChild(mkEl('h3', `${a.kind === 'edit' ? '✏️ Изменение' : '🆕 Новый магазин'} #${a.id}`));
    card.appendChild(mkEl('p', `Заявитель: ${a.applicant_username ? '@' + a.applicant_username : ''} (ID ${a.applicant_telegram_id})`));
    fieldRows(card, a, a.kind === 'edit' ? a.current : null);
    const actions = mkEl('div', null, 'actions');
    actions.appendChild(mkBtn('✅ Одобрить', async () => {
      if (await apiCall(`/api/admin/shop-applications/${a.id}/approve`, 'POST')) loadShopApps();
    }));
    actions.appendChild(mkBtn('❌ Отклонить', async () => {
      const reason = await showModal('Причина отклонения (необязательно)', 'Причина...', true);
      if (reason === null) return;
      if (await apiCall(`/api/admin/shop-applications/${a.id}/reject`, 'POST', { reason })) loadShopApps();
    }, 'danger'));
    card.appendChild(actions);
    box.appendChild(card);
  });
}

async function loadShopList() {
  const q = document.getElementById('shopSearch').value.trim();
  const resp = await fetch('/api/admin/shops?' + new URLSearchParams(q ? { q } : {}), { headers });
  const box = document.getElementById('shopListItems');
  box.innerHTML = '';
  if (!resp.ok) { box.appendChild(mkEl('p', 'Нет доступа', 'hint')); return; }
  const shops = await resp.json();
  if (!shops.length) { box.appendChild(mkEl('p', 'Магазины не найдены', 'hint')); return; }
  shops.forEach((s) => {
    const card = mkEl('div', null, 'card');
    card.appendChild(mkEl('h3', `🏬 ${s.name} (#${s.id})`));
    card.appendChild(mkEl('p', `Владелец: ${s.owner_username ? '@' + s.owner_username : ''} (ID ${s.owner_telegram_id})`, 'meta'));
    card.appendChild(mkEl('p', `Город: ${s.city || '—'} • Объявлений: ${s.items_count} • Заказов: ${s.orders_count}`, 'meta'));
    if (s.status === 'blocked') {
      const until = s.blocked_until ? 'до ' + new Date(s.blocked_until).toLocaleString('ru-RU') : 'навсегда';
      card.appendChild(mkEl('p', `⛔ Заблокирован ${until}${s.block_reason ? '. Причина: ' + s.block_reason : ''}`, 'alert'));
    }
    const actions = mkEl('div', null, 'actions');
    if (s.status === 'blocked') {
      actions.appendChild(mkBtn('✅ Разблокировать', async () => {
        if (await apiCall(`/api/admin/shops/${s.id}/unblock`, 'POST')) loadShopList();
      }));
    }
    actions.appendChild(mkBtn('⛔ Заблокировать', async () => {
      const days = await showModal('Срок блокировки в днях (пусто — навсегда)', '7');
      if (days === null) return;
      if (days && !/^\d+$/.test(days)) { alert('Введите число дней'); return; }
      const reason = await showModal('Причина блокировки', 'Причина...', true);
      if (reason === null) return;
      if (await apiCall(`/api/admin/shops/${s.id}/block`, 'POST', { days: days ? Number(days) : null, reason })) loadShopList();
    }));
    actions.appendChild(mkBtn('🗑 Удалить', async () => {
      if (!(await askConfirm(`Удалить магазин «${s.name}» вместе с товарами, заказами и отзывами? Это необратимо.`))) return;
      if (await apiCall(`/api/admin/shops/${s.id}`, 'DELETE')) loadShopList();
    }, 'danger'));
    card.appendChild(actions);
    box.appendChild(card);
  });
}
