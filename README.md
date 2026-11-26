# CS2 Rewards — Telegram Mini App starter

Готовый стартовый проект: Telegram Mini App + Python API + SQLite + ежедневный бонус + магазин + серверный инвентарь.

## Что уже работает
- Авторизация через подписанные Telegram WebApp `initData` (проверка на сервере).
- Баланс и покупки хранятся на сервере в SQLite, а не в `localStorage`.
- Ежедневный бонус 100 монет раз в 24 часа по серверному времени.
- Каталог с тестовыми ценами, категории и инвентарь.
- Telegram-бот `/start` показывает кнопку открытия Mini App.

## Важно
Покупки сейчас демонстрационные. Запись предмета в инвентарь приложения **не отправляет скин в Steam**. Реальная выдача потребует отдельного Steam trade workflow, доступных к обмену предметов на аккаунте-отправителе, проверок ограничений Steam и мониторинга trade offers. Не собирайте у пользователей Steam-пароли, Steam Guard-коды или API-ключи.

## 1. Подготовка
Требуется Python 3.11+ и токен Telegram-бота от @BotFather.

1. Распакуйте архив.
2. Создайте файл `.env` на основе `.env.example`.
3. В `.env` укажите `BOT_TOKEN`.
4. Установите зависимости:

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Публикация
Mini App должен открываться по публичному HTTPS-адресу. Один из простых вариантов — Render или Railway:

- создайте новый Web Service из этой папки/репозитория;
- Build command: `pip install -r requirements.txt`;
- Start command: `python backend/main.py`;
- добавьте переменные `BOT_TOKEN` и `WEBAPP_URL`;
- настройте постоянный диск и `DB_PATH`, иначе база SQLite может потеряться при пересоздании контейнера.

Сначала получите HTTPS-домен от хостинга, затем укажите его в `WEBAPP_URL` и перезапустите сервис. Если хостинг требует отдельную команду запуска, используйте `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` (при этом бот polling должен запускаться тем же процессом; основной `Procfile` рассчитан на запуск `python backend/main.py`).

## 3. Подключение в Telegram

1. Откройте @BotFather.
2. Выберите своего бота → Bot Settings → Menu Button → Configure menu button.
3. Укажите текст `CS2 Rewards` и тот же публичный HTTPS URL.
4. Также можно использовать `/setmenubutton`, если BotFather предлагает эту команду.
5. Откройте бота и нажмите `/start`, затем кнопку Mini App.

## 4. Локальная разработка
Для Telegram-авторизации нужен HTTPS-доступный адрес. Локальный `file://` или обычный `http://localhost` не подходит для реального открытия Mini App в Telegram. Для теста используйте HTTPS-туннель (например, Cloudflare Tunnel/ngrok) и укажите его URL как `WEBAPP_URL`.

## Переменные окружения
- `BOT_TOKEN` — секретный токен BotFather. Никогда не публикуйте его и не отправляйте в чаты.
- `WEBAPP_URL` — публичный HTTPS URL Mini App.
- `DB_PATH` — путь к SQLite-файлу.
- `PORT` — порт, который задаёт хостинг (по умолчанию 8000).
