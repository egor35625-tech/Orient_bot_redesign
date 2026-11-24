const PAGE_SIZE = 30;
let categoriesCache = [];
let marketOffset = 0;
let marketReqId = 0;

/* ---------- Категории (плитки на главной + форма объявления) ---------- */
function renderCategoryTiles() {
  const box = document.getElementById('categoryTiles');
  if (!box) return;
  const cur = document.getElementById('categoryFilter')?.value || '';
  const all = [{ id: '', name: 'Все', icon: '' }, ...categoriesCache];
  box.innerHTML = all.map((c) => `
    <button class="cat ${String(c.id) === cur ? 'active' : ''}" data-cat="${esc(c.id)}">
      <span class="cat-ic">${c.icon ? esc(c.icon) : '<svg class="ic"><use href="#i-hanger"/></svg>'}</span>
      <span class="cat-name">${esc(c.name)}</span>
    </button>`).join('');
  box.querySelectorAll('.cat').forEach((btn) => {
    btn.onclick = () => {
      document.getElementById('categoryFilter').value = btn.dataset.cat;
      renderCategoryTiles();
      loadMarket(true);
    };
  });
}

async function loadCategories() {
  const res = await apiGet('/api/categories');
  categoriesCache = Array.isArray(res) ? res : [];
  const opts = categoriesCache.map((c) => `<option value="${c.id}">${esc(c.icon || '')} ${esc(c.name)}</option>`).join('');
  const filter = document.getElementById('categoryFilter');
  if (filter) {
    const keep = filter.value;
    filter.innerHTML = '<option value="">Все категории</option>' + opts;
    filter.value = keep;
  }
  const form = document.getElementById('itemCategory');
  if (form) form.innerHTML = '<option value="">Без категории</option>' + opts;
  renderCategoryTiles();
}

/* ---------- Карточка объявления ---------- */
function deliveryBadges(item) {
  const m = item.delivery_methods || '';
  const parts = [];
  if (m.includes('pickup')) parts.push('Самовывоз');
  if (m.includes('cdek')) parts.push('СДЭК');
  if (m.includes('post')) parts.push('Почта');
  return parts.map((p) => `<span class="badge">${p}</span>`).join('');
}

function priceText(item) {
  return item.price ? `${esc(item.price)} ${esc(item.currency || '')}` : 'Договорная';
}

const NO_PHOTO_HTML = '<div class="no-photo"><svg class="ic" style="fill:currentColor;stroke:none"><use href="#i-star"/></svg></div>';

/* Кнопки действий (покупка / написать / позвонить) — используются в листе товара. */
function buildItemActions(item, container) {
  container.innerHTML = '';
  if (item.is_mine) {
    container.innerHTML = '<span class="hint left">Это ваше объявление</span>';
    return;
  }
  if (item.shop_id) {
    const buy = document.createElement('button');
    buy.className = 'primary';
    buy.textContent = 'Купить';
    buy.onclick = () => buyItem(item.shop_id, item.id);
    container.appendChild(buy);
  }
  if (item.seller_username) {
    const msg = document.createElement('button');
    msg.className = item.shop_id ? 'secondary' : 'primary';
    msg.textContent = 'Написать';
    msg.onclick = () => { countView(item.id); openTelegramUser(item.seller_username); };
    container.appendChild(msg);
  }
  if (item.phone && item.contact_mode === 'calls') {
    const call = document.createElement('a');
    call.className = 'btn secondary';
    call.href = 'tel:' + item.phone.replace(/[^\d+]/g, '');
    call.textContent = 'Позвонить';
    call.onclick = () => countView(item.id);
    container.appendChild(call);
  }
  if (!container.children.length) container.innerHTML = '<span class="hint left">Контакты не указаны</span>';
}

/* opts.mine = true — режим «Мои объявления» (изменить/удалить), иначе плитка, открывающая карточку товара. */
function buildItemCard(item, opts = {}) {
  const div = document.createElement('div');
  div.className = 'tile';
  const photo = item.photos && item.photos.length
    ? `<img src="${esc(mediaUrl(item.photos[0].file_path))}" alt="" loading="lazy">`
    : NO_PHOTO_HTML;
  const where = item.shop_id ? (item.shop?.name || 'Магазин') : (item.city || 'Беларусь');
  div.innerHTML = `
    <div class="tile-img">${photo}
      ${opts.mine ? '' : `<button class="heart ${isFav(item.id) ? 'on' : ''}" data-fav-id="${esc(item.id)}" aria-label="В избранное"><svg class="ic"><use href="#i-heart"/></svg></button>`}
    </div>
    <div class="tile-body">
      <div class="tile-title">${esc(item.title)}</div>
      <div class="tile-price">${priceText(item)}</div>
      <div class="tile-meta">${item.shop_id ? '🏬 ' : ''}${esc(where)}</div>
    </div>`;

  if (opts.mine) {
    const actions = document.createElement('div');
    actions.className = 'tile-actions';
    const edit = document.createElement('button');
    edit.className = 'secondary small';
    edit.textContent = 'Изменить';
    edit.onclick = (e) => { e.stopPropagation(); openItemModal({ item }); };
    const del = document.createElement('button');
    del.className = 'secondary small danger';
    del.textContent = 'Удалить';
    del.onclick = (e) => { e.stopPropagation(); deleteItem(item); };
    actions.append(edit, del);
    div.appendChild(actions);
    div.onclick = () => openItemDetail(item);
    return div;
  }

  div.querySelector('.heart').onclick = (e) => { e.stopPropagation(); toggleFav(item); };
  div.onclick = () => openItemDetail(item);
  return div;
}

/* ---------- Лист товара (как «страница товара» в макете) ---------- */
let detailItem = null;

function openItemDetail(item) {
  detailItem = item;
  const modal = document.getElementById('itemDetailModal');
  const body = document.getElementById('itemDetailBody');
  const photos = item.photos || [];
  const gallery = photos.length
    ? `<div class="gallery-strip">${photos.map((p) => `<img src="${esc(mediaUrl(p.file_path))}" alt="">`).join('')}</div>
       ${photos.length > 1 ? `<div class="dots">${photos.map((_, i) => `<i class="${i ? '' : 'on'}"></i>`).join('')}</div>` : ''}`
    : NO_PHOTO_HTML;
  const shopBadge = item.shop_id
    ? `<span class="badge green">🏬 ${esc(item.shop?.name || 'Магазин')}</span>`
    : '<span class="badge">Частное</span>';
  const phoneLine = item.phone
    ? `<p class="meta">📱 ${esc(item.phone)} · ${item.contact_mode === 'calls' ? 'сообщения и звонки' : 'только сообщения'}</p>` : '';
  const pickup = item.pickup_address ? `<p class="meta">📍 Самовывоз: ${esc(item.pickup_address)}</p>` : '';
  const delivery = deliveryBadges(item);

  body.innerHTML = `
    <div class="gallery">${gallery}</div>
    <div class="detail-panel">
      <div class="detail-title">${esc(item.title)}</div>
      <div class="detail-price">${priceText(item)}</div>
      <div class="badges">${shopBadge}${delivery}</div>
      ${item.description ? `<p class="desc">${esc(item.description)}</p>` : ''}
      <p class="meta">🇧🇾 ${item.city ? esc(item.city) : 'Беларусь'}</p>
      ${pickup}${phoneLine}
      <div class="actions-row"></div>
    </div>`;
  buildItemActions(item, body.querySelector('.actions-row'));

  const strip = body.querySelector('.gallery-strip');
  if (strip) {
    strip.addEventListener('scroll', () => {
      const i = Math.round(strip.scrollLeft / strip.clientWidth);
      body.querySelectorAll('.dots i').forEach((d, k) => d.classList.toggle('on', k === i));
    }, { passive: true });
  }
  const fav = document.getElementById('itemDetailFav');
  fav.dataset.favId = item.id;
  fav.classList.toggle('on', isFav(item.id));
  fav.classList.toggle('hidden', !!item.is_mine);
  modal.classList.remove('hidden');
  modal.scrollTop = 0;
}

document.getElementById('itemDetailBack')?.addEventListener('click', () => document.getElementById('itemDetailModal').classList.add('hidden'));
document.getElementById('itemDetailFav')?.addEventListener('click', () => { if (detailItem) toggleFav(detailItem); });
document.getElementById('itemDetailShare')?.addEventListener('click', () => {
  if (!detailItem) return;
  const url = location.origin;
  const text = `${detailItem.title} — ${detailItem.price ? detailItem.price + ' ' + (detailItem.currency || '') : 'Договорная'}`;
  const link = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text)}`;
  if (tg && tg.openTelegramLink) tg.openTelegramLink(link);
  else if (navigator.share) navigator.share({ title: detailItem.title, text, url }).catch(() => {});
  else window.open(link, '_blank');
});

function renderItemsInto(list, items, append = false) {
  if (!list) return;
  if (!append) list.innerHTML = '';
  if (!Array.isArray(items) || (!items.length && !append)) {
    if (!append) list.innerHTML = '<p class="hint">Ничего не найдено</p>';
    return;
  }
  items.forEach((item) => list.appendChild(buildItemCard(item)));
}

/* ---------- Загрузка маркета ---------- */
async function loadMarket(reset = true) {
  const reqId = ++marketReqId;
  const list = document.getElementById('marketList');
  const more = document.getElementById('marketMoreBtn');
  if (reset) {
    marketOffset = 0;
    list.innerHTML = '<div class="skeleton" style="height:200px;"></div>';
    more.classList.add('hidden');
  }
  const params = new URLSearchParams();
  const q = document.getElementById('searchInput').value.trim();
  const cat = document.getElementById('categoryFilter').value;
  if (q) params.append('q', q);
  if (cat) params.append('category_id', cat);
  params.append('sort', document.getElementById('sortSelect').value || 'new');
  params.append('limit', PAGE_SIZE);
  params.append('offset', marketOffset);

  const items = await apiGet('/api/market?' + params.toString());
  if (reqId !== marketReqId) return; // пришёл устаревший ответ
  if (isError(items)) {
    list.innerHTML = `<p class="hint">${esc(items.detail)}</p>`;
    return;
  }
  renderItemsInto(list, items, !reset);
  marketOffset += items.length;
  more.classList.toggle('hidden', items.length < PAGE_SIZE);
}

function countView(itemId) {
  fetch(`/api/market/${itemId}/view`, { method: 'POST' }).catch(() => {});
}

async function buyItem(shopId, itemId) {
  if (!(await requireRegistered())) return;
  if (!(await askConfirm('Оформить заказ на этот товар? Магазин получит уведомление.'))) return;
  countView(itemId);
  const resp = await apiPost(`/api/shops/${shopId}/order/${itemId}`, {});
  if (!isError(resp) && resp.ok) {
    notify(`Заказ #${resp.order_id} оформлен! Следить за ним можно во вкладке «Покупки».`);
  } else {
    notify(resp?.detail || 'Не удалось оформить заказ');
  }
}

/* ---------- Форма объявления (создание / редактирование) ---------- */
let itemState = { itemId: null, shopId: null, existing: [], removed: new Set(), sending: false };

function _setDeliveryChecks(prefix, methods) {
  ['pickup', 'cdek', 'post'].forEach((m) => {
    const el = document.getElementById(`${prefix}${m}`);
    if (el) el.checked = (methods || '').includes(m);
  });
}

function _readDelivery(prefix) {
  return ['pickup', 'cdek', 'post'].filter((m) => document.getElementById(`${prefix}${m}`)?.checked).join(',');
}

function updateItemContactMode() {
  const has = document.getElementById('itemPhone').value.trim().length > 0;
  document.getElementById('itemContactModeBox').classList.toggle('hidden', !has);
}

function renderExistingPhotos() {
  const box = document.getElementById('itemExistingPhotos');
  box.innerHTML = '';
  itemState.existing.filter((p) => !itemState.removed.has(p.id)).forEach((p) => {
    const wrap = document.createElement('div');
    wrap.className = 'thumb';
    wrap.innerHTML = `<img src="${esc(mediaUrl(p.file_path))}" alt=""><button type="button" title="Убрать">✕</button>`;
    wrap.querySelector('button').onclick = () => { itemState.removed.add(p.id); renderExistingPhotos(); };
    box.appendChild(wrap);
  });
}

/* openItemModal({ item }) — редактирование; openItemModal({ shop }) — новое объявление магазина; без аргументов — частное. */
async function openItemModal({ item = null, shop = null } = {}) {
  if (!(await requireRegistered())) return;
  const editing = !!item;
  const isShop = editing ? !!item.shop_id : !!shop;
  itemState = { itemId: item ? item.id : null, shopId: item ? item.shop_id : (shop ? shop.id : null), existing: item ? [...item.photos] : [], removed: new Set(), sending: false };

  document.getElementById('itemModalTitle').textContent = editing ? 'Редактирование объявления' : (isShop ? 'Новое объявление магазина' : 'Новое объявление');
  document.getElementById('submitItem').textContent = editing ? 'Сохранить' : 'Опубликовать';
  document.getElementById('itemShopNote').classList.toggle('hidden', !isShop);
  document.getElementById('itemPrivateFields').classList.toggle('hidden', isShop);

  document.getElementById('itemCategory').value = item?.category_id ? String(item.category_id) : '';
  document.getElementById('itemTitle').value = item?.title || '';
  document.getElementById('itemDesc').value = item?.description || '';
  document.getElementById('itemPrice').value = item?.price || '';
  document.getElementById('itemCurrency').value = item?.currency || 'BYN';
  document.getElementById('itemCity').value = editing ? (item.city || '') : (me.city || '');
  document.getElementById('itemPhone').value = editing ? (item.phone || '') : '';
  document.getElementById('itemContactMode').value = item?.contact_mode || 'messages';
  _setDeliveryChecks('del_', item?.delivery_methods);
  document.getElementById('pickupAddress').value = item?.pickup_address || '';
  document.getElementById('itemPhotos').value = '';
  updateItemContactMode();
  renderExistingPhotos();
  document.getElementById('itemModal').classList.remove('hidden');
}

function closeItemModal() {
  document.getElementById('itemModal').classList.add('hidden');
}

async function submitItemForm() {
  if (itemState.sending) return;
  const title = document.getElementById('itemTitle').value.trim();
  if (title.length < 2) { notify('Введите название (минимум 2 символа)'); return; }

  const files = Array.from(document.getElementById('itemPhotos').files || []);
  const keepCount = itemState.existing.filter((p) => !itemState.removed.has(p.id)).length;
  if (keepCount + files.length > 5) { notify('Можно прикрепить не более 5 фото'); return; }

  const isShop = !!itemState.shopId;
  const fd = new FormData();
  fd.append('title', title);
  fd.append('description', document.getElementById('itemDesc').value.trim());
  fd.append('price', document.getElementById('itemPrice').value.trim());
  fd.append('currency', document.getElementById('itemCurrency').value);
  const cat = document.getElementById('itemCategory').value;
  if (cat) fd.append('category_id', cat);
  if (!isShop) {
    fd.append('city', document.getElementById('itemCity').value.trim());
    const phone = document.getElementById('itemPhone').value.trim();
    fd.append('phone', phone);
    fd.append('contact_mode', phone ? document.getElementById('itemContactMode').value : 'messages');
    fd.append('delivery_methods', _readDelivery('del_'));
    fd.append('pickup_address', document.getElementById('pickupAddress').value.trim());
  }
  if (!itemState.itemId && isShop) fd.append('shop_id', itemState.shopId);
  if (itemState.itemId) fd.append('remove_photos', Array.from(itemState.removed).join(','));
  files.forEach((f) => fd.append('photos', f));

  const btn = document.getElementById('submitItem');
  itemState.sending = true;
  btn.disabled = true;
  const res = itemState.itemId
    ? await apiForm(`/api/market/${itemState.itemId}`, 'PUT', fd)
    : await apiForm('/api/market', 'POST', fd);
  itemState.sending = false;
  btn.disabled = false;

  if (isError(res)) { notify(res.detail); return; }
  closeItemModal();
  notify(itemState.itemId ? 'Объявление сохранено' : 'Объявление опубликовано!');
  if (currentSection() === 'market') loadMarket(true);
  if (currentSection() === 'myads') loadMyAds();
}

async function deleteItem(item) {
  if (!(await askConfirm(`Удалить объявление «${item.title}»?`))) return;
  const res = await apiDelete(`/api/market/${item.id}`);
  if (isError(res)) { notify(res.detail); return; }
  loadMyAds();
}

/* ---------- События ---------- */
document.getElementById('addItemBtn')?.addEventListener('click', () => openItemModal());
document.getElementById('cancelItem')?.addEventListener('click', closeItemModal);
document.getElementById('submitItem')?.addEventListener('click', submitItemForm);
document.getElementById('itemPhone')?.addEventListener('input', updateItemContactMode);
document.getElementById('marketMoreBtn')?.addEventListener('click', () => loadMarket(false));
document.getElementById('searchInput')?.addEventListener('input', () => {
  clearTimeout(window._searchTimer);
  window._searchTimer = setTimeout(() => loadMarket(true), 400);
});
document.getElementById('categoryFilter')?.addEventListener('change', () => loadMarket(true));
document.getElementById('sortSelect')?.addEventListener('change', () => loadMarket(true));
document.getElementById('heroBtn')?.addEventListener('click', () => document.getElementById('catalog')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
document.getElementById('catAllBtn')?.addEventListener('click', () => {
  document.getElementById('categoryFilter').value = '';
  renderCategoryTiles();
  loadMarket(true);
});
