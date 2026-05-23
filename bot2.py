import telebot
import sqlite3
import json
from datetime import datetime
import os
from flask import Flask, request
import threading

# === ТОКЕН ===
TOKEN = "8929942084:AAH6B35zStNKF920JGIxCugIbSafdSzcMqM"  # Обязательно замените!
ADMIN_CHAT_ID = 8929942084

bot = telebot.TeleBot(TOKEN)
user_carts = {}

# Flask приложение для Render
app = Flask(__name__)


# === БАЗА ДАННЫХ ===
def init_db():
    conn = sqlite3.connect('cosmetic.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT,
        category TEXT,
        price INTEGER,
        description TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT,
        user_id INTEGER,
        user_name TEXT,
        phone TEXT,
        address TEXT,
        items TEXT,
        total INTEGER,
        status TEXT,
        date TEXT
    )''')

    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        products = [
            (1, '💧 Увлажняющая сыворотка', 'Уход', 1890, 'Глубокое увлажнение с гиалуроновой кислотой'),
            (2, '🌸 Тоник для лица', 'Уход', 890, 'Мягкое очищение и тонизирование'),
            (3, '🎨 BB-крем SPF 30', 'Декоративная', 1590, 'Легкое покрытие с защитой от солнца'),
            (4, '🍬 Скраб для тела', 'Уход', 750, 'Мягкое отшелушивание'),
            (5, '✨ Маска для волос', 'Волосы', 1250, 'Восстановление и блеск'),
            (6, '💄 Помада матовая', 'Декоративная', 990, 'Стойкая матовая помада'),
        ]
        for p in products:
            c.execute("INSERT INTO products (id, name, category, price, description) VALUES (?,?,?,?,?)", p)

    conn.commit()
    conn.close()
    print("✅ База данных готова")


def get_products():
    conn = sqlite3.connect('cosmetic.db')
    conn.row_factory = sqlite3.Row
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return products


def get_product_by_id(pid):
    conn = sqlite3.connect('cosmetic.db')
    conn.row_factory = sqlite3.Row
    product = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    conn.close()
    return product


def save_order(user_id, user_name, phone, address, cart, total):
    conn = sqlite3.connect('cosmetic.db')
    c = conn.cursor()
    order_num = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}"
    items_json = json.dumps(cart, ensure_ascii=False)
    c.execute('''INSERT INTO orders (order_number, user_id, user_name, phone, address, items, total, status, date) 
                 VALUES (?,?,?,?,?,?,?,?,?)''',
              (order_num, user_id, user_name, phone, address, items_json, total, 'new',
               datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    return order_num


# === КЛАВИАТУРЫ И ОБРАБОТЧИКИ ===
def main_menu():
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=2)
    btn_catalog = telebot.types.InlineKeyboardButton("🛍️ Каталог", callback_data="catalog")
    btn_cart = telebot.types.InlineKeyboardButton("🛒 Корзина", callback_data="cart")
    btn_contacts = telebot.types.InlineKeyboardButton("📞 Контакты", callback_data="contacts")
    btn_help = telebot.types.InlineKeyboardButton("❓ Помощь", callback_data="help")
    keyboard.add(btn_catalog, btn_cart, btn_contacts, btn_help)
    return keyboard


def catalog_menu():
    products = get_products()
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    for p in products:
        keyboard.add(
            telebot.types.InlineKeyboardButton(f"{p['name']} - {p['price']}₽", callback_data=f"product_{p['id']}"))
    keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад", callback_data="back"))
    return keyboard


def product_detail_menu(product_id):
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(telebot.types.InlineKeyboardButton("➕ Добавить в корзину", callback_data=f"add_{product_id}"))
    keyboard.add(telebot.types.InlineKeyboardButton("🔙 Назад в каталог", callback_data="catalog"))
    return keyboard


def cart_menu():
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(telebot.types.InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout"))
    keyboard.add(telebot.types.InlineKeyboardButton("🗑️ Очистить корзину", callback_data="clear_cart"))
    keyboard.add(telebot.types.InlineKeyboardButton("🔙 В главное меню", callback_data="back"))
    return keyboard


@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.chat.id
    user_carts[user_id] = {}
    welcome = f"✨ Добро пожаловать в *Cosmetic Shop*, {message.from_user.first_name}! ✨\n\n🛍️ *Что вы можете сделать:*\n• Посмотреть каталог товаров\n• Добавить понравившееся в корзину\n• Оформить заказ"
    bot.send_message(user_id, welcome, parse_mode="Markdown", reply_markup=main_menu())


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.message.chat.id
    data = call.data

    if data == "back":
        bot.edit_message_text("Главное меню:", user_id, call.message.message_id, reply_markup=main_menu())
    elif data == "catalog":
        bot.edit_message_text("📋 *Наш каталог:*", user_id, call.message.message_id, parse_mode="Markdown",
                              reply_markup=catalog_menu())
    elif data == "cart":
        cart = user_carts.get(user_id, {})
        if not cart:
            bot.edit_message_text("🛒 *Корзина пуста*", user_id, call.message.message_id, parse_mode="Markdown",
                                  reply_markup=main_menu())
            return
        text = "🛒 *Ваша корзина:*\n\n"
        total = 0
        for pid, qty in cart.items():
            product = get_product_by_id(int(pid))
            if product:
                subtotal = product['price'] * qty
                total += subtotal
                text += f"• {product['name']}\n  {product['price']}₽ x {qty} = {subtotal}₽\n\n"
        text += f"💰 *Итого: {total}₽*"
        bot.edit_message_text(text, user_id, call.message.message_id, parse_mode="Markdown", reply_markup=cart_menu())
    elif data == "checkout":
        cart = user_carts.get(user_id, {})
        if not cart:
            bot.answer_callback_query(call.id, "Корзина пуста!")
            return
        user_carts[user_id]['_temp_cart'] = cart.copy()
        msg = bot.send_message(user_id, "📝 *Оформление заказа*\n\nВведите ваше имя:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_name)
    elif data == "clear_cart":
        user_carts[user_id] = {}
        bot.edit_message_text("🗑️ Корзина очищена!", user_id, call.message.message_id, reply_markup=main_menu())
    elif data == "contacts":
        text = "📞 *Контакты:*\n\n🌐 Сайт: cosmetic-shop.ru\n📧 Email: shop@cosmetic.ru"
        bot.edit_message_text(text, user_id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu())
    elif data == "help":
        text = "❓ *Помощь*\n\nВыберите товар → Добавьте в корзину → Оформите заказ"
        bot.edit_message_text(text, user_id, call.message.message_id, parse_mode="Markdown", reply_markup=main_menu())
    elif data.startswith("product_"):
        pid = int(data.split("_")[1])
        product = get_product_by_id(pid)
        if product:
            text = f"*{product['name']}*\n\n📖 {product['description']}\n\n💰 Цена: {product['price']}₽\n📁 Категория: {product['category']}"
            bot.edit_message_text(text, user_id, call.message.message_id, parse_mode="Markdown",
                                  reply_markup=product_detail_menu(pid))
    elif data.startswith("add_"):
        pid = int(data.split("_")[1])
        product = get_product_by_id(pid)
        if user_id not in user_carts:
            user_carts[user_id] = {}
        cart = user_carts[user_id]
        cart[str(pid)] = cart.get(str(pid), 0) + 1
        bot.answer_callback_query(call.id, f"✅ {product['name']} добавлен в корзину!")
        text = f"*{product['name']}*\n\n✅ Добавлено в корзину!"
        bot.edit_message_text(text, user_id, call.message.message_id, parse_mode="Markdown",
                              reply_markup=product_detail_menu(pid))


def process_name(message):
    user_id = message.chat.id
    user_carts[user_id]['_temp_name'] = message.text
    msg = bot.send_message(user_id, "📞 Введите ваш номер телефона:")
    bot.register_next_step_handler(msg, process_phone)


def process_phone(message):
    user_id = message.chat.id
    user_carts[user_id]['_temp_phone'] = message.text
    msg = bot.send_message(user_id, "📍 Введите адрес доставки:")
    bot.register_next_step_handler(msg, process_address)


def process_address(message):
    user_id = message.chat.id
    name = user_carts[user_id].pop('_temp_name')
    phone = user_carts[user_id].pop('_temp_phone')
    address = message.text
    cart = user_carts[user_id].pop('_temp_cart', {})
    items_list = []
    total = 0
    for pid, qty in cart.items():
        product = get_product_by_id(int(pid))
        if product:
            items_list.append({'name': product['name'], 'quantity': qty, 'price': product['price']})
            total += product['price'] * qty
    order_num = save_order(user_id, name, phone, address, items_list, total)
    user_carts[user_id] = {}
    bot.send_message(user_id, f"✅ *Заказ #{order_num} оформлен!*\n\nСумма: {total}₽\n\nСпасибо за покупку! 💖",
                     parse_mode="Markdown", reply_markup=main_menu())
    admin_text = f"🛍️ *НОВЫЙ ЗАКАЗ!*\n\n📦 Номер: {order_num}\n👤 Клиент: {name}\n📞 Телефон: {phone}\n📍 Адрес: {address}\n💰 Сумма: {total}₽"
    bot.send_message(ADMIN_CHAT_ID, admin_text, parse_mode="Markdown")


# Функция для запуска бота в отдельном потоке
def run_bot():
    bot.infinity_polling()


# Flask маршруты для Render
@app.route('/')
def home():
    return "Bot is running!"


@app.route('/health')
def health():
    return "OK", 200


# === ЗАПУСК ===
if __name__ == "__main__":
    init_db()

    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()

    # Запускаем Flask сервер для Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)