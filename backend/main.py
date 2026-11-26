
import asyncio
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time

from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qsl, parse_qs, urlparse

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import WebAppInfo, MenuButtonWebApp

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"

DB_PATH = Path(
    os.getenv(
        "DB_PATH",
        str(ROOT / "data" / "cs2rewards.sqlite3")
    )
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")

BONUS_AMOUNT = 100
BONUS_HOURS = 24


# Магазин
CATALOG = [
    {
        "id": 1,
        "name": "AK-47 | Redline",
        "type": "Винтовка",
        "category": "rifles",
        "price": 300,
        "icon": "🔫",
        "rarity": "CLASSIFIED"
    },
    {
        "id": 2,
        "name": "AWP | Asiimov",
        "type": "Снайперская винтовка",
        "category": "snipers",
        "price": 500,
        "icon": "🎯",
        "rarity": "COVERT"
    },
    {
        "id": 3,
        "name": "M4A4 | Neo-Noir",
        "type": "Винтовка",
        "category": "rifles",
        "price": 400,
        "icon": "🔫",
        "rarity": "COVERT"
    },
    {
        "id": 4,
        "name": "Glock-18 | Fade",
        "type": "Пистолет",
        "category": "pistols",
        "price": 200,
        "icon": "🔫",
        "rarity": "RESTRICTED"
    },
    {
        "id": 5,
        "name": "AWP | Dragon Lore",
        "type": "Снайперская винтовка",
        "category": "snipers",
        "price": 1000,
        "icon": "🐉",
        "rarity": "COVERT"
    },
    {
        "id": 6,
        "name": "Karambit | Fade",
        "type": "Нож",
        "category": "knives",
        "price": 1500,
        "icon": "🔪",
        "rarity": "COVERT"
    },
]


# Кейсы и вероятности выпадения.
# Стоимость предметов условная, это не реальные цены Steam.
CASES = [
    {
        "id": "rookie",
        "name": "Rookie Case",
        "price": 100,
        "icon": "📦",
        "drops": [
            {
                "name": "Glock-18 | Candy",
                "type": "Пистолет",
                "icon": "🔫",
                "rarity": "MIL-SPEC",
                "value": 35,
                "weight": 55
            },
            {
                "name": "MP9 | Sand",
                "type": "ПП",
                "icon": "🔫",
                "rarity": "RESTRICTED",
                "value": 80,
                "weight": 28
            },
            {
                "name": "AK-47 | Ember",
                "type": "Винтовка",
                "icon": "🔫",
                "rarity": "CLASSIFIED",
                "value": 180,
                "weight": 13
            },
            {
                "name": "★ Shadow Daggers",
                "type": "Нож",
                "icon": "🔪",
                "rarity": "COVERT",
                "value": 650,
                "weight": 4
            }
        ]
    },
    {
        "id": "pro",
        "name": "Pro Case",
        "price": 250,
        "icon": "🎯",
        "drops": [
            {
                "name": "P250 | Steel",
                "type": "Пистолет",
                "icon": "🔫",
                "rarity": "MIL-SPEC",
                "value": 90,
                "weight": 48
            },
            {
                "name": "M4A4 | Night",
                "type": "Винтовка",
                "icon": "🔫",
                "rarity": "RESTRICTED",
                "value": 210,
                "weight": 30
            },
            {
                "name": "AWP | Fever",
                "type": "Снайперская винтовка",
                "icon": "🎯",
                "rarity": "CLASSIFIED",
                "value": 500,
                "weight": 17
            },
            {
                "name": "★ Karambit | Neon",
                "type": "Нож",
                "icon": "🔪",
                "rarity": "COVERT",
                "value": 1800,
                "weight": 5
            }
        ]
    },
    {
        "id": "elite",
        "name": "Elite Case",
        "price": 500,
        "icon": "💎",
        "drops": [
            {
                "name": "USP-S | Carbon",
                "type": "Пистолет",
                "icon": "🔫",
                "rarity": "MIL-SPEC",
                "value": 160,
                "weight": 42
            },
            {
                "name": "AK-47 | Neon Rider",
                "type": "Винтовка",
                "icon": "🔫",
                "rarity": "RESTRICTED",
                "value": 420,
                "weight": 32
            },
            {
                "name": "AWP | Hyper Beast",
                "type": "Снайперская винтовка",
                "icon": "🎯",
                "rarity": "CLASSIFIED",
                "value": 950,
                "weight": 20
            },
            {
                "name": "★ Butterfly | Aurora",
                "type": "Нож",
                "icon": "🔪",
                "rarity": "COVERT",
                "value": 3500,
                "weight": 6
            }
        ]
    }
]


app = FastAPI(title="CS2 Rewards API")

bot = Bot(BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher()


# Работа с базой данных
@contextmanager
def db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=15)
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
                last_bonus REAL,
                created_at TEXT,
                last_seen TEXT,
                steam_trade_url TEXT
            )
        """)

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }

        migrations = {
            "created_at": "TEXT",
            "last_seen": "TEXT",
            "steam_trade_url": "TEXT"
        }

        for column, definition in migrations.items():
            if column not in columns:
                conn.execute(
                    f"ALTER TABLE users ADD COLUMN {column} {definition}"
                )

        conn.execute("""
            UPDATE users
            SET created_at = COALESCE(created_at, datetime('now'))
        """)

        conn.execute("""
            UPDATE users
            SET last_seen = COALESCE(last_seen, datetime('now'))
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                item_category TEXT NOT NULL,
                price INTEGER NOT NULL,
                purchased_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS game_inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                item_category TEXT NOT NULL,
                price INTEGER NOT NULL,
                purchased_at TEXT NOT NULL
            )
        """)


# Проверка авторизации Telegram
def validate_init_data(init_data: str) -> dict:

    if not BOT_TOKEN:
        raise HTTPException(
            503,
            "Бот ещё не настроен: добавьте BOT_TOKEN."
        )

    if not init_data:
        raise HTTPException(
            401,
            "Откройте Mini App через Telegram."
        )

    parsed = dict(
        parse_qsl(init_data, keep_blank_values=True)
    )

    received_hash = parsed.pop("hash", None)

    if not received_hash:
        raise HTTPException(
            401,
            "Не удалось проверить авторизацию Telegram."
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

    if not hmac.compare_digest(
        calculated_hash,
        received_hash
    ):
        raise HTTPException(
            401,
            "Недействительные данные авторизации Telegram."
        )

    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except ValueError:
        raise HTTPException(
            401,
            "Некорректная дата авторизации Telegram."
        )

    if time.time() - auth_date > 86400:
        raise HTTPException(
            401,
            "Сессия Telegram устарела. Перезапустите приложение."
        )

    try:
        user_data = json.loads(parsed["user"])
        telegram_id = int(user_data["id"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(
            401,
            "Не удалось прочитать профиль Telegram."
        )

    return {
        "id": telegram_id,
        "first_name": str(
            user_data.get("first_name", "Player")
        )[:64],
        "username": str(
            user_data.get("username", "")
        )[:64]
    }


def ensure_user(user):
    now = datetime.now(timezone.utc).isoformat()

    with db() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO users
            (telegram_id, first_name, balance, created_at, last_seen)
            VALUES (?, ?, 0, ?, ?)
        """, (
            user["id"],
            user["first_name"],
            now,
            now
        ))

        conn.execute("""
            UPDATE users
            SET first_name = ?, last_seen = ?
            WHERE telegram_id = ?
        """, (
            user["first_name"],
            now,
            user["id"]
        ))

        row = conn.execute("""
            SELECT * FROM users WHERE telegram_id = ?
        """, (user["id"],)).fetchone()

    return row


def inventory_for(telegram_id):

    with db() as conn:
        rows = conn.execute("""
            SELECT
                item_id AS id,
                item_name AS name,
                item_type AS type,
                item_category AS category,
                price,
                purchased_at
            FROM inventory
            WHERE telegram_id = ?
            ORDER BY id DESC
        """, (telegram_id,)).fetchall()

        game_rows = conn.execute("""
            SELECT
                id,
                item_name AS name,
                item_type AS type,
                item_category AS category,
                price,
                purchased_at
            FROM game_inventory
            WHERE telegram_id = ?
            ORDER BY id DESC
        """, (telegram_id,)).fetchall()

    result = [dict(row) for row in rows]

    for row in game_rows:
        item = dict(row)
        item["id"] = -item["id"]
        item["category"] = "game"
        result.append(item)

    return result


def save_game_item(telegram_id, item):
    with db() as conn:
        conn.execute("""
            INSERT INTO game_inventory
            (
                telegram_id,
                item_name,
                item_type,
                item_category,
                price,
                purchased_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            telegram_id,
            item["name"],
            item["type"],
            "game",
            item["value"],
            datetime.now(timezone.utc).isoformat()
        ))


# Выбор предмета из кейса
def choose_drop(case):

    total = sum(
        item["weight"]
        for item in case["drops"]
    )

    pick = secrets.randbelow(total)

    for item in case["drops"]:

        if pick < item["weight"]:
            return {
                key: value
                for key, value in item.items()
                if key != "weight"
            }

        pick -= item["weight"]

    return {
        key: value
        for key, value in case["drops"][-1].items()
        if key != "weight"
    }


def case_by_id(case_id):

    case = next(
        (item for item in CASES if item["id"] == case_id),
        None
    )

    if not case:
        raise HTTPException(404, "Кейс не найден.")

    return case


# Проверка Steam Trade URL
def validate_trade_url(value):

    value = (value or "").strip()

    if not value:
        return ""

    if len(value) > 500:
        raise HTTPException(
            400,
            "Ссылка слишком длинная."
        )

    parsed = urlparse(value)

    if (
        parsed.scheme != "https"
        or parsed.hostname not in (
            "steamcommunity.com",
            "www.steamcommunity.com"
        )
    ):
        raise HTTPException(
            400,
            "Нужна официальная HTTPS-ссылка Steam."
        )

    if parsed.path.rstrip("/") != "/tradeoffer/new":
        raise HTTPException(
            400,
            "Ссылка должна вести на /tradeoffer/new/."
        )

    query = parse_qs(parsed.query)

    partner = query.get("partner", [""])[0]
    token = query.get("token", [""])[0]

    if (
        not partner.isdigit()
        or not (5 <= len(token) <= 32)
        or not token.isalnum()
    ):
        raise HTTPException(
            400,
            "Проверьте параметры partner и token в ссылке."
        )

    return value


# Команды Telegram
@dp.message(Command("myid"))
async def myid_handler(message: types.Message):
    await message.answer(
        f"Твой Telegram ID: {message.from_user.id}"
    )


@dp.message(Command("stats"))
async def stats_handler(message: types.Message):

    if not ADMIN_ID:
        await message.answer(
            "Статистика ещё не настроена: добавьте ADMIN_ID в Render."
        )
        return

    if message.from_user.id != ADMIN_ID:
        await message.answer(
            "У тебя нет доступа к статистике."
        )
        return

    with db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]

        today = conn.execute("""
            SELECT COUNT(*) FROM users
            WHERE date(created_at) = date('now')
        """).fetchone()[0]

        active = conn.execute("""
            SELECT COUNT(*) FROM users
            WHERE julianday(last_seen) >= julianday('now', '-7 days')
        """).fetchone()[0]

    await message.answer(
        "📊 Статистика CS2 Rewards\n\n"
        f"👥 Всего пользователей: {total}\n"
        f"🆕 Новых сегодня: {today}\n"
        f"🔥 Активных за 7 дней: {active}"
    )


@dp.message(CommandStart())
async def start_handler(message: types.Message):

    ensure_user({
        "id": message.from_user.id,
        "first_name": message.from_user.first_name or "Player"
    })

    if not WEBAPP_URL:
        await message.answer(
            "Бот создан, но Mini App ещё не опубликовано. "
            "Сначала задайте WEBAPP_URL."
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
        "Добро пожаловать в CS2 Rewards! "
        "Открой мини-приложение кнопкой ниже.",
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


# Запуск приложения
@app.on_event("startup")
async def startup():
    init_db()

    if bot:
        asyncio.create_task(
            dp.start_polling(bot)
        )


@app.on_event("shutdown")
async def shutdown():
    if bot:
        await bot.session.close()


@app.get("/")
async def index():
    return FileResponse(
        FRONTEND / "index.html"
    )


# Магазин
@app.get("/api/shop")
async def shop(
    x_telegram_init_data: str = Header(default="")
):
    validate_init_data(x_telegram_init_data)

    return {
        "items": CATALOG
    }


# Профиль и информация пользователя
@app.get("/api/me")
async def me(
    x_telegram_init_data: str = Header(default="")
):

    user = validate_init_data(x_telegram_init_data)
    row = ensure_user(user)

    last_bonus = row["last_bonus"]

    next_bonus = (
        datetime.fromtimestamp(
            last_bonus,
            timezone.utc
        ) + timedelta(hours=BONUS_HOURS)
        if last_bonus else None
    )

    return {
        "user": {
            "id": user["id"],
            "first_name": user["first_name"],
            "username": user["username"]
        },
        "balance": row["balance"],
        "next_bonus_at": (
            next_bonus.isoformat()
            if next_bonus else None
        ),
        "inventory": inventory_for(user["id"]),
        "steam_trade_url": row["steam_trade_url"] or ""
    }


class ProfileRequest(BaseModel):
    steam_trade_url: str = Field(
        default="",
        max_length=500
    )


@app.put("/api/profile")
async def update_profile(
    payload: ProfileRequest,
    x_telegram_init_data: str = Header(default="")
):

    user = validate_init_data(x_telegram_init_data)

    safe_url = validate_trade_url(
        payload.steam_trade_url
    )

    ensure_user(user)

    with db() as conn:
        conn.execute("""
            UPDATE users
            SET steam_trade_url = ?
            WHERE telegram_id = ?
        """, (
            safe_url,
            user["id"]
        ))

    return {
        "saved": True,
        "steam_trade_url": safe_url
    }


# Ежедневный бонус
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
        """, (
            user["id"],
            user["first_name"]
        ))

        row = conn.execute("""
            SELECT balance, last_bonus
            FROM users
            WHERE telegram_id = ?
        """, (user["id"],)).fetchone()

        if (
            row["last_bonus"]
            and now - row["last_bonus"] < BONUS_HOURS * 3600
        ):
            next_at = datetime.fromtimestamp(
                row["last_bonus"] + BONUS_HOURS * 3600,
                timezone.utc
            ).isoformat()

            raise HTTPException(
                429,
                f"Бонус уже получен. Следующий будет доступен: {next_at}"
            )

        new_balance = row["balance"] + BONUS_AMOUNT

        conn.execute("""
            UPDATE users
            SET balance = ?, last_bonus = ?
            WHERE telegram_id = ?
        """, (
            new_balance,
            now,
            user["id"]
        ))

    next_at = datetime.fromtimestamp(
        now + BONUS_HOURS * 3600,
        timezone.utc
    ).isoformat()

    return {
        "awarded": BONUS_AMOUNT,
        "balance": new_balance,
        "next_bonus_at": next_at
    }


# Покупка предметов в магазине
class BuyRequest(BaseModel):
    item_id: int


@app.post("/api/buy")
async def buy_item(
    payload: BuyRequest,
    x_telegram_init_data: str = Header(default="")
):

    user = validate_init_data(x_telegram_init_data)

    item = next(
        (item for item in CATALOG if item["id"] == payload.item_id),
        None
    )

    if not item:
        raise HTTPException(
            404,
            "Предмет не найден."
        )

    with db() as conn:

        conn.execute("BEGIN IMMEDIATE")

        conn.execute("""
            INSERT OR IGNORE INTO users
            (telegram_id, first_name, balance)
            VALUES (?, ?, 0)
        """, (
            user["id"],
            user["first_name"]
        ))

        row = conn.execute("""
            SELECT balance FROM users
            WHERE telegram_id = ?
        """, (user["id"],)).fetchone()

        if row["balance"] < item["price"]:
            raise HTTPException(
                400,
                "Недостаточно монет для покупки."
            )

        new_balance = row["balance"] - item["price"]

        conn.execute("""
            UPDATE users
            SET balance = ?
            WHERE telegram_id = ?
        """, (
            new_balance,
            user["id"]
        ))

        conn.execute("""
            INSERT INTO inventory
            (
                telegram_id,
                item_id,
                item_name,
                item_type,
                item_category,
                price,
                purchased_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user["id"],
            item["id"],
            item["name"],
            item["type"],
            item["category"],
            item["price"],
            datetime.now(timezone.utc).isoformat()
        ))

    return {
        "balance": new_balance,
        "item_name": item["name"],
        "message": "Покупка добавлена в инвентарь проекта."
    }


# Список кейсов
@app.get("/api/cases")
async def get_cases(
    x_telegram_init_data: str = Header(default="")
):

    validate_init_data(x_telegram_init_data)

    return {
        "cases": [
            {
                "id": case["id"],
                "name": case["name"],
                "price": case["price"],
                "icon": case["icon"]
            }
            for case in CASES
        ]
    }


# Открытие кейса
class OpenCaseRequest(BaseModel):
    case_id: str
    demo: bool = False


@app.post("/api/game/open")
async def open_case(
    payload: OpenCaseRequest,
    x_telegram_init_data: str = Header(default="")
):

    user = validate_init_data(x_telegram_init_data)
    case = case_by_id(payload.case_id)

    ensure_user(user)

    drop = choose_drop(case)

    with db() as conn:

        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute("""
            SELECT balance FROM users
            WHERE telegram_id = ?
        """, (user["id"],)).fetchone()

        if not payload.demo:

            if row["balance"] < case["price"]:
                raise HTTPException(
                    400,
                    "Недостаточно монет для открытия этого кейса."
                )

            conn.execute("""
                UPDATE users
                SET balance = balance - ?
                WHERE telegram_id = ?
            """, (
                case["price"],
                user["id"]
            ))

            conn.execute("""
                INSERT INTO game_inventory
                (
                    telegram_id,
                    item_name,
                    item_type,
                    item_category,
                    price,
                    purchased_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user["id"],
                drop["name"],
                drop["type"],
                "game",
                drop["value"],
                datetime.now(timezone.utc).isoformat()
            ))

        balance = conn.execute("""
            SELECT balance FROM users
            WHERE telegram_id = ?
        """, (user["id"],)).fetchone()["balance"]

    return {
        "demo": payload.demo,
        "drop": drop,
        "balance": balance,
        "case": case["name"]
    }


# Case Battle против бота
class BattleRequest(BaseModel):
    case_id: str
    rounds: int = Field(default=3, ge=1, le=5)
    stake: int = Field(default=100, ge=50, le=5000)
    demo: bool = False


@app.post("/api/game/battle")
async def case_battle(
    payload: BattleRequest,
    x_telegram_init_data: str = Header(default="")
):

    user = validate_init_data(x_telegram_init_data)
    case = case_by_id(payload.case_id)

    ensure_user(user)

    # Сначала проверяем и списываем ставку игрока.
    if not payload.demo:

        with db() as conn:

            conn.execute("BEGIN IMMEDIATE")

            row = conn.execute("""
                SELECT balance FROM users
                WHERE telegram_id = ?
            """, (user["id"],)).fetchone()

            if row["balance"] < payload.stake:
                raise HTTPException(
                    400,
                    "Недостаточно монет для ставки."
                )

            conn.execute("""
                UPDATE users
                SET balance = balance - ?
                WHERE telegram_id = ?
            """, (
                payload.stake,
                user["id"]
            ))

    # Игрок и бот открывают одинаковое число кейсов.
    player_drops = [
        choose_drop(case)
        for _ in range(payload.rounds)
    ]

    bot_drops = [
        choose_drop(case)
        for _ in range(payload.rounds)
    ]

    player_total = sum(
        item["value"]
        for item in player_drops
    )

    bot_total = sum(
        item["value"]
        for item in bot_drops
    )

    if player_total > bot_total:
        result = "win"

        if not payload.demo:
            # Победитель забирает две ставки:
            # свою и виртуальную ставку бота.
            with db() as conn:
                conn.execute("""
                    UPDATE users
                    SET balance = balance + ?
                    WHERE telegram_id = ?
                """, (
                    payload.stake * 2,
                    user["id"]
                ))

    elif player_total < bot_total:
        result = "lose"

    else:
        result = "draw"

        if not payload.demo:
            # При ничьей возвращаем ставку игрока.
            with db() as conn:
                conn.execute("""
                    UPDATE users
                    SET balance = balance + ?
                    WHERE telegram_id = ?
                """, (
                    payload.stake,
                    user["id"]
                ))

    with db() as conn:
        balance = conn.execute("""
            SELECT balance FROM users
            WHERE telegram_id = ?
        """, (user["id"],)).fetchone()["balance"]

    return {
        "demo": payload.demo,
        "result": result,
        "player_drops": player_drops,
        "bot_drops": bot_drops,
        "player_total": player_total,
        "bot_total": bot_total,
        "pot": payload.stake * 2,
        "stake": payload.stake,
        "balance": balance
    }


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


# Подключение frontend
app.mount(
    "/",
    StaticFiles(directory=FRONTEND, html=True),
    name="frontend"
)
