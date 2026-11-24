let currentShopDetailId = null;
let myShop = null;        // магазин, которым владеет пользователь
let managedShop = null;   // магазин, где пользователь менеджер
let myApplication = null; // последняя заявка (создание/изменение)

function formatStars(rating) { return `⭐ ${Number(rating || 0).toFixed(1)}`; }

function shopAvatarHtml(shop, size = 76) {
  return shop.logo
    ? `<img class="shop-avatar" src="${esc(mediaUrl(shop.logo))}" alt="" style="width:${size}px;height:${size}px;">`
    : `<div class="shop-avatar ph" style="width:${size}px;height:${size}px;">🏬</div>`;
}

function socialsHtml(shop) {
  const links = [];
  if (shop.instagram_url) links.push(`<a href="${esc(externalLink(shop.instagram_url))}" target="_blank" rel="noopener noreferrer">Instagram</a>`);
  if (shop.tiktok_url) links.push(`<a href="${esc(externalLink(shop.tiktok_url))}" target="_blank" rel="noopener noreferrer">TikTok</a>`);
  return links.length ? `<div class="links">${links.join('')}</div>` : '';
}

/* ---------- Список магазинов ---------- */
async function loadShops() {
  const list = document.getElementById('shopsList');
  list.innerHTML = '<div class="skeleton" style="height:140px;"></div>';
  const params = new URLSearchParams();
  const q = document.getElementById('shopSearchInput').value.trim();
  const rating = document.getElementById('shopRatingFilter').value;
  if (q) params.append('q', q);
  if (rating) params.append('min_rating', rating);
  params.append('sort', document.getElementById('shopSortSelect').value || 'boost');
  const shops = await apiGet('/api/shops?' + params.toString());
  if (isError(shops)) { list.innerHTML = `<p class="hint">${esc(shops.detail)}</p>`; return; }
  renderShops(shops);
}

function renderShops(shops) {
  const list = document.getElementById('shopsList');
  list.innerHTML = '';
  if (!shops.length) { list.innerHTML = '<p class="hint">Магазины не найдены</p>'; return; }
  shops.forEach((shop) => {
    const div = document.createElement('div');
    div.className = 'card';
    const boost = shop.boost_until ? '<span class="badge gold">🚀 ТОП</span>' : '';
    const manager = shop.manager_username ? `<p class="meta">👤 Менеджер: @${esc(shop.manager_username)}</p>` : '';
    div.innerHTML = `
      <div class="shop-head">
        ${shopAvatarHtml(shop)}
        <div class="grow"><h3>${esc(shop.name)}</h3> ${boost}</div>
        <span class="rating">${formatStars(shop.rating_avg)} (${shop.reviews_count || 0})</span>
      </div>
      ${shop.description ? `<p class="desc">${esc(shop.description)}</p>` : ''}
      <p class="meta">📍 🇧🇾 ${esc(shop.city || 'Беларусь')} • 📦 Заказов: ${shop.orders_count || 0}</p>
      ${manager}${socialsHtml(shop)}
      <div class="row mt">
        <button class="primary small grow" data-act="detail">Открыть магазин</button>
        <button class="secondary small" data-act="items">Товары</button>
      </div>`;
    div.querySelector('[data-act="detail"]').onclick = () => openShopDetailModal(shop.id);
    div.querySelector('[data-act="items"]').onclick = () => openShopItems(shop.id);
    list.appendChild(div);
  });
}

/* ---------- Товары магазина внутри раздела «Магазины» ---------- */
function closeShopItems() {
  document.getElementById('shopItemsView').classList.add('hidden');
  document.getElementById('shopsListView').classList.remove('hidden');
}

async function openShopItems(shopId) {
  document.getElementById('shopDetailModal').classList.add('hidden');
  showSection('shops');
  document.getElementById('shopsListView').classList.add('hidden');
  document.getElementById('shopItemsView').classList.remove('hidden');
  const header = document.getElementById('shopItemsHeader');
  const list = document.getElementById('shopItemsList');
  header.innerHTML = '<div class="skeleton" style="height:80px;"></div>';
  list.innerHTML = '';

  const data = await apiGet(`/api/shops/${shopId}`);
  if (isError(data) || !data.shop) {
    header.innerHTML = `<p class="hint">${esc(data?.detail || 'Не удалось загрузить магазин')}</p>`;
    return;
  }
  const s = data.shop;
  header.innerHTML = `
    <div class="shop-head">
      ${shopAvatarHtml(s, 64)}
      <div class="grow"><h3>${esc(s.name)}</h3>
        <p class="meta">${formatStars(s.rating_avg)} (${s.reviews_count || 0}) • ${esc(s.city || 'Беларусь')}</p></div>
    </div>
    <button class="secondary small mt" data-act="detail">О магазине и отзывы</button>`;
  header.querySelector('[data-act="detail"]').onclick = () => openShopDetailModal(s.id);
  if (!data.items.length) list.innerHTML = '<p class="hint">В этом магазине пока нет товаров</p>';
  else renderItemsInto(list, data.items);
}

document.getElementById('shopItemsBackBtn')?.addEventListener('click', closeShopItems);

/* ---------- Окно магазина и отзывы ---------- */
async function openShopDetailModal(shopId) {
  currentShopDetailId = shopId;
  const modal = document.getElementById('shopDetailModal');
  const body = document.getElementById('shopDetailBody');
  const reviewsBox = document.getElementById('shopReviewsList');
  modal.classList.remove('hidden');
  body.innerHTML = '<p class="hint">Загрузка...</p>';
  reviewsBox.innerHTML = '';

  const data = await apiGet(`/api/shops/${shopId}`);
  if (isError(data) || !data.shop) { body.innerHTML = `<p class="hint">${esc(data?.detail || 'Не удалось загрузить магазин')}</p>`; return; }
  const s = data.shop;
  const manager = s.manager_username ? '@' + esc(s.manager_username) : 'не указан';
  const delivery = deliveryBadges(s);
  const phone = s.phone ? `<p class="meta">📱 ${esc(s.phone)} · ${s.contact_mode === 'calls' ? 'сообщения и звонки' : 'только сообщения'}</p>` : '';
  body.innerHTML = `
    ${s.logo ? `<img class="shop-cover" src="${esc(mediaUrl(s.logo))}" alt="">` : '<div class="shop-cover ph">🏬</div>'}
    <h3>${esc(s.name)}</h3>
    <p class="meta">${formatStars(s.rating_avg)} (${s.reviews_count || 0} отзывов) • 📦 Заказов: ${s.orders_count || 0}</p>
    <p class="desc">${esc(s.description || 'Описание не указано')}</p>
    <p class="meta">📍 🇧🇾 ${esc(s.city || 'Беларусь')}</p>
    <p class="meta">👤 Менеджер: ${manager}</p>
    ${phone}
    ${delivery ? `<div class="badges">${delivery}</div>` : ''}
    ${s.pickup_address ? `<p class="meta">📍 Самовывоз: ${esc(s.pickup_address)}</p>` : ''}
    ${socialsHtml(s)}
    <button class="primary mt" data-act="items">Перейти к товарам магазина</button>`;
  body.querySelector('[data-act="items"]').onclick = () => openShopItems(s.id);
  renderShopReviews(data.reviews || []);
}

function renderShopReviews(reviews) {
  const box = document.getElementById('shopReviewsList');
  box.innerHTML = '';
  if (!reviews.length) { box.innerHTML = '<p class="hint">Отзывов пока нет. Будьте первым!</p>'; return; }
  reviews.forEach((r) => {
    const el = document.createElement('div');
    el.className = 'review';
    el.innerHTML = `
      <div class="review-head"><span>${esc(r.author_name || 'Покупатель')}</span><span>${'⭐'.repeat(r.rating || 5)}</span></div>
      <p>${esc(r.text)}</p>`;
    box.appendChild(el);
  });
}

document.getElementById('submitShopReviewBtn')?.addEventListener('click', async () => {
  if (!currentShopDetailId) return;
  if (!(await requireRegistered())) return;
  const text = document.getElementById('shopReviewText').value.trim();
  if (!text) { notify('Напишите текст отзыва'); return; }
  const rating = Number(document.getElementById('shopReviewRating').value || 5);
  const res = await apiPost(`/api/shops/${currentShopDetailId}/reviews`, { rating, text });
  if (isError(res)) { notify(res.detail); return; }
  document.getElementById('shopReviewText').value = '';
  await openShopDetailModal(currentShopDetailId);
  notify('Отзыв добавлен!');
});

document.getElementById('closeShopDetailBtn')?.addEventListener('click', () => {
  document.getElementById('shopDetailModal').classList.add('hidden');
  currentShopDetailId = null;
});

/* ---------- Мой магазин: статус, заявки ---------- */
function blockInfoHtml(shop) {
  if (shop.status !== 'blocked') return '';
  const term = shop.blocked_until ? `до ${fmtDate(shop.blocked_until)}` : 'навсегда';
  return `<p class="alert">⛔ Магазин заблокирован ${term}.${shop.block_reason ? ' Причина: ' + esc(shop.block_reason) : ''}</p>`;
}

function applicationInfoHtml(app) {
  if (!app) return '';
  const what = app.kind === 'edit' ? 'изменение магазина' : 'создание магазина';
  if (app.status === 'pending') return `<p class="note">⏳ Заявка на ${what} «${esc(app.shop_name)}» на модерации. Пока она не одобрена, действуют прежние данные.</p>`;
  if (app.status === 'rejected') return `<p class="alert">❌ Заявка на ${what} отклонена.${app.reject_reason ? ' Причина: ' + esc(app.reject_reason) : ''}</p>`;
  return '';
}

function myShopCardHtml(shop, app) {
  const mgr = shop.manager_username ? '@' + esc(shop.manager_username) : '—';
  return `
    <div class="shop-head">
      ${shopAvatarHtml(shop, 64)}
      <div class="grow"><h4>🏬 ${esc(shop.name)}</h4>
        <p class="meta">${formatStars(shop.rating_avg)} (${shop.reviews_count || 0}) • 📦 Заказов: ${shop.orders_count || 0}</p></div>
    </div>
    <p class="meta">📍 ${esc(shop.city || '—')} • 👤 ${mgr}${shop.phone ? ' • 📱 ' + esc(shop.phone) : ''}</p>
    ${blockInfoHtml(shop)}${applicationInfoHtml(app)}`;
}

async function checkShopStatus() {
  const data = await apiGet('/api/shops/my/status');
  if (!isError(data)) {
    myShop = data.shop || null;
    managedShop = data.managed_shop || null;
    myApplication = data.application || null;
  }
  renderShopStatusBox();
  if (typeof updateMyAdsShopChip === 'function') updateMyAdsShopChip();
}

function renderShopStatusBox() {
  const box = document.getElementById('shopStatusBox');
  const btn = document.getElementById('openShopFormBtn');
  if (!box || !btn) return;
  const pending = myApplication && myApplication.status === 'pending';
  if (myShop) {
    box.innerHTML = myShopCardHtml(myShop, myApplication);
    btn.textContent = 'Изменить магазин (через модерацию)';
  } else {
    box.innerHTML = myApplication
      ? (applicationInfoHtml(myApplication) || '<p class="hint left">У вас пока нет магазина.</p>')
      : '<p class="hint left">У вас пока нет магазина. Можно создать один магазин — после проверки модератором.</p>';
    if (managedShop) box.innerHTML += `<p class="note">Вы менеджер магазина «${esc(managedShop.name)}».</p>`;
    btn.textContent = 'Создать магазин';
  }
  btn.classList.toggle('hidden', !!pending);
}

/* ---------- Форма магазина (создание / изменение через модерацию) ---------- */
function updateShopContactMode() {
  const has = document.getElementById('shopPhone').value.trim().length > 0;
  document.getElementById('shopContactModeBox').classList.toggle('hidden', !has);
}

function openShopForm() {
  requireRegistered().then((ok) => {
    if (!ok) return;
    const editing = !!myShop;
    const s = myShop || {};
    document.getElementById('shopFormTitle').textContent = editing ? 'Изменение магазина' : 'Создание магазина';
    document.getElementById('shopFormNote').textContent = editing
      ? 'Любые изменения магазина проверяет модератор. До одобрения на сайте остаются прежние данные.'
      : 'Заявка проверяется модератором. Эти данные подставляются во все объявления магазина — повторно вводить их не придётся.';
    document.getElementById('submitShopFormBtn').textContent = 'Отправить на модерацию';
    document.getElementById('shopName').value = s.name || '';
    document.getElementById('shopDesc').value = s.description || '';
    document.getElementById('shopCity').value = s.city || me.city || '';
    document.getElementById('shopPhone').value = s.phone || '';
    document.getElementById('shopContactMode').value = s.contact_mode || 'messages';
    document.getElementById('shopManagerUsername').value = s.manager_username ? '@' + s.manager_username : '';
    document.getElementById('shopManagerId').value = s.manager_telegram_id || '';
    document.getElementById('shopInstagram').value = s.instagram_url || '';
    document.getElementById('shopTikTok').value = s.tiktok_url || '';
    _setDeliveryChecks('shop_del_', s.delivery_methods);
    document.getElementById('shopPickup').value = s.pickup_address || '';
    document.getElementById('shopLogoFile').value = '';
    document.getElementById('shopLogoRemove').checked = false;
    document.getElementById('shopLogoRemove').closest('label').classList.toggle('hidden', !(editing && s.logo));
    const prev = document.getElementById('shopLogoPreview');
    if (s.logo) { prev.src = mediaUrl(s.logo); prev.classList.remove('hidden'); } else { prev.classList.add('hidden'); prev.removeAttribute('src'); }
    updateShopContactMode();
    document.getElementById('shopFormModal').classList.remove('hidden');
  });
}

document.getElementById('openShopFormBtn')?.addEventListener('click', openShopForm);
document.getElementById('cancelShopFormBtn')?.addEventListener('click', () => document.getElementById('shopFormModal').classList.add('hidden'));
document.getElementById('shopPhone')?.addEventListener('input', updateShopContactMode);
document.getElementById('shopLogoFile')?.addEventListener('change', (e) => {
  const f = e.target.files && e.target.files[0];
  const prev = document.getElementById('shopLogoPreview');
  if (f) { prev.src = URL.createObjectURL(f); prev.classList.remove('hidden'); document.getElementById('shopLogoRemove').checked = false; }
});

document.getElementById('submitShopFormBtn')?.addEventListener('click', async () => {
  const name = document.getElementById('shopName').value.trim();
  if (name.length < 2) { notify('Введите название магазина (минимум 2 символа)'); return; }
  const phone = document.getElementById('shopPhone').value.trim();
  const fd = new FormData();
  fd.append('shop_name', name);
  fd.append('description', document.getElementById('shopDesc').value.trim());
  fd.append('city', document.getElementById('shopCity').value.trim());
  fd.append('phone', phone);
  fd.append('contact_mode', phone ? document.getElementById('shopContactMode').value : 'messages');
  fd.append('manager_username', document.getElementById('shopManagerUsername').value.trim());
  fd.append('manager_telegram_id', document.getElementById('shopManagerId').value.trim());
  fd.append('instagram_url', document.getElementById('shopInstagram').value.trim());
  fd.append('tiktok_url', document.getElementById('shopTikTok').value.trim());
  fd.append('pickup_address', document.getElementById('shopPickup').value.trim());
  fd.append('delivery_methods', _readDelivery('shop_del_'));
  fd.append('remove_logo', document.getElementById('shopLogoRemove').checked ? '1' : '0');
  const file = document.getElementById('shopLogoFile').files[0];
  if (file) fd.append('logo', file);

  const btn = document.getElementById('submitShopFormBtn');
  btn.disabled = true;
  const res = await apiForm('/api/shops/applications', 'POST', fd);
  btn.disabled = false;
  if (isError(res)) { notify(res.detail); return; }
  document.getElementById('shopFormModal').classList.add('hidden');
  await checkShopStatus();
  if (currentSection() === 'myads') loadMyAds();
  notify('Заявка отправлена! Ожидайте решения модератора.');
});

document.getElementById('shopSearchInput')?.addEventListener('input', () => {
  clearTimeout(window._shopSearchTimer);
  window._shopSearchTimer = setTimeout(loadShops, 350);
});
document.getElementById('shopRatingFilter')?.addEventListener('change', loadShops);
document.getElementById('shopSortSelect')?.addEventListener('change', loadShops);
