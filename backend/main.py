import asyncio
import hashlib
import hmac
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qsl

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import WebAppInfo, MenuButtonWebApp
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
DB_PATH = Path(os.getenv("DB_PATH", str(ROOT / "data" / "cs2rewards.sqlite3")))
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip().rstrip("/")
BONUS_AMOUNT = 100
BONUS_HOURS = 24

CATALOG = [
    {"id": 1, "name": "AK-47 | Redline", "type": "Винтовка", "category": "rifles", "price": 300, "icon": "🔫", "rarity": "CLASSIFIED"},
    {"id": 2, "name": "AWP | Asiimov", "type": "Снайперская винтовка", "category": "snipers", "price": 500, "icon": "🎯", "rarity": "COVERT"},
    {"id": 3, "name": "M4A4 | Neo-Noir", "type": "Винтовка", "category": "rifles", "price": 400, "icon": "🔫", "rarity": "COVERT"},
    {"id": 4, "name": "Glock-18 | Fade", "type": "Пистолет", "category": "pistols", "price": 200, "icon": "🔫", "rarity": "RESTRICTED"},
    {"id": 5, "name": "AWP | Dragon Lore", "type": "Снайперская винтовка", "category": "snipers", "price": 1000, "icon": "🐉", "rarity": "COVERT"},
    {"id": 6, "name": "Karambit | Fade", "type": "Нож", "category": "knives", "price": 1500, "icon": "🔪", "rarity": "COVERT"},
]

app = FastAPI(title="CS2 Rewards API")
bot = Bot(BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher()


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
        conn.execute("CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY, first_name TEXT NOT NULL, balance INTEGER NOT NULL DEFAULT 0, last_bonus REAL)")
        conn.execute("CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER NOT NULL, item_id INTEGER NOT NULL, item_name TEXT NOT NULL, item_type TEXT NOT NULL, item_category TEXT NOT NULL, price INTEGER NOT NULL, purchased_at TEXT NOT NULL)")


def validate_init_data(init_data: str) -> dict:
    if not BOT_TOKEN:
        raise HTTPException(503, "Бот ещё не настроен: добавьте BOT_TOKEN в переменные окружения.")
    if not init_data:
        raise HTTPException(401, "Откройте Mini App через Telegram.")
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(401, "Не удалось проверить авторизацию Telegram.")
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(401, "Недействительные данные авторизации Telegram.")
    auth_date = int(parsed.get("auth_date", "0"))
    if time.time() - auth_date > 86400 or auth_date > time.time() + 60:
        raise HTTPException(401, "Сессия Telegram устарела. Закройте и снова откройте приложение.")
    try:
        user = json.loads(parsed["user"])
        telegram_id = int(user["id"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(401, "Не удалось прочитать профиль Telegram.")
    return {"id": telegram_id, "first_name": str(user.get("first_name", "Player"))[:64]}


def current_user(x_telegram_init_data: str = Header(default="")):
    return validate_init_data(x_telegram_init_data)


def ensure_user(user):
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO users (telegram_id, first_name, balance) VALUES (?, ?, 0)", (user["id"], user["first_name"]))
        conn.execute("UPDATE users SET first_name=? WHERE telegram_id=?", (user["first_name"], user["id"]))
        row = conn.execute("SELECT * FROM users WHERE telegram_id=?", (user["id"],)).fetchone()
    return row


def inventory_for(telegram_id):
    with db() as conn:
        rows = conn.execute("SELECT item_id AS id, item_name AS name, item_type AS type, item_category AS category, price, purchased_at FROM inventory WHERE telegram_id=? ORDER BY id DESC", (telegram_id,)).fetchall()
    return [dict(row) for row in rows]


@dp.message(CommandStart())
async def start_handler(message: types.Message):
    if not WEBAPP_URL:
        await message.answer("Бот создан, но Mini App ещё не опубликовано. Сначала задайте WEBAPP_URL.")
        return
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="Открыть CS2 Rewards", web_app=WebAppInfo(url=WEBAPP_URL))]],
        resize_keyboard=True,
    )
    await message.answer("Добро пожаловать в CS2 Rewards! Открой мини-приложение кнопкой ниже.", reply_markup=keyboard)
    await bot.set_chat_menu_button(chat_id=message.chat.id, menu_button=MenuButtonWebApp(text="CS2 Rewards", web_app=WebAppInfo(url=WEBAPP_URL)))


@app.on_event("startup")
async def startup():
    init_db()
    if bot:
        asyncio.create_task(dp.start_polling(bot))


@app.on_event("shutdown")
async def shutdown():
    if bot:
        await bot.session.close()


@app.get("/")
async def index():
    return FileResponse(FRONTEND / "index.html")



@app.get("/api/shop")
async def shop(x_telegram_init_data: str = Header(default="")):
    validate_init_data(x_telegram_init_data)
    return {"items": CATALOG}


@app.get("/api/me")
async def me(x_telegram_init_data: str = Header(default="")):
    user = validate_init_data(x_telegram_init_data)
    row = ensure_user(user)
    last_bonus = row["last_bonus"]
    next_bonus = datetime.fromtimestamp(last_bonus, timezone.utc) + timedelta(hours=BONUS_HOURS) if last_bonus else None
    return {
        "user": {"id": user["id"], "first_name": user["first_name"]},
        "balance": row["balance"],
        "next_bonus_at": next_bonus.isoformat() if next_bonus else None,
        "inventory": inventory_for(user["id"]),
    }


@app.post("/api/bonus")
async def claim_bonus(x_telegram_init_data: str = Header(default="")):
    user = validate_init_data(x_telegram_init_data)
    now = time.time()
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT OR IGNORE INTO users (telegram_id, first_name, balance) VALUES (?, ?, 0)", (user["id"], user["first_name"]))
        row = conn.execute("SELECT balance, last_bonus FROM users WHERE telegram_id=?", (user["id"],)).fetchone()
        if row["last_bonus"] and now - row["last_bonus"] < BONUS_HOURS * 3600:
            next_at = datetime.fromtimestamp(row["last_bonus"] + BONUS_HOURS * 3600, timezone.utc).isoformat()
            raise HTTPException(429, f"Бонус уже получен. Следующий будет доступен: {next_at}")
        new_balance = row["balance"] + BONUS_AMOUNT
        conn.execute("UPDATE users SET balance=?, last_bonus=? WHERE telegram_id=?", (new_balance, now, user["id"]))
    next_at = datetime.fromtimestamp(now + BONUS_HOURS * 3600, timezone.utc).isoformat()
    return {"awarded": BONUS_AMOUNT, "balance": new_balance, "next_bonus_at": next_at}


class BuyRequest(BaseModel):
    item_id: int


@app.post("/api/buy")
async def buy_item(payload: BuyRequest, x_telegram_init_data: str = Header(default="")):
    user = validate_init_data(x_telegram_init_data)
    item = next((item for item in CATALOG if item["id"] == payload.item_id), None)
    if not item:
        raise HTTPException(404, "Предмет не найден.")
    with db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("INSERT OR IGNORE INTO users (telegram_id, first_name, balance) VALUES (?, ?, 0)", (user["id"], user["first_name"]))
        row = conn.execute("SELECT balance FROM users WHERE telegram_id=?", (user["id"],)).fetchone()
        if row["balance"] < item["price"]:
            raise HTTPException(400, "Недостаточно монет для покупки.")
        new_balance = row["balance"] - item["price"]
        conn.execute("UPDATE users SET balance=? WHERE telegram_id=?", (new_balance, user["id"]))
        conn.execute("INSERT INTO inventory (telegram_id, item_id, item_name, item_type, item_category, price, purchased_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (user["id"], item["id"], item["name"], item["type"], item["category"], item["price"], datetime.now(timezone.utc).isoformat()))
    return {"balance": new_balance, "item_name": item["name"], "message": "Демо-покупка добавлена в инвентарь проекта."}


if __name__ == "__main__":
    import uvicorn
    if not BOT_TOKEN:
        raise SystemExit("Укажите BOT_TOKEN в переменных окружения перед запуском.")
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

# Serve frontend files after API routes so /api/* is not shadowed.
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
