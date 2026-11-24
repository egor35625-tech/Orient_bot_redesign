let activeOrderChatId = null;
let purchasesFilter = 'active';

const ORDER_STATUS_LABELS = { active: 'В процессе', completed: 'Выполнен', cancelled: 'Отменён' };

/* mode: 'buyer' — покупка пользователя, 'seller' — заказ магазина (с выбором этапа). */
function buildOrderCard(order, mode) {
  const div = document.createElement('div');
  div.className = 'order-card';
  const stageLabel = order.current_stage ? order.current_stage.label : (ORDER_STATUS_LABELS[order.status] || 'Новый');
  const title = order.item ? order.item.title : `Товар #${order.item_id}`;
  const price = order.item && order.item.price ? ` • ${esc(order.item.price)} ${esc(order.item.currency || '')}` : '';
  const shopName = order.shop ? order.shop.name : `Магазин #${order.shop_id}`;

  let extra;
  if (mode === 'seller') {
    const stages = order.shop_stages || [];
    const options = stages.map((st) => `<option value="${st.id}" ${order.current_stage_id === st.id ? 'selected' : ''}>${esc(st.label)}</option>`).join('');
    extra = `
      <p class="meta">Покупатель: ${order.buyer_username ? '@' + esc(order.buyer_username) : 'ID ' + order.buyer_telegram_id}</p>
      <label class="inline">Этап заказа</label>
      <select class="stage-select">${options || `<option>${esc(stageLabel)}</option>`}</select>`;
  } else {
    extra = `<p class="meta"><strong>Этап:</strong> <span class="badge">${esc(stageLabel)}</span>
      ${order.status !== 'active' ? `<span class="badge ${order.status === 'completed' ? 'green' : ''}">${ORDER_STATUS_LABELS[order.status] || esc(order.status)}</span>` : ''}</p>`;
  }
  div.innerHTML = `
    <div class="card-head"><strong>Заказ #${order.id}</strong><span class="meta">${esc(shopName)}</span></div>
    <p>${esc(title)}${price}</p>
    <p class="meta">${fmtDate(order.created_at)}</p>
    ${extra}
    <button class="secondary small mt" data-act="chat">💬 Чат по заказу #${order.id}</button>`;
  div.querySelector('[data-act="chat"]').onclick = () => openOrderChat(order.id, title);
  const sel = div.querySelector('.stage-select');
  if (sel) sel.onchange = () => setOrderStage(order.id, sel.value);
  return div;
}

/* ---------- Покупки ---------- */
async function loadPurchases() {
  const list = document.getElementById('ordersList');
  list.innerHTML = '<div class="skeleton" style="height:100px;border-radius:16px;"></div>';
  document.querySelectorAll('[data-purchases]').forEach((c) => c.classList.toggle('active', c.dataset.purchases === purchasesFilter));
  const orders = await apiGet('/api/shops/orders/buyer');
  if (isError(orders)) { list.innerHTML = `<p class="hint">${esc(orders.detail)}</p>`; return; }
  const shown = orders.filter((o) => (purchasesFilter === 'active' ? o.status === 'active' : o.status !== 'active'));
  list.innerHTML = '';
  if (!shown.length) {
    list.innerHTML = `<p class="hint">${purchasesFilter === 'active' ? 'Ожидаемых покупок нет' : 'Совершённых покупок пока нет'}</p>`;
    return;
  }
  shown.forEach((o) => list.appendChild(buildOrderCard(o, 'buyer')));
}

document.querySelectorAll('[data-purchases]').forEach((chip) => {
  chip.addEventListener('click', () => { purchasesFilter = chip.dataset.purchases; loadPurchases(); });
});

/* ---------- Заказы магазина (в «Мои объявления → Объявления магазина») ---------- */
async function loadShopOrders() {
  const list = document.getElementById('shopOrdersList');
  list.innerHTML = '<div class="skeleton" style="height:80px;border-radius:16px;"></div>';
  const orders = await apiGet('/api/shops/orders/my');
  if (isError(orders)) { list.innerHTML = `<p class="hint">${esc(orders.detail)}</p>`; return; }
  list.innerHTML = '';
  if (!orders.length) { list.innerHTML = '<p class="hint">Заказов пока нет</p>'; return; }
  orders.forEach((o) => list.appendChild(buildOrderCard(o, 'seller')));
}

async function setOrderStage(orderId, stageId) {
  if (!stageId) return;
  const res = await apiPost(`/api/shops/orders/${orderId}/stage`, { stage_id: Number(stageId) });
  if (isError(res)) notify(res.detail);
  loadShopOrders();
}

/* ---------- Чат ---------- */
async function openOrderChat(orderId, title = '') {
  activeOrderChatId = orderId;
  document.getElementById('orderChatTitle').textContent = `Заказ #${orderId}${title ? ' — ' + title : ''}`;
  document.getElementById('orderChatModal').classList.remove('hidden');
  await refreshOrderChatMessages();
}

async function refreshOrderChatMessages() {
  if (!activeOrderChatId) return;
  const box = document.getElementById('orderChatMessages');
  const msgs = await apiGet(`/api/shops/orders/${activeOrderChatId}/messages`);
  box.innerHTML = '';
  if (isError(msgs)) { box.innerHTML = `<p class="hint">${esc(msgs.detail)}</p>`; return; }
  if (!msgs.length) { box.innerHTML = '<p class="hint">Сообщений пока нет. Напишите первым!</p>'; return; }
  msgs.forEach((m) => {
    const seller = m.sender_role === 'seller';
    const bubble = document.createElement('div');
    bubble.className = 'bubble ' + (seller ? 'seller' : 'buyer');
    bubble.innerHTML = `<div class="role">${seller ? 'Магазин / менеджер' : 'Покупатель'}</div><div>${esc(m.text)}</div>`;
    box.appendChild(bubble);
  });
  box.scrollTop = box.scrollHeight;
}

async function sendOrderChat() {
  if (!activeOrderChatId) return;
  const input = document.getElementById('orderChatInput');
  const text = input.value.trim();
  if (!text) return;
  const res = await apiPost(`/api/shops/orders/${activeOrderChatId}/messages`, { text });
  if (isError(res)) { notify(res.detail); return; }
  input.value = '';
  refreshOrderChatMessages();
}

document.getElementById('sendOrderChatBtn')?.addEventListener('click', sendOrderChat);
document.getElementById('orderChatInput')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendOrderChat(); });
document.getElementById('closeOrderChatBtn')?.addEventListener('click', () => {
  document.getElementById('orderChatModal').classList.add('hidden');
  activeOrderChatId = null;
});
