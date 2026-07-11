import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import pymongo
import time
import threading
from flask import Flask

# ========== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URL = os.environ.get("MONGO_URL")
if not BOT_TOKEN or not MONGO_URL:
    raise ValueError("Задайте BOT_TOKEN и MONGO_URL в Render")

# ========== ПОДКЛЮЧЕНИЯ ==========
bot = telebot.TeleBot(BOT_TOKEN)
client = pymongo.MongoClient(MONGO_URL)
db = client["color_parcel"]
users_col = db["users"]
purchases_col = db["purchases"]

# ========== КОНФИГ ЦВЕТОВ ==========
COLORS = {
    "red":    {"name": "Красный", "emoji": "🔴", "price": 0.1,  "multiplier": 1.5, "time": 7200},
    "green":  {"name": "Зелёный", "emoji": "🟢", "price": 0.5,  "multiplier": 1.5, "time": 7200},
    "yellow": {"name": "Жёлтый", "emoji": "🟡", "price": 1.0,  "multiplier": 1.5, "time": 7200},
    "blue":   {"name": "Синий", "emoji": "🔵", "price": 3.0,  "multiplier": 1.5, "time": 7200},
    "white":  {"name": "Белый", "emoji": "⚪", "price": 5.0,  "multiplier": 1.5, "time": 7200},
    "black":  {"name": "Чёрный", "emoji": "⚫", "price": 10.0, "multiplier": 1.5, "time": 7200},
    "purple": {"name": "Фиолетовый", "emoji": "🟣", "price": 20.0, "multiplier": 1.5, "time": 7200},
    "orange": {"name": "Оранжевый", "emoji": "🟠", "price": 40.0, "multiplier": 1.5, "time": 7200}
}

# ========== ФУНКЦИИ БД ==========
def get_user(user_id):
    user = users_col.find_one({"_id": user_id})
    if not user:
        user = {
            "_id": user_id,
            "balance": 0.0,
            "auto_reinvest": False,
            "lang": "ru",
            "referrer": None,
            "referrals": []
        }
        users_col.insert_one(user)
    return user

def update_user(user_id, data):
    users_col.update_one({"_id": user_id}, {"$set": data})

def get_purchases(user_id):
    return list(purchases_col.find({"user_id": user_id}))

def add_purchase(user_id, color_key, quantity):
    color = COLORS[color_key]
    now = int(time.time())
    end_time = now + color["time"]
    for _ in range(quantity):
        purchases_col.insert_one({
            "user_id": user_id,
            "color": color_key,
            "price": color["price"],
            "multiplier": color["multiplier"],
            "buy_date": now,
            "end_date": end_time,
            "collected": False
        })

# ========== /START ==========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    get_user(user_id)
    text = (
        f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
        "🎨 **Color Parcel** — покупай цвета, жди и получай прибыль в TON.\n"
        "Выбери действие:"
    )
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🪞 Моя станция", callback_data="station"),
        InlineKeyboardButton("🛒 Магазин", callback_data="shop"),
        InlineKeyboardButton("📋 Задания", callback_data="tasks"),
        InlineKeyboardButton("👥 Друзья", callback_data="friends"),
        InlineKeyboardButton("👛 Кошелек", callback_data="wallet"),
        InlineKeyboardButton("🏆 Рейтинг", callback_data="rating"),
        InlineKeyboardButton("🌍 Язык", callback_data="lang"),
        InlineKeyboardButton("ℹ️ Информация", callback_data="info")
    )
    bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode="Markdown")

# ========== CALLBACK ==========
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data

    if data == "station":
        bot.answer_callback_query(call.id, "🪞 Открываю станцию...")
        show_station(call.message)
    elif data == "shop":
        bot.answer_callback_query(call.id, "🛒 Загружаю магазин...")
        show_shop(call.message)
    elif data == "tasks":
        bot.answer_callback_query(call.id, "📋 Список заданий")
        bot.send_message(call.message.chat.id, "📋 Задания будут здесь (в разработке).")
    elif data == "friends":
        bot.answer_callback_query(call.id, "👥 Реферальная система")
        bot.send_message(call.message.chat.id, "👥 Рефералка появится позже.")
    elif data == "wallet":
        bot.answer_callback_query(call.id, "👛 Кошелёк")
        bot.send_message(call.message.chat.id, "👛 Кошелёк в разработке.")
    elif data == "rating":
        bot.answer_callback_query(call.id, "🏆 Топ игроков")
        bot.send_message(call.message.chat.id, "🏆 Рейтинг будет позже.")
    elif data == "lang":
        bot.answer_callback_query(call.id, "🌍 Выбор языка")
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang_ru"),
            InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")
        )
        bot.send_message(call.message.chat.id, "Выбери язык:", reply_markup=keyboard)
    elif data.startswith("set_lang_"):
        lang = data.split("_")[-1]
        update_user(user_id, {"lang": lang})
        bot.answer_callback_query(call.id, f"Язык изменён на {lang}")
        bot.edit_message_text("Язык обновлён. Нажми /start для перезапуска.", call.message.chat.id, call.message.message_id)
    elif data == "back_to_menu":
        bot.answer_callback_query(call.id, "🔙 Возврат в меню")
        start(call.message)
    elif data.startswith("buy_"):
        parts = data.split("_")
        if len(parts) != 3:
            bot.answer_callback_query(call.id, "❌ Ошибка в данных")
            return
        color_key = parts[1]
        quantity = int(parts[2])
        if color_key not in COLORS:
            bot.answer_callback_query(call.id, "❌ Такого цвета нет")
            return
        color = COLORS[color_key]
        total_price = color["price"] * quantity
        user = get_user(user_id)
        if user["balance"] < total_price:
            bot.answer_callback_query(call.id, f"❌ Не хватает TON! Нужно {total_price:.2f}")
            return
        update_user(user_id, {"balance": user["balance"] - total_price})
        add_purchase(user_id, color_key, quantity)
        bot.answer_callback_query(call.id, f"✅ Куплено {quantity} шт. {color['name']}!")
        bot.send_message(call.message.chat.id, f"Ты купил {quantity} цветов {color['name']}!\nОжидай {color['time']//3600} ч.")
        show_station(call.message)
    elif data == "collect_profit":
        collect_profit(call)
    elif data == "toggle_auto":
        user = get_user(user_id)
        new_val = not user.get("auto_reinvest", False)
        update_user(user_id, {"auto_reinvest": new_val})
        status = "включён" if new_val else "выключен"
        bot.answer_callback_query(call.id, f"♻️ Авто-реинвест {status}")
        show_station(call.message)
    elif data == "history":
        bot.answer_callback_query(call.id, "📊 История")
        bot.send_message(call.message.chat.id, "📊 История операций появится позже.")
    else:
        bot.answer_callback_query(call.id, "❓ Неизвестная команда")

# ========== МАГАЗИН ==========
def show_shop(message):
    text = "🛒 **Магазин цветов**\n\nВыбери цвет для покупки:\n"
    for key, c in COLORS.items():
        income = c["price"] * c["multiplier"]
        text += f"{c['emoji']} **{c['name']}**\n"
        text += f"   Цена: {c['price']} TON | Доход: {income} TON | Время: {c['time']//3600} ч\n\n"
    
    keyboard = InlineKeyboardMarkup(row_width=3)
    for key, c in COLORS.items():
        buttons = [
            InlineKeyboardButton(f"{c['emoji']} 1", callback_data=f"buy_{key}_1"),
            InlineKeyboardButton(f"{c['emoji']} 5", callback_data=f"buy_{key}_5"),
            InlineKeyboardButton(f"{c['emoji']} 10", callback_data=f"buy_{key}_10")
        ]
        keyboard.add(*buttons)
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu"))
    bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode="Markdown")

# ========== СТАНЦИЯ ==========
def show_station(message):
    user_id = message.chat.id
    user = get_user(user_id)
    balance = user["balance"]
    purchases = get_purchases(user_id)
    now = int(time.time())
    active = []
    ready = []
    for p in purchases:
        if p.get("collected", False):
            continue
        if p["end_date"] <= now:
            ready.append(p)
        else:
            active.append(p)
    
    expected_profit = 0.0
    for p in purchases:
        if not p.get("collected", False):
            expected_profit += p["price"] * p["multiplier"]
    
    auto = user.get("auto_reinvest", False)
    auto_status = "✅ Включен" if auto else "❌ Выключен"
    
    text = (
        f"🪞 **Моя станция**\n\n"
        f"💰 Баланс: {balance:.3f} TON\n"
        f"📬 Цветов в пути: {len(active)}\n"
        f"💸 Ожидаемая прибыль: {expected_profit:.3f} TON\n"
        f"♻️ Авто-реинвест: {auto_status}\n"
        "\n"
    )
    if active:
        text += "🔄 **В процессе:**\n"
        for p in active:
            remaining = p["end_date"] - now
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            text += f"{p['color']} ⏳ Осталось {hours}ч {minutes}м\n"
    else:
        text += "🔄 Нет цветов в пути.\n"
    
    if ready:
        text += "\n✅ **Готовы к сбору:**\n"
        for p in ready:
            text += f"{p['color']} ✅ Готова\n"
    else:
        text += "\n✅ Нет готовых.\n"
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("💰 Собрать прибыль", callback_data="collect_profit"),
        InlineKeyboardButton(f"♻️ Авто-реинвест {'Выкл' if auto else 'Вкл'}", callback_data="toggle_auto"),
        InlineKeyboardButton("📊 История", callback_data="history"),
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
    )
    bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode="Markdown")

# ========== СБОР ПРИБЫЛИ ==========
def collect_profit(call):
    user_id = call.from_user.id
    purchases = get_purchases(user_id)
    now = int(time.time())
    total_profit = 0.0
    any_collected = False
    user = get_user(user_id)
    auto = user.get("auto_reinvest", False)
    new_purchases = []
    
    for p in purchases:
        if p.get("collected", False):
            continue
        if p["end_date"] <= now:
            profit = p["price"] * p["multiplier"]
            total_profit += profit
            any_collected = True
            if auto:
                new_purchases.append({
                    "user_id": user_id,
                    "color": p["color"],
                    "price": p["price"],
                    "multiplier": p["multiplier"],
                    "buy_date": now,
                    "end_date": now + (p["end_date"] - p["buy_date"]),
                    "collected": False
                })
            else:
                update_user(user_id, {"balance": user["balance"] + profit})
            purchases_col.update_one({"_id": p["_id"]}, {"$set": {"collected": True}})
        else:
            pass
    
    if not any_collected:
        bot.answer_callback_query(call.id, "❌ Нет готовых цветов для сбора.")
        return
    
    for np in new_purchases:
        purchases_col.insert_one(np)
    
    msg = f"💰 Собрано {total_profit:.3f} TON"
    if auto:
        msg += " (авто-реинвест включён, прибыль реинвестирована)"
    bot.answer_callback_query(call.id, msg)
    show_station(call.message)

# ========== FLASK ДЛЯ RENDER ==========
app = Flask(__name__)

@app.route('/')
def health():
    return "OK"

def run_bot():
    bot.polling(none_stop=True)

if __name__ == "__main__":
    thread = threading.Thread(target=run_bot)
    thread.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)