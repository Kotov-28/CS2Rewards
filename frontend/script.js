
// ================================================
// CS2 REWARDS
// Основной JavaScript приложения
// ================================================

const tg = window.Telegram?.WebApp;

if (tg) {
    tg.ready();
    tg.expand();
    tg.setHeaderColor("#101318");
    tg.setBackgroundColor("#101318");
}


// ================================================
// СОСТОЯНИЕ ПРИЛОЖЕНИЯ
// ================================================

let balance = 0;
let currentUser = null;
let cases = [];
let shopItems = [];
let inventory = [];

let selectedCase = null;
let openCount = 1;
let currentFilter = "all";
let toastTimeout = null;


// ================================================
// API
// ================================================

async function api(url, options = {}) {
    const initData = tg?.initData || "";

    if (!initData) {
        throw new Error(
            "Открой приложение через Telegram, чтобы авторизоваться."
        );
    }

    const response = await fetch(url, {
        ...options,
        headers: {
            "Content-Type": "application/json",
            "X-Telegram-Init-Data": initData,
            ...(options.headers || {})
        }
    });

    let data;

    try {
        data = await response.json();
    } catch {
        throw new Error("Сервер вернул неправильный ответ.");
    }

    if (!response.ok) {
        throw new Error(
            data.detail || data.message || "Произошла ошибка."
        );
    }

    return data;
}


// ================================================
// УВЕДОМЛЕНИЯ
// ================================================

function showToast(message) {
    const toast = document.getElementById("toast");

    if (!toast) return;

    toast.textContent = message;
    toast.classList.add("show");

    clearTimeout(toastTimeout);

    toastTimeout = setTimeout(() => {
        toast.classList.remove("show");
    }, 2800);
}


// ================================================
// ФОРМАТИРОВАНИЕ ЧИСЕЛ
// ================================================

function formatNumber(number) {
    return Number(number || 0).toLocaleString("ru-RU");
}


// ================================================
// ОБНОВЛЕНИЕ БАЛАНСА
// ================================================

function updateBalance(value) {
    balance = Number(value || 0);

    const balanceElement = document.getElementById("balance");
    const profileBalance = document.getElementById("profileBalance");

    if (balanceElement) {
        balanceElement.textContent = formatNumber(balance);
    }

    if (profileBalance) {
        profileBalance.textContent = formatNumber(balance);
    }
}


// ================================================
// ЗАГРУЗКА ДАННЫХ
// ================================================

async function refresh() {
    try {
        const data = await api("/api/me");

        currentUser = data.user;
        inventory = data.inventory || [];

        updateBalance(data.balance);

        renderInventory();
        renderProfile();

        updateBonusButton(data.next_bonus_at);

    } catch (error) {
        showToast(error.message);
    }
}


// ================================================
// ПЕРЕКЛЮЧЕНИЕ СТРАНИЦ
// ================================================

function showPage(pageId) {
    document.querySelectorAll(".page").forEach(page => {
        page.classList.remove("active");
    });

    const page = document.getElementById(pageId);

    if (page) {
        page.classList.add("active");
    }

    document.querySelectorAll(".nav-button").forEach(button => {
        button.classList.toggle(
            "active",
            button.dataset.page === pageId
        );
    });

    if (pageId === "shopPage") {
        loadShop();
    }

    if (pageId === "inventoryPage") {
        refresh();
    }

    if (pageId === "casesPage") {
        loadCases();
    }

    if (pageId === "profilePage") {
        refresh();
    }

    if (tg) {
        tg.BackButton.show();

        tg.BackButton.onClick(() => {
            showPage("homePage");
            tg.BackButton.hide();
        });
    }

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}


// ================================================
// КЕЙСЫ
// ================================================

async function loadCases() {
    const container = document.getElementById("casesList");

    if (!container) return;

    if (cases.length > 0) {
        renderCases();
        return;
    }

    container.innerHTML = '<div class="loading">Загрузка кейсов...</div>';

    try {
        const data = await api("/api/cases");

        cases = data.cases || [];

        renderCases();
        updateBattleCases();

    } catch (error) {
        container.innerHTML =
            '<div class="empty-state">Не удалось загрузить кейсы.</div>';

        showToast(error.message);
    }
}


function renderCases() {
    const container = document.getElementById("casesList");

    if (!container) return;

    if (!cases.length) {
        container.innerHTML =
            '<div class="empty-state">Кейсы пока недоступны.</div>';
        return;
    }

    container.innerHTML = cases.map(item => `
        <div class="case-card">
            <div class="case-image">${item.icon || "📦"}</div>

            <h3>${escapeHTML(item.name)}</h3>

            <p>🪙 ${formatNumber(item.price)}</p>

            <button onclick="selectCase('${escapeHTML(item.id)}')">
                ОТКРЫТЬ КЕЙС
            </button>
        </div>
    `).join("");
}


function selectCase(caseId) {
    selectedCase = cases.find(item => item.id === caseId);

    if (!selectedCase) {
        showToast("Кейс не найден.");
        return;
    }

    openCount = 1;

    document.getElementById("openingCaseName").textContent =
        selectedCase.name.toUpperCase();

    document.getElementById("openingCaseTitle").textContent =
        selectedCase.name;

    document.getElementById("openingCaseIcon").textContent =
        selectedCase.icon || "📦";

    document.getElementById("openingCasePrice").textContent =
        "Цена: " + formatNumber(selectedCase.price) + " монет";

    document.getElementById("openingResults").innerHTML = "";

    updateOpenCount();

    showPage("openingPage");
}


// ================================================
// КОЛИЧЕСТВО КЕЙСОВ
// ================================================

function setOpenCount(value) {
    openCount = Math.max(1, Math.min(50, Number(value) || 1));
    updateOpenCount();
}


function changeOpenCount(change) {
    setOpenCount(openCount + change);
}


function updateOpenCount() {
    const countElement = document.getElementById("openCount");
    const totalElement = document.getElementById("openTotal");

    if (countElement) {
        countElement.textContent = openCount;
    }

    if (totalElement && selectedCase) {
        totalElement.textContent = formatNumber(
            selectedCase.price * openCount
        );
    }
}


// ================================================
// ОТКРЫТИЕ КЕЙСОВ
// ================================================

async function openCases(demo) {
    if (!selectedCase) {
        showToast("Сначала выбери кейс.");
        return;
    }

    const total = selectedCase.price * openCount;

    if (!demo && balance < total) {
        showToast("Недостаточно монет.");
        return;
    }

    const buttons = document.querySelectorAll(
        ".opening-actions button"
    );

    buttons.forEach(button => button.disabled = true);

    const results = document.getElementById("openingResults");

    results.innerHTML =
        '<div class="loading">🎲 Открываем кейсы...</div>';

    try {
        const data = await api("/api/game/open", {
            method: "POST",
            body: JSON.stringify({
                case_id: selectedCase.id,
                count: openCount,
                demo: Boolean(demo)
            })
        });

        updateBalance(data.balance);

        if (!demo) {
            await refresh();
        }

        renderOpeningResults(data.drops, demo);

        if (demo) {
            showToast("Демо-открытие завершено!");
        } else {
            showToast("Кейсы открыты! Предметы добавлены в инвентарь.");
        }

    } catch (error) {
        results.innerHTML = "";
        showToast(error.message);

    } finally {
        buttons.forEach(button => button.disabled = false);
    }
}


function renderOpeningResults(drops, demo) {
    const container = document.getElementById("openingResults");

    if (!container) return;

    if (!drops || !drops.length) {
        container.innerHTML =
            '<div class="empty-state">Нет результатов.</div>';
        return;
    }

    const title = demo
        ? "РЕЗУЛЬТАТЫ ДЕМО-ОТКРЫТИЯ"
        : "ТВОИ ВЫПАВШИЕ ПРЕДМЕТЫ";

    container.innerHTML = `
        <div class="section-heading">
            <h2>${title}</h2>
        </div>

        ${demo ? `
            <p class="demo-note">
                Демо не списывает монеты и не добавляет предметы в инвентарь.
            </p>
        ` : ""}

        <div class="results-grid">
            ${drops.map(item => `
                <div class="result-card">
                    <div class="item-icon">${item.icon || "🔫"}</div>
                    <h4>${escapeHTML(item.name)}</h4>
                    <p>${escapeHTML(item.rarity)}</p>
                    <p>🪙 ${formatNumber(item.value)}</p>
                </div>
            `).join("")}
        </div>
    `;
}


// ================================================
// МАГАЗИН
// ================================================

async function loadShop() {
    const container = document.getElementById("shopList");

    if (!container) return;

    if (shopItems.length > 0) {
        renderShop();
        return;
    }

    container.innerHTML = '<div class="loading">Загрузка магазина...</div>';

    try {
        const data = await api("/api/shop");

        shopItems = data.items || [];

        renderShop();

    } catch (error) {
        container.innerHTML =
            '<div class="empty-state">Не удалось загрузить магазин.</div>';

        showToast(error.message);
    }
}


function renderShop() {
    const container = document.getElementById("shopList");

    if (!container) return;

    const filtered = currentFilter === "all"
        ? shopItems
        : shopItems.filter(item => item.category === currentFilter);

    if (!filtered.length) {
        container.innerHTML =
            '<div class="empty-state">Предметов пока нет.</div>';
        return;
    }

    container.innerHTML = filtered.map(item => `
        <div class="item-card">
            <div class="item-icon">${item.icon || "🔫"}</div>

            <h3>${escapeHTML(item.name)}</h3>

            <p class="item-type">${escapeHTML(item.type)}</p>

            <span class="rarity">${escapeHTML(item.rarity)}</span>

            <p class="item-price">
                🪙 ${formatNumber(item.price)}
            </p>

            <button onclick="buyItem(${Number(item.id)})">
                КУПИТЬ
            </button>
        </div>
    `).join("");
}


// ================================================
// ФИЛЬТРЫ МАГАЗИНА
// ================================================

document.querySelectorAll(".filter-button").forEach(button => {
    button.addEventListener("click", () => {
        document.querySelectorAll(".filter-button").forEach(item => {
            item.classList.remove("active");
        });

        button.classList.add("active");

        currentFilter = button.dataset.filter;

        renderShop();
    });
});


// ================================================
// ПОКУПКА ПРЕДМЕТОВ
// ================================================

async function buyItem(itemId) {
    const item = shopItems.find(x => x.id === itemId);

    if (!item) {
        showToast("Предмет не найден.");
        return;
    }

    if (balance < item.price) {
        showToast("Недостаточно монет.");
        return;
    }

    try {
        const data = await api("/api/buy", {
            method: "POST",
            body: JSON.stringify({
                item_id: itemId
            })
        });

        updateBalance(data.balance);

        await refresh();

        showToast("Покупка успешна!");

    } catch (error) {
        showToast(error.message);
    }
}


// ================================================
// ИНВЕНТАРЬ
// ================================================

function renderInventory() {
    const container = document.getElementById("inventoryList");
    const count = document.getElementById("inventoryCount");

    if (!container) return;

    if (count) {
        count.textContent = inventory.length;
    }

    if (!inventory.length) {
        container.innerHTML = `
            <div class="empty-state">
                🎒<br><br>
                Инвентарь пуст.<br>
                Открой кейс или купи предмет в магазине.
            </div>
        `;
        return;
    }

    container.innerHTML = inventory.map(item => `
        <div class="item-card">
            <div class="item-icon">${item.icon || "🔫"}</div>

            <h3>${escapeHTML(item.name)}</h3>

            <p class="item-type">${escapeHTML(item.type)}</p>

            <span class="rarity">${escapeHTML(item.rarity || "CLASSIFIED")}</span>

            <p class="item-price">
                🪙 ${formatNumber(item.value)}
            </p>

            ${item.source === "case" || item.source === "battle"
                ? `<small class="muted">Получено в игре</small>`
                : `<small class="muted">Покупка в магазине</small>`
            }
        </div>
    `).join("");
}


// ================================================
// ПРОДАЖА ПРЕДМЕТА
// ================================================

async function sellItem(itemId) {
    if (!confirm("Продать этот предмет за 80% его стоимости?")) {
        return;
    }

    try {
        const data = await api("/api/inventory/sell", {
            method: "POST",
            body: JSON.stringify({
                inventory_id: itemId
            })
        });

        updateBalance(data.balance);

        await refresh();

        showToast("Предмет продан!");

    } catch (error) {
        showToast(error.message);
    }
}


// ================================================
// ЕЖЕДНЕВНЫЙ БОНУС
// ================================================

async function claimBonus() {
    const button = document.getElementById("bonusButton");

    if (button) {
        button.disabled = true;
    }

    try {
        const data = await api("/api/bonus", {
            method: "POST"
        });

        updateBalance(data.balance);

        updateBonusButton(data.next_bonus_at);

        showToast("Ты получил " + data.awarded + " монет!");

    } catch (error) {
        showToast(error.message);

        await refresh();

    } finally {
        if (button && !button.dataset.waiting) {
            button.disabled = false;
        }
    }
}


function updateBonusButton(nextBonusAt) {
    const button = document.getElementById("bonusButton");
    const timer = document.getElementById("bonusTimer");

    if (!button || !timer) return;

    if (!nextBonusAt) {
        button.disabled = false;
        button.dataset.waiting = "";
        button.textContent = "ПОЛУЧИТЬ";
        timer.textContent = "Бонус доступен!";
        return;
    }

    const next = new Date(nextBonusAt);
    const now = new Date();

    if (next <= now) {
        button.disabled = false;
        button.dataset.waiting = "";
        button.textContent = "ПОЛУЧИТЬ";
        timer.textContent = "Бонус доступен!";
        return;
    }

    button.disabled = true;
    button.dataset.waiting = "true";
    button.textContent = "ПОЛУЧЕН";

    const difference = next - now;

    const hours = Math.floor(difference / 3600000);
    const minutes = Math.floor(
        (difference % 3600000) / 60000
    );

    const seconds = Math.floor(
        (difference % 60000) / 1000
    );

    timer.textContent =
        `Следующий бонус через ${hours}ч ${minutes}м ${seconds}с`;
}


// ================================================
// ПРОФИЛЬ
// ================================================

function renderProfile() {
    if (!currentUser) return;

    const name = document.getElementById("profileName");
    const username = document.getElementById("profileUsername");
    const tradeUrl = document.getElementById("steamTradeUrl");

    if (name) {
        name.textContent = currentUser.first_name || "Игрок";
    }

    if (username) {
        username.textContent = currentUser.username
            ? "@" + currentUser.username
            : "Telegram пользователь";
    }

    if (tradeUrl && document.activeElement !== tradeUrl) {
        tradeUrl.value = currentUser.steam_trade_url || "";
    }

    updateBalance(balance);
}


async function saveProfile() {
    const input = document.getElementById("steamTradeUrl");
    const message = document.getElementById("profileMessage");

    if (!input) return;

    try {
        const data = await api("/api/profile", {
            method: "PUT",
            body: JSON.stringify({
                steam_trade_url: input.value.trim()
            })
        });

        if (currentUser) {
            currentUser.steam_trade_url = data.steam_trade_url;
        }

        if (message) {
            message.textContent = "Ссылка успешно сохранена!";
        }

        showToast("Профиль обновлён.");

    } catch (error) {
        if (message) {
            message.textContent = error.message;
            message.style.color = "#ed6262";
        }

        showToast(error.message);
    }
}


// ================================================
// CASE BATTLE
// ================================================

function updateBattleCases() {
    const select = document.getElementById("battleCase");

    if (!select || !cases.length) return;

    select.innerHTML = cases.map(item => `
        <option value="${escapeHTML(item.id)}">
            ${escapeHTML(item.name)} — ${formatNumber(item.price)} монет
        </option>
    `).join("");
}


async function startBattle() {
    const caseId = document.getElementById("battleCase").value;
    const rounds = Number(
        document.getElementById("battleRounds").value
    );

    const stake = Number(
        document.getElementById("battleStake").value
    );

    const demo = document.getElementById("battleDemo").checked;

    const results = document.getElementById("battleResults");

    if (!caseId) {
        showToast("Выбери кейс.");
        return;
    }

    if (!Number.isInteger(stake) || stake < 1 || stake > 50000) {
        if (!demo) {
            showToast("Ставка должна быть от 1 до 50000 монет.");
            return;
        }
    }

    if (!demo && balance < stake) {
        showToast("Недостаточно монет для ставки.");
        return;
    }

    results.innerHTML =
        '<div class="loading">⚔️ Битва началась...</div>';

    try {
        const data = await api("/api/game/battle", {
            method: "POST",
            body: JSON.stringify({
                case_id: caseId,
                rounds: rounds,
                stake: stake,
                demo: demo,
                team_size: 1
            })
        });

        updateBalance(data.balance);

        if (!demo) {
            await refresh();
        }

        renderBattleResults(data);

    } catch (error) {
        results.innerHTML = "";
        showToast(error.message);
    }
}


function renderBattleResults(data) {
    const container = document.getElementById("battleResults");

    if (!container) return;

    let resultText = "";

    if (data.result === "win") {
        resultText = "🏆 ТЫ ПОБЕДИЛ!";

    } else if (data.result === "lose") {
        resultText = "😔 ПОБЕДИЛ БОТ";

    } else {
        resultText = "🤝 НИЧЬЯ";
    }

    container.innerHTML = `
        <div class="battle-result">
            <h3>РЕЗУЛЬТАТ БИТВЫ</h3>

            <div class="battle-players">
                <div class="battle-player">
                    <strong>ТЫ</strong>
                    <div class="score">
                        ${formatNumber(data.player_total)}
                    </div>
                    <small>Стоимость предметов</small>
                </div>

                <div class="battle-player">
                    <strong>БОТ</strong>
                    <div class="score">
                        ${formatNumber(data.opponent_total)}
                    </div>
                    <small>Стоимость предметов</small>
                </div>
            </div>

            <div class="winner">${resultText}</div>

            <div class="section-heading">
                <h2>Твои предметы</h2>
            </div>

            <div class="results-grid">
                ${data.player_drops.map(item => `
                    <div class="result-card">
                        <div class="item-icon">${item.icon || "🔫"}</div>
                        <h4>${escapeHTML(item.name)}</h4>
                        <p>🪙 ${formatNumber(item.value)}</p>
                    </div>
                `).join("")}
            </div>

            <div class="section-heading">
                <h2>Предметы бота</h2>
            </div>

            <div class="results-grid">
                ${data.opponent_drops.map(item => `
                    <div class="result-card">
                        <div class="item-icon">${item.icon || "🔫"}</div>
                        <h4>${escapeHTML(item.name)}</h4>
                        <p>🪙 ${formatNumber(item.value)}</p>
                    </div>
                `).join("")}
            </div>

            <p class="battle-note">
                ${data.demo
                    ? "Демо-битва: баланс и инвентарь не изменены."
                    : "Общий банк: " + formatNumber(data.pot) + " монет."
                }
            </p>
        </div>
    `;
}


// ================================================
// ЗАЩИТА ТЕКСТА В HTML
// ================================================

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => {
        const entities = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        };

        return entities[character];
    });
}


// ================================================
// ТАЙМЕР БОНУСА
// ================================================

setInterval(() => {
    if (currentUser) {
        refreshBonusTimer();
    }
}, 1000);


function refreshBonusTimer() {
    const timer = document.getElementById("bonusTimer");

    if (!timer) return;

    const button = document.getElementById("bonusButton");

    if (!button || !button.dataset.waiting) return;

    const text = timer.textContent;

    if (!text.startsWith("Следующий бонус через")) return;

    // Обновляем состояние бонуса с сервера при необходимости.
    // Точное время доступности проверяется сервером при получении.
}


// ================================================
// ЗАПУСК ПРИЛОЖЕНИЯ
// ================================================

async function initApp() {
    if (!tg || !tg.initData) {
        showToast(
            "Для работы приложения открой его через Telegram."
        );

        return;
    }

    await refresh();

    await Promise.all([
        loadCases(),
        loadShop()
    ]);

    updateBattleCases();
}


document.addEventListener("DOMContentLoaded", () => {
    initApp();
});
