const tg = window.Telegram?.WebApp;
if (tg) { tg.ready(); tg.expand(); }

const $ = (id) => document.getElementById(id);
const state = { user: null, balance: 0, lastBonusAt: null, nextBonusAt: null, inventory: [], category: 'all', skins: [] };
const pages = ['homePage', 'shopPage', 'inventoryPage'];
let toastTimer;

function showToast(message) {
  const el = $('toast'); el.textContent = message; el.classList.add('show');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('show'), 2600);
  if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
}
function money(value) { return `${Number(value).toLocaleString('ru-RU')} 🪙`; }
function authHeaders() {
  return { 'Content-Type': 'application/json', 'X-Telegram-Init-Data': tg?.initData || '' };
}
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { ...authHeaders(), ...(options.headers || {}) } });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || 'Ошибка сервера');
  return data;
}
function updateHeader() {
  $('balance').innerHTML = `${Number(state.balance).toLocaleString('ru-RU')} <span>🪙</span>`;
  $('userLabel').textContent = state.user?.first_name || 'PLAYER';
}
function switchPage(pageId) {
  pages.forEach(id => $(id).classList.toggle('hidden', id !== pageId));
  document.querySelectorAll('.nav-button').forEach(btn => btn.classList.toggle('active', btn.dataset.page === pageId));
  if (pageId === 'shopPage') renderShop();
  if (pageId === 'inventoryPage') renderInventory();
}
function cardMarkup(skin, owned = false) {
  const buy = owned ? '<button class="buy-button" disabled>В ИНВЕНТАРЕ</button>' : `<button class="buy-button" data-buy="${skin.id}">КУПИТЬ</button>`;
  return `<article class="skin-card">
    <div class="skin-art"><span class="skin-rarity">${skin.rarity || 'CLASSIFIED'}</span><span class="weapon-symbol">${skin.icon || '🔫'}</span></div>
    <h3>${skin.name}</h3><p class="skin-type">${skin.type}</p>
    <div class="skin-bottom"><span class="skin-price">${money(skin.price)}</span></div>${buy}
  </article>`;
}
function renderShop() {
  const filtered = state.skins.filter(s => state.category === 'all' || s.category === state.category);
  $('shopCount').textContent = `${filtered.length} ITEMS`;
  $('shopItems').innerHTML = filtered.length ? filtered.map(s => cardMarkup(s)).join('') : '<div class="empty-state">В этой категории пока нет предметов.</div>';
}
function renderInventory() {
  $('inventoryCount').textContent = `${state.inventory.length} ITEMS`;
  $('inventoryItems').innerHTML = state.inventory.length ? state.inventory.map(s => cardMarkup(s, true)).join('') : '<div class="empty-state">Инвентарь пока пуст.<br>Загляни в магазин и выбери первый предмет.</div>';
}
function updateBonusTimer() {
  const button = $('bonusButton');
  if (!state.nextBonusAt) { button.disabled = false; $('bonusStatus').textContent = 'Ежедневная награда доступна'; $('countdown').textContent = 'ГОТОВО'; return; }
  const ms = new Date(state.nextBonusAt).getTime() - Date.now();
  if (ms <= 0) { button.disabled = false; button.textContent = 'ПОЛУЧИТЬ 100 МОНЕТ'; $('bonusStatus').textContent = 'Новая награда доступна'; $('countdown').textContent = 'ГОТОВО'; return; }
  button.disabled = true; button.textContent = 'БОНУС УЖЕ ПОЛУЧЕН';
  const h = Math.floor(ms / 3600000), m = Math.floor(ms % 3600000 / 60000), s = Math.floor(ms % 60000 / 1000);
  $('bonusStatus').textContent = 'Следующая награда через'; $('countdown').textContent = [h,m,s].map(n => String(n).padStart(2,'0')).join(':');
}
async function refresh() {
  const data = await api('/api/me');
  state.user = data.user; state.balance = data.balance; state.nextBonusAt = data.next_bonus_at;
  state.inventory = data.inventory; updateHeader(); renderInventory(); updateBonusTimer();
}
async function loadApp() {
  if (!tg || !tg.initData) {
    document.body.innerHTML = `<div style="max-width:420px;margin:15vh auto;padding:24px;color:#fff;font-family:Arial;line-height:1.6"><h2 style="color:#f2a900">CS2 REWARDS</h2><p>Открой приложение через кнопку меню Telegram-бота. В обычном браузере авторизация Telegram недоступна.</p></div>`;
    return;
  }
  try {
    const [shop] = await Promise.all([api('/api/shop')]);
    state.skins = shop.items;
    await refresh(); renderShop();
  } catch (error) { showToast(error.message); }
}
$('bonusButton').addEventListener('click', async () => {
  try { const result = await api('/api/bonus', { method: 'POST' }); state.balance = result.balance; state.nextBonusAt = result.next_bonus_at; updateHeader(); updateBonusTimer(); showToast(`Начислено ${result.awarded} монет!`); }
  catch (error) { showToast(error.message); await refresh().catch(() => {}); }
});
$('shopItems').addEventListener('click', async (event) => {
  const button = event.target.closest('[data-buy]'); if (!button) return;
  button.disabled = true;
  try { const result = await api('/api/buy', { method: 'POST', body: JSON.stringify({ item_id: Number(button.dataset.buy) }) }); state.balance = result.balance; await refresh(); renderShop(); showToast(`Покупка оформлена: ${result.item_name}`); }
  catch (error) { button.disabled = false; showToast(error.message); }
});
$('filters').addEventListener('click', (event) => {
  const button = event.target.closest('[data-category]'); if (!button) return;
  document.querySelectorAll('.filter').forEach(b => b.classList.toggle('active', b === button));
  state.category = button.dataset.category; renderShop();
});
document.querySelectorAll('[data-page]').forEach(button => button.addEventListener('click', () => switchPage(button.dataset.page)));
setInterval(updateBonusTimer, 1000);
loadApp();
