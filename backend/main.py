
import asyncio
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlparse

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import WebAppInfo, MenuButtonWebApp
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


# --------------------------------------------------
# НАСТРОЙКИ
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

DB_PATH = Path(
    os.getenv("DB_PATH", str(ROOT / "data" / "cs2rewards.sqlite3"))
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")

BONUS_AMOUNT = 10
BONUS_HOURS = 24


# --------------------------------------------------
# МАГАЗИН
# --------------------------------------------------

CATALOG = [
    {"id": 1, "name": "AK-47 | Redline", "type": "Винтовка",
     "category": "rifles", "price": 2500, "icon": "🔫", "rarity": "CLASSIFIED"},

    {"id": 2, "name": "AWP | Asiimov", "type": "Снайперская винтовка",
     "category": "snipers", "price": 5000, "icon": "🎯", "rarity": "COVERT"},

    {"id": 3, "name": "M4A4 | Neo-Noir", "type": "Винтовка",
     "category": "rifles", "price": 3200, "icon": "🔫", "rarity": "COVERT"},

    {"id": 4, "name": "Glock-18 | Fade", "type": "Пистолет",
     "category": "pistols", "price": 4000, "icon": "🔫", "rarity": "RESTRICTED"},

    {"id": 5, "name": "AWP | Dragon Lore", "type": "Снайперская винтовка",
     "category": "snipers", "price": 250000, "icon": "🐉", "rarity": "COVERT"},

    {"id": 6, "name": "Karambit | Fade", "type": "Нож",
     "category": "knives", "price": 180000, "icon": "🔪", "rarity": "COVERT"},

    {"id": 7, "name": "USP-S | Kill Confirmed", "type": "Пистолет",
     "category": "pistols", "price": 4200, "icon": "🔫", "rarity": "COVERT"},

    {"id": 8, "name": "Butterfly Knife | Doppler", "type": "Нож",
     "category": "knives", "price": 220000, "icon": "🔪", "rarity": "COVERT"},

    {"id": 9, "name": "M4A1-S | Printstream", "type": "Винтовка",
     "category": "rifles", "price": 7000, "icon": "🔫", "rarity": "COVERT"},

    {"id": 10, "name": "Sport Gloves | Vice", "type": "Перчатки",
     "category": "gloves", "price": 150000, "icon": "🧤", "rarity": "EXTRAORDINARY"},
]


# --------------------------------------------------
# КЕЙСЫ
# В каждом кейсе ровно 10 предметов.
# Вес определяет вероятность выпадения.
# --------------------------------------------------

def skin(name, item_type, value, rarity, weight, icon="🔫"):
    return {
        "name": name,
        "type": item_type,
        "value": value,
        "rarity": rarity,
        "weight": weight,
        "icon": icon
    }


def make_case(case_id, name, price, drops):
    return {
        "id": case_id,
        "name": name,
        "price": price,
        "icon": "📦",
        "drops": drops
    }


CASES = [
    make_case("starter", "Starter Case", 50, [
        skin("Glock-18 | Candy", "Пистолет", 20, "MIL-SPEC", 30),
        skin("MP9 | Sand", "ПП", 35, "MIL-SPEC", 25),
        skin("P250 | Sand Dune", "Пистолет", 45, "MIL-SPEC", 18),
        skin("UMP-45 | Gunsmoke", "ПП", 60, "RESTRICTED", 10),
        skin("FAMAS | Survivor Z", "Винтовка", 80, "RESTRICTED", 7),
        skin("Galil AR | Stone Cold", "Винтовка", 100, "RESTRICTED", 4),
        skin("AK-47 | Slate", "Винтовка", 180, "CLASSIFIED", 2),
        skin("AWP | Atheris", "Снайперская винтовка", 250, "CLASSIFIED", 2),
        skin("USP-S | Cortex", "Пистолет", 400, "COVERT", 1),
        skin("Shadow Daggers | Safari Mesh", "Нож", 1200, "COVERT", 1, "🔪")
    ]),

    make_case("bronze", "Bronze Case", 100, [
        skin("P2000 | Pulse", "Пистолет", 40, "MIL-SPEC", 28),
        skin("Nova | Koi", "Дробовик", 55, "MIL-SPEC", 22),
        skin("MAC-10 | Neon Rider", "ПП", 100, "RESTRICTED", 16),
        skin("Five-SeveN | Monkey Business", "Пистолет", 130, "RESTRICTED", 12),
        skin("M4A1-S | Decimator", "Винтовка", 220, "CLASSIFIED", 8),
        skin("AK-47 | Frontside Misty", "Винтовка", 280, "CLASSIFIED", 6),
        skin("AWP | Hyper Beast", "Снайперская винтовка", 500, "COVERT", 3),
        skin("USP-S | Kill Confirmed", "Пистолет", 650, "COVERT", 2),
        skin("Huntsman Knife | Forest", "Нож", 1500, "COVERT", 2, "🔪"),
        skin("Driver Gloves | Racing Green", "Перчатки", 2200, "EXTRAORDINARY", 1, "🧤")
    ]),

    make_case("silver", "Silver Case", 180, [
        skin("MP7 | Ocean Foam", "ПП", 70, "MIL-SPEC", 26),
        skin("P250 | Muertos", "Пистолет", 100, "MIL-SPEC", 22),
        skin("M4A4 | Evil Daimyo", "Винтовка", 150, "RESTRICTED", 16),
        skin("AWP | Fever Dream", "Снайперская винтовка", 220, "RESTRICTED", 12),
        skin("AK-47 | Redline", "Винтовка", 350, "CLASSIFIED", 9),
        skin("M4A4 | Neo-Noir", "Винтовка", 500, "CLASSIFIED", 6),
        skin("AWP | Asiimov", "Снайперская винтовка", 850, "COVERT", 4),
        skin("Glock-18 | Fade", "Пистолет", 1000, "COVERT", 2),
        skin("Bowie Knife | Doppler", "Нож", 2500, "COVERT", 2, "🔪"),
        skin("Moto Gloves | Eclipse", "Перчатки", 4000, "EXTRAORDINARY", 1, "🧤")
    ]),

    make_case("gold", "Gold Case", 300, [
        skin("Desert Eagle | Bronze Deco", "Пистолет", 90, "MIL-SPEC", 25),
        skin("Galil AR | Eco", "Винтовка", 140, "MIL-SPEC", 20),
        skin("M4A1-S | Hyper Beast", "Винтовка", 260, "RESTRICTED", 16),
        skin("AK-47 | Neon Revolution", "Винтовка", 400, "RESTRICTED", 12),
        skin("AWP | Containment Breach", "Снайперская винтовка", 650, "CLASSIFIED", 9),
        skin("USP-S | Printstream", "Пистолет", 900, "CLASSIFIED", 7),
        skin("AK-47 | Fire Serpent", "Винтовка", 1800, "COVERT", 4),
        skin("AWP | Dragon Lore", "Снайперская винтовка", 3500, "COVERT", 3),
        skin("Karambit | Crimson Web", "Нож", 6000, "COVERT", 2, "🔪"),
        skin("Specialist Gloves | Fade", "Перчатки", 8000, "EXTRAORDINARY", 2, "🧤")
    ]),

    make_case("pro", "Pro Case", 450, [
        skin("P90 | Asiimov", "ПП", 100, "MIL-SPEC", 24),
        skin("FAMAS | Mecha Industries", "Винтовка", 180, "MIL-SPEC", 20),
        skin("M4A4 | The Emperor", "Винтовка", 300, "RESTRICTED", 16),
        skin("AK-47 | Asiimov", "Винтовка", 500, "RESTRICTED", 12),
        skin("AWP | Neo-Noir", "Снайперская винтовка", 800, "CLASSIFIED", 9),
        skin("USP-S | Monster Mashup", "Пистолет", 1100, "CLASSIFIED", 7),
        skin("M4A1-S | Printstream", "Винтовка", 1800, "COVERT", 5),
        skin("AK-47 | Wild Lotus", "Винтовка", 3000, "COVERT", 3),
        skin("Butterfly Knife | Slaughter", "Нож", 6500, "COVERT", 2, "🔪"),
        skin("Sport Gloves | Vice", "Перчатки", 9000, "EXTRAORDINARY", 2, "🧤")
    ]),

    make_case("elite", "Elite Case", 700, [
        skin("MP9 | Starlight Protector", "ПП", 180, "MIL-SPEC", 24),
        skin("Glock-18 | Water Elemental", "Пистолет", 250, "MIL-SPEC", 20),
        skin("M4A1-S | Golden Coil", "Винтовка", 450, "RESTRICTED", 16),
        skin("AK-47 | The Empress", "Винтовка", 700, "RESTRICTED", 12),
        skin("AWP | Wildfire", "Снайперская винтовка", 1000, "CLASSIFIED", 9),
        skin("Desert Eagle | Printstream", "Пистолет", 1400, "CLASSIFIED", 7),
        skin("AK-47 | Vulcan", "Винтовка", 2400, "COVERT", 5),
        skin("AWP | Gungnir", "Снайперская винтовка", 4500, "COVERT", 3),
        skin("M9 Bayonet | Doppler", "Нож", 8000, "COVERT", 2, "🔪"),
        skin("Hand Wraps | Cobalt Skulls", "Перчатки", 11000, "EXTRAORDINARY", 2, "🧤")
    ]),

    make_case("royal", "Royal Case", 1000, [
        skin("P250 | See Ya Later", "Пистолет", 250, "MIL-SPEC", 24),
        skin("AK-47 | Ice Coaled", "Винтовка", 350, "MIL-SPEC", 20),
        skin("M4A4 | Dragon King", "Винтовка", 600, "RESTRICTED", 16),
        skin("AWP | Duality", "Снайперская винтовка", 850, "RESTRICTED", 12),
        skin("USP-S | The Traitor", "Пистолет", 1300, "CLASSIFIED", 9),
        skin("AK-47 | Bloodsport", "Винтовка", 1800, "CLASSIFIED", 7),
        skin("AWP | Fade", "Снайперская винтовка", 3000, "COVERT", 5),
        skin("M4A1-S | Welcome to the Jungle", "Винтовка", 5000, "COVERT", 3),
        skin("Butterfly Knife | Fade", "Нож", 9500, "COVERT", 2, "🔪"),
        skin("Sport Gloves | Pandora's Box", "Перчатки", 14000, "EXTRAORDINARY", 2, "🧤")
    ]),

    make_case("diamond", "Diamond Case", 1500, [
        skin("Five-SeveN | Angry Mob", "Пистолет", 300, "MIL-SPEC", 24),
        skin("MAC-10 | Stalker", "ПП", 450, "MIL-SPEC", 20),
        skin("M4A4 | Dragon King", "Винтовка", 750, "RESTRICTED", 16),
        skin("AK-47 | Neon Rider", "Винтовка", 1100, "RESTRICTED", 12),
        skin("AWP | Oni Taiji", "Снайперская винтовка", 1700, "CLASSIFIED", 9),
        skin("Desert Eagle | Code Red", "Пистолет", 2300, "CLASSIFIED", 7),
        skin("AK-47 | Gold Arabesque", "Винтовка", 4000, "COVERT", 5),
        skin("AWP | Medusa", "Снайперская винтовка", 6500, "COVERT", 3),
        skin("Karambit | Doppler", "Нож", 12000, "COVERT", 2, "🔪"),
        skin("Specialist Gloves | Crimson Kimono", "Перчатки", 18000, "EXTRAORDINARY", 2, "🧤")
    ]),

    make_case("legend", "Legend Case", 2500, [
        skin("USP-S | Cortex", "Пистолет", 450, "MIL-SPEC", 24),
        skin("AK-47 | Phantom Disruptor", "Винтовка", 650, "MIL-SPEC", 20),
        skin("M4A1-S | Player Two", "Винтовка", 1000, "RESTRICTED", 16),
        skin("AWP | Hyper Beast", "Снайперская винтовка", 1500, "RESTRICTED", 12),
        skin("AK-47 | Head Shot", "Винтовка", 2200, "CLASSIFIED", 9),
        skin("M4A4 | Howl", "Винтовка", 3500, "CLASSIFIED", 7),
        skin("AWP | Dragon Lore", "Снайперская винтовка", 6000, "COVERT", 5),
        skin("AK-47 | Wild Lotus", "Винтовка", 8500, "COVERT", 3),
        skin("Butterfly Knife | Doppler", "Нож", 15000, "COVERT", 2, "🔪"),
        skin("Sport Gloves | Pandora's Box", "Перчатки", 22000, "EXTRAORDINARY", 2, "🧤")
    ]),

    make_case("supreme", "Supreme Case", 5000, [
        skin("Glock-18 | Gamma Doppler", "Пистолет", 700, "MIL-SPEC", 24),
        skin("Desert Eagle | Blaze", "Пистолет", 1000, "MIL-SPEC", 20),
        skin("M4A1-S | Blue Phosphor", "Винтовка", 1600, "RESTRICTED", 16),
        skin("AK-47 | Case Hardened", "Винтовка", 2300, "RESTRICTED", 12),
        skin("AWP | The Prince", "Снайперская винтовка", 3500, "CLASSIFIED", 9),
        skin("M4A4 | Poseidon", "Винтовка", 5000, "CLASSIFIED", 7),
        skin("AK-47 | Gold Arabesque", "Винтовка", 8000, "COVERT", 5),
        skin("AWP | Dragon Lore", "Снайперская винтовка", 12000, "COVERT", 3),
        skin("Karambit | Fade", "Нож", 20000, "COVERT", 2, "🔪"),
        skin("Sport Gloves | Vice", "Перчатки", 30000, "EXTRAORDINARY", 2, "🧤")
    ])
]


# --------------------------------------------------
# ПРИЛОЖЕНИЕ И БАЗА ДАННЫХ
# --------------------------------------------------

app = FastAPI(title="CS2 Rewards API")
bot = Bot(BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher()


@contextmanager
def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                first_name TEXT NOT NULL,
                balance INTEGER NOT NULL DEFAULT 0,
                last_bonus REAL
            )
        """)

        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }

        migrations = {
            "username": "TEXT",
            "created_at": "TEXT",
            "last_seen": "TEXT",
            "steam_trade_url": "TEXT"
        }

        for name, definition in migrations.items():
            if name not in columns:
                conn.execute(
                    f"ALTER TABLE users ADD COLUMN {name} {definition}"
                )

        conn.execute("""
            UPDATE users
            SET created_at = COALESCE(created_at, datetime('now'))
        """)

        conn.execute("""
            UPDATE users
            SET last_seen = COALESCE(last_seen, datetime('now'))
        """)

        # Старая таблица inventory остаётся для совместимости
        # с уже купленными предметами.
                conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                  item_id INTEGER,
                item_name TEXT NOT NULL,
                item_type TEXT,
                item_category TEXT,
                price INTEGER DEFAULT 0,
                purchased_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                rarity TEXT NOT NULL,
                value INTEGER NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS battles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                result TEXT NOT NULL,
                player_total INTEGER NOT NULL,
                bot_total INTEGER NOT NULL,
                stake INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)


# --------------------------------------------------
# АВТОРИЗАЦИЯ TELEGRAM
# --------------------------------------------------

def validate_init_data(init_data: str) -> dict:
    if not BOT_TOKEN:
        raise HTTPException(
            503,
            "Бот не настроен. Добавьте BOT_TOKEN в Render."
        )

    if not init_data:
        raise HTTPException(
            401,
            "Откройте приложение через Telegram."
        )

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)

    if not received_hash:
        raise HTTPException(
            401,
            "Не найдена подпись Telegram."
        )

    data_check_string = "\n".join(
        f"{key}={value}"
        for key, value in sorted(parsed.items())
    )

    secret_key = hmac.new(
        b"WebAppData",
        BOT_TOKEN.encode(),
        hashlib.sha256
    ).digest()

    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(
            401,
            "Не удалось проверить авторизацию Telegram."
        )

    try:
        auth_date = int(parsed.get("auth_date", "0"))

        if time.time() - auth_date > 86400:
            raise HTTPException(401, "Сессия Telegram устарела.")

        if auth_date > time.time() + 60:
            raise HTTPException(401, "Неверное время авторизации.")

        telegram_user = json.loads(parsed["user"])
        telegram_id = int(telegram_user["id"])

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            401,
            "Не удалось прочитать профиль Telegram."
        )

    return {
        "id": telegram_id,
        "first_name": str(
            telegram_user.get("first_name", "Player")
        )[:64],
        "username": str(
            telegram_user.get("username", "")
        )[:64]
    }


def current_user(x_telegram_init_data: str = Header(default="")):
    return validate_init_data(x_telegram_init_data)


# --------------------------------------------------
# ПОЛЬЗОВАТЕЛИ И ИНВЕНТАРЬ
# --------------------------------------------------

def ensure_user(user):
    now = datetime.now(timezone.utc).isoformat()

    with db() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO users
            (telegram_id, first_name, username, balance, created_at, last_seen)
            VALUES (?, ?, ?, 0, ?, ?)
        """, (
            user["id"],
            user["first_name"],
            user.get("username", ""),
            now,
            now
        ))

        conn.execute("""
            UPDATE users
            SET first_name = ?, username = ?, last_seen = ?
            WHERE telegram_id = ?
        """, (
            user["first_name"],
            user.get("username", ""),
            now,
            user["id"]
        ))

        return conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?",
            (user["id"],)
        ).fetchone()


def add_inventory(conn, telegram_id, item, source):
    conn.execute("""
        INSERT INTO player_inventory
        (telegram_id, item_name, item_type, rarity, value, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        telegram_id,
        item["name"],
        item["type"],
        item["rarity"],
        item["value"],
        source,
        datetime.now(timezone.utc).isoformat()
    ))


def get_inventory(telegram_id):
    result = []

    with db() as conn:
        # Предметы, купленные в старой версии приложения.
        old_items = conn.execute("""
            SELECT
                id,
                item_name AS name,
                item_type AS type,
                item_category AS category,
                price AS value,
                'legacy' AS source,
                purchased_at AS created_at
            FROM inventory
            WHERE telegram_id = ?
            ORDER BY id DESC
        """, (telegram_id,)).fetchall()

        for item in old_items:
            row = dict(item)
            row["id"] = -row["id"]
            row["rarity"] = "CLASSIFIED"
            row["icon"] = "🔫"
            result.append(row)

        # Новые предметы.
        new_items = conn.execute("""
            SELECT
                id,
                item_name AS name,
                item_type AS type,
                rarity,
                value,
                source,
                created_at
            FROM player_inventory
            WHERE telegram_id = ?
            ORDER BY id DESC
        """, (telegram_id,)).fetchall()

        for item in new_items:
            row = dict(item)
            row["icon"] = "🔫"
            result.append(row)

    return result


# --------------------------------------------------
# РАБОТА С КЕЙСАМИ
# --------------------------------------------------

def get_case(case_id):
    case = next(
        (item for item in CASES if item["id"] == case_id),
        None
    )

    if not case:
        raise HTTPException(404, "Кейс не найден.")

    return case


def choose_drop(case):
    total_weight = sum(
        item["weight"] for item in case["drops"]
    )

    number = secrets.randbelow(total_weight)

    for item in case["drops"]:
        if number < item["weight"]:
            return {
                key: value
                for key, value in item.items()
                if key != "weight"
            }

        number -= item["weight"]

    return {
        key: value
        for key, value in case["drops"][-1].items()
        if key != "weight"
    }


def public_case(case):
    return {
        "id": case["id"],
        "name": case["name"],
        "price": case["price"],
        "icon": case["icon"],
        "skins": [
            {
                key: value
                for key, value in item.items()
                if key != "weight"
            }
            for item in case["drops"]
        ]
    }


# --------------------------------------------------
# ПРОВЕРКА STEAM TRADE URL
# --------------------------------------------------

def validate_trade_url(value):
    value = (value or "").strip()

    if not value:
        return ""

    parsed = urlparse(value)

    if parsed.scheme != "https":
        raise HTTPException(
            400,
            "Ссылка должна начинаться с https://"
        )

    if parsed.hostname not in (
        "steamcommunity.com",
        "www.steamcommunity.com"
    ):
        raise HTTPException(
            400,
            "Укажите официальную ссылку Steam."
        )

    if parsed.path.rstrip("/") != "/tradeoffer/new":
        raise HTTPException(
            400,
            "Неверный адрес Steam Trade URL."
        )

    query = parse_qs(parsed.query)

    partner = query.get("partner", [""])[0]
    token = query.get("token", [""])[0]

    if not partner.isdigit():
        raise HTTPException(
            400,
            "В ссылке отсутствует правильный partner."
        )

    if not (5 <= len(token) <= 32) or not token.isalnum():
        raise HTTPException(
            400,
            "Проверьте token в Steam Trade URL."
        )

    return value


# --------------------------------------------------
# КОМАНДЫ TELEGRAM-БОТА
# --------------------------------------------------

@dp.message(Command("myid"))
async def myid_handler(message: types.Message):
    await message.answer(
        f"Твой Telegram ID: {message.from_user.id}"
    )


@dp.message(Command("stats"))
async def stats_handler(message: types.Message):
    if not ADMIN_ID or message.from_user.id != ADMIN_ID:
        await message.answer("Нет доступа к статистике.")
        return

    with db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        active = conn.execute("""
            SELECT COUNT(*)
            FROM users
            WHERE julianday(last_seen) >= julianday('now', '-7 days')
        """).fetchone()[0]

    await message.answer(
        "📊 Статистика CS2 Rewards\n\n"
        f"Пользователей: {total}\n"
        f"Активных за 7 дней: {active}"
    )


@dp.message(CommandStart())
async def start_handler(message: types.Message):
    ensure_user({
        "id": message.from_user.id,
        "first_name": message.from_user.first_name or "Player",
        "username": message.from_user.username or ""
    })

    if not WEBAPP_URL:
        await message.answer(
            "Mini App ещё не опубликовано. "
            "Настройте WEBAPP_URL в Render."
        )
        return

    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[
            types.KeyboardButton(
                text="Открыть CS2 Rewards",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )
        ]],
        resize_keyboard=True
    )

    await message.answer(
        "Добро пожаловать в CS2 Rewards!",
        reply_markup=keyboard
    )

    if bot:
        await bot.set_chat_menu_button(
            chat_id=message.chat.id,
            menu_button=MenuButtonWebApp(
                text="CS2 Rewards",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )
        )


# --------------------------------------------------
# ЗАПУСК И ОСТАНОВКА
# --------------------------------------------------

@app.on_event("startup")
async def startup():
    init_db()

    if bot:
        asyncio.create_task(dp.start_polling(bot))


@app.on_event("shutdown")
async def shutdown():
    if bot:
        await bot.session.close()


# --------------------------------------------------
# ГЛАВНАЯ СТРАНИЦА
# --------------------------------------------------

@app.get("/")
async def index():
    return FileResponse(FRONTEND / "index.html")


# --------------------------------------------------
# ПРОФИЛЬ И ДАННЫЕ ПОЛЬЗОВАТЕЛЯ
# --------------------------------------------------

@app.get("/api/me")
async def me(x_telegram_init_data: str = Header(default="")):
    user = validate_init_data(x_telegram_init_data)
    row = ensure_user(user)

    next_bonus = None

    if row["last_bonus"]:
        next_bonus = (
            datetime.fromtimestamp(
                row["last_bonus"],
                timezone.utc
            ) + timedelta(hours=BONUS_HOURS)
        )

    return {
        "user": {
            "id": user["id"],
            "first_name": user["first_name"],
            "username": user["username"]
        },
        "balance": row["balance"],
        "next_bonus_at": (
            next_bonus.isoformat() if next_bonus else None
        ),
        "steam_trade_url": row["steam_trade_url"] or "",
        "inventory": get_inventory(user["id"])
    }


class ProfileRequest(BaseModel):
    steam_trade_url: str = Field(default="", max_length=500)


@app.put("/api/profile")
async def save_profile(
    payload: ProfileRequest,
    x_telegram_init_data: str = Header(default="")
):
    user = validate_init_data(x_telegram_init_data)
    ensure_user(user)

    trade_url = validate_trade_url(
        payload.steam_trade_url
    )

    with db() as conn:
        conn.execute("""
            UPDATE users
            SET steam_trade_url = ?
            WHERE telegram_id = ?
        """, (trade_url, user["id"]))

    return {
        "saved": True,
        "steam_trade_url": trade_url
    }


# --------------------------------------------------
# МАГАЗИН
# --------------------------------------------------

@app.get("/api/shop")
async def shop(x_telegram_init_data: str = Header(default="")):
    validate_init_data(x_telegram_init_data)

    return {"items": CATALOG}


class BuyRequest(BaseModel):
    item_id: int


@app.post("/api/buy")
async def buy_item(
    payload: BuyRequest,
    x_telegram_init_data: str = Header(default="")
):
    user = validate_init_data(x_telegram_init_data)

    item = next(
        (x for x in CATALOG if x["id"] == payload.item_id),
        None
    )

    if not item:
        raise HTTPException(404, "Предмет не найден.")

    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            "SELECT balance FROM users WHERE telegram_id = ?",
            (user["id"],)
        ).fetchone()

        if not row or row["balance"] < item["price"]:
            raise HTTPException(
                400,
                "Недостаточно монет для покупки."
            )

        new_balance = row["balance"] - item["price"]

        conn.execute("""
            UPDATE users
            SET balance = ?
            WHERE telegram_id = ?
        """, (new_balance, user["id"]))

        add_inventory(
            conn,
            user["id"],
            {
                "name": item["name"],
                "type": item["type"],
                "rarity": item["rarity"],
                "value": item["price"]
            },
            "shop"
        )

    return {
        "balance": new_balance,
        "item_name": item["name"]
    }


# --------------------------------------------------
# СПИСОК КЕЙСОВ
# --------------------------------------------------

@app.get("/api/cases")
async def cases(x_telegram_init_data: str = Header(default="")):
    validate_init_data(x_telegram_init_data)

    return {
        "cases": [public_case(case) for case in CASES]
    }


# --------------------------------------------------
# ЕЖЕДНЕВНЫЙ БОНУС
# --------------------------------------------------

@app.post("/api/bonus")
async def claim_bonus(
    x_telegram_init_data: str = Header(default="")
):
    user = validate_init_data(x_telegram_init_data)
    now = time.time()

    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")

        conn.execute("""
            INSERT OR IGNORE INTO users
            (telegram_id, first_name, balance)
            VALUES (?, ?, 0)
        """, (user["id"], user["first_name"]))

        row = conn.execute("""
            SELECT balance, last_bonus
            FROM users
            WHERE telegram_id = ?
        """, (user["id"],)).fetchone()

        if (
            row["last_bonus"]
            and now - row["last_bonus"] < BONUS_HOURS * 3600
        ):
            raise HTTPException(
                429,
                "Ежедневный бонус уже получен."
            )

        new_balance = row["balance"] + BONUS_AMOUNT

        conn.execute("""
            UPDATE users
            SET balance = ?, last_bonus = ?
            WHERE telegram_id = ?
        """, (new_balance, now, user["id"]))

    next_bonus = datetime.fromtimestamp(
        now + BONUS_HOURS * 3600,
        timezone.utc
    ).isoformat()

    return {
        "awarded": BONUS_AMOUNT,
        "balance": new_balance,
        "next_bonus_at": next_bonus
    }


# --------------------------------------------------
# ОТКРЫТИЕ КЕЙСОВ
# --------------------------------------------------

class OpenRequest(BaseModel):
    case_id: str
    count: int = Field(default=1, ge=1, le=50)
    demo: bool = False


@app.post("/api/game/open")
async def open_cases(
    payload: OpenRequest,
    x_telegram_init_data: str = Header(default="")
):
    user = validate_init_data(x_telegram_init_data)
    case = get_case(payload.case_id)

    total_cost = case["price"] * payload.count

    # Все результаты рассчитываются на сервере.
    drops = [
        choose_drop(case)
        for _ in range(payload.count)
    ]

    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute("""
            SELECT balance
            FROM users
            WHERE telegram_id = ?
        """, (user["id"],)).fetchone()

        if not row:
            raise HTTPException(
                404,
                "Пользователь не найден."
            )

        balance = row["balance"]

        # Демо не списывает монеты и не сохраняет предметы.
        if not payload.demo:
            if balance < total_cost:
                raise HTTPException(
                    400,
                    f"Недостаточно монет. Нужно: {total_cost}."
                )

            balance -= total_cost

            conn.execute("""
                UPDATE users
                SET balance = ?
                WHERE telegram_id = ?
            """, (balance, user["id"]))

            for drop in drops:
                add_inventory(
                    conn,
                    user["id"],
                    drop,
                    "case"
                )

    return {
        "demo": payload.demo,
        "case": case["name"],
        "count": payload.count,
        "total_cost": 0 if payload.demo else total_cost,
        "drops": drops,
        "balance": balance
    }


# --------------------------------------------------
# CASE BATTLE ПРОТИВ БОТА
# --------------------------------------------------

class BattleRequest(BaseModel):
    case_id: str
    rounds: int = Field(default=3, ge=1, le=10)
    stake: int = Field(default=50, ge=0, le=50000)
    demo: bool = False
    team_size: int = Field(default=1, ge=1, le=4)


@app.post("/api/game/battle")
async def battle(
    payload: BattleRequest,
    x_telegram_init_data: str = Header(default="")
):
    user = validate_init_data(x_telegram_init_data)
    case = get_case(payload.case_id)

    player_drops = [
        choose_drop(case)
        for _ in range(payload.rounds)
    ]

    bot_drops = [
        choose_drop(case)
        for _ in range(payload.rounds)
    ]

    player_total = sum(
        item["value"] for item in player_drops
    )

    bot_total = sum(
        item["value"] for item in bot_drops
    )

    if player_total > bot_total:
        result = "win"
    elif player_total < bot_total:
        result = "lose"
    else:
        result = "draw"

    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute("""
            SELECT balance
            FROM users
            WHERE telegram_id = ?
        """, (user["id"],)).fetchone()

        if not row:
            raise HTTPException(
                404,
                "Пользователь не найден."
            )

        balance = row["balance"]
        stake = 0 if payload.demo else payload.stake

        if not payload.demo:
            if stake <= 0:
                raise HTTPException(
                    400,
                    "Ставка должна быть больше нуля."
                )

            if balance < stake:
                raise HTTPException(
                    400,
                    "Недостаточно монет для ставки."
                )

            # Сначала списываем ставку игрока.
            balance -= stake

            # Победитель получает весь банк.
            if result == "win":
                balance += stake * 2

                # Предметы победителя сохраняются.
                for item in player_drops:
                    add_inventory(
                        conn,
                        user["id"],
                        item,
                        "battle"
                    )

            # При ничьей возвращаем ставку.
            elif result == "draw":
                balance += stake

            conn.execute("""
                UPDATE users
                SET balance = ?
                WHERE telegram_id = ?
            """, (balance, user["id"]))

        conn.execute("""
            INSERT INTO battles
            (telegram_id, result, player_total, bot_total, stake, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user["id"],
            result,
            player_total,
            bot_total,
            stake,
            datetime.now(timezone.utc).isoformat()
        ))

    return {
        "demo": payload.demo,
        "result": result,
        "player_drops": player_drops,
        "opponent_drops": bot_drops,
        "player_total": player_total,
        "opponent_total": bot_total,
        "pot": stake * 2,
        "balance": balance,
        "team_size": payload.team_size,
        "note": "Соперник в этой версии — бот."
    }


# --------------------------------------------------
# ПРОДАЖА ПРЕДМЕТОВ ИЗ ИНВЕНТАРЯ
# --------------------------------------------------

class SellRequest(BaseModel):
    inventory_id: int


@app.post("/api/inventory/sell")
async def sell_item(
    payload: SellRequest,
    x_telegram_init_data: str = Header(default="")
):
    user = validate_init_data(x_telegram_init_data)

    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")

        item = conn.execute("""
            SELECT *
            FROM player_inventory
            WHERE id = ? AND telegram_id = ?
        """, (
            payload.inventory_id,
            user["id"]
        )).fetchone()

        if not item:
            raise HTTPException(
                404,
                "Предмет не найден."
            )

        # Продажа за 80% условной стоимости предмета.
        payout = max(
            1,
            int(item["value"] * 0.8)
        )

        conn.execute("""
            DELETE FROM player_inventory
            WHERE id = ? AND telegram_id = ?
        """, (
            payload.inventory_id,
            user["id"]
        ))

        conn.execute("""
            UPDATE users
            SET balance = balance + ?
            WHERE telegram_id = ?
        """, (
            payout,
            user["id"]
        ))

        balance = conn.execute("""
            SELECT balance
            FROM users
            WHERE telegram_id = ?
        """, (user["id"],)).fetchone()["balance"]

    return {
        "sold": item["item_name"],
        "payout": payout,
        "balance": balance
    }


# --------------------------------------------------
# ЗАПУСК СЕРВЕРА
# --------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    if not BOT_TOKEN:
        raise SystemExit(
            "Укажите BOT_TOKEN в переменных окружения."
        )

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000"))
    )


# Статические файлы подключаем в самом конце,
# чтобы они не перехватывали API-запросы.
app.mount(
    "/",
    StaticFiles(directory=FRONTEND, html=True),
    name="frontend"
)
