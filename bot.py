import os
import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import qrcode
from io import BytesIO
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise ValueError("Не найден API_TOKEN. Добавь его в Render Environment Variables.")

# Настройки администратора
ADMIN_USERNAME = "@paymentprosu"
ADMIN_IDS = [123456789]  # Замени на свой ID Telegram

# Способы оплаты
PAYMENT_METHODS = [
    {
        "id": "sber",
        "name": "Сбербанк",
        "details": "Номер карты: 1234 5678 9012 3456\nПолучатель: Иван Иванов"
    },
    {
        "id": "tbank", 
        "name": "Т-Банк",
        "details": "Номер карты: 2345 6789 0123 4567\nПолучатель: Петр Петров"
    },
    {
        "id": "alpha",
        "name": "Альфа-Банк",
        "details": "Номер карты: 3456 7890 1234 5678\nПолучатель: Сергей Сергеев"
    },
    {
        "id": "mts",
        "name": "МТС Банк", 
        "details": "Номер карты: 4567 8901 2345 6789\nПолучатель: Андрей Андреев"
    },
    {
        "id": "ozon",
        "name": "Ozon Bank",
        "details": "Номер карты: 5678 9012 3456 7890\nПолучатель: Дмитрий Дмитриев"
    },
    {
        "id": "nspk",
        "name": "QR НСПК",
        "details": "Оплата по QR-коду через СБП"
    }
]

# Данные организации для НСПК
NSPK_ORGANIZATION = {
    "name": "ООО 'Ваша организация'",
    "inn": "1234567890",
    "bank": "ПАО 'Сбербанк'"
}

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Состояния для FSM
class OrderStates(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_payment = State()

class ManualOrderStates(StatesGroup):
    waiting_for_product = State()
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_payment = State()
    waiting_for_customer = State()

# ========================
# Инициализация базы данных
# ========================
def init_db():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    
    # Таблица товаров
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            photo_url TEXT,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')
    
    # Таблица заказов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            product_id INTEGER,
            product_name TEXT,
            amount REAL,
            order_date TEXT NOT NULL,
            order_time TEXT NOT NULL,
            payment_method TEXT,
            payment_details TEXT,
            status TEXT DEFAULT 'pending',
            admin_confirmed BOOLEAN DEFAULT FALSE,
            admin_contact TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Добавляем тестовые товары если их нет
    cursor.execute('SELECT COUNT(*) FROM products')
    if cursor.fetchone()[0] == 0:
        products = [
            ("Веб-разработка", "Создание сайта под ключ", 1000, "https://via.placeholder.com/300x200.png?text=Веб-разработка"),
            ("Дизайн", "UI/UX дизайн интерфейса", 2000, "https://via.placeholder.com/300x200.png?text=Дизайн"),
            ("Консультация", "Техническая консультация 1 час", 3000, "https://via.placeholder.com/300x200.png?text=Консультация"),
            ("SEO", "Продвижение сайта в поиске", 4000, "https://via.placeholder.com/300x200.png?text=SEO"),
            ("Поддержка", "Техническая поддержка", 5000, "https://via.placeholder.com/300x200.png?text=Поддержка")
        ]
        cursor.executemany('INSERT INTO products (name, description, price, photo_url) VALUES (?, ?, ?, ?)', products)
    
    conn.commit()
    conn.close()

# ========================
# Функции работы с БД
# ========================
def get_products():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE is_active = TRUE')
    products = cursor.fetchall()
    conn.close()
    return products

def get_product(product_id):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()
    conn.close()
    return product

def create_order(user_id, username, product_id, product_name, amount, order_date, order_time, payment_method):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    
    payment_details = next((pm["details"] for pm in PAYMENT_METHODS if pm["name"] == payment_method), "")
    
    cursor.execute('''
        INSERT INTO orders (user_id, username, product_id, product_name, amount, 
                          order_date, order_time, payment_method, payment_details, admin_contact)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, product_id, product_name, amount, 
          order_date, order_time, payment_method, payment_details, ADMIN_USERNAME))
    
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id

def create_manual_order(product_name, amount, order_date, order_time, payment_method, customer_name):
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    
    payment_details = next((pm["details"] for pm in PAYMENT_METHODS if pm["name"] == payment_method), "")
    
    cursor.execute('''
        INSERT INTO orders (product_name, amount, order_date, order_time, 
                          payment_method, payment_details, username, admin_contact, admin_confirmed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, TRUE)
    ''', (product_name, amount, order_date, order_time, payment_method, 
          payment_details, customer_name, ADMIN_USERNAME))
    
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id

def get_orders():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders ORDER BY order_date DESC, order_time DESC')
    orders = cursor.fetchall()
    conn.close()
    return orders

# ========================
# Вспомогательные функции
# ========================
def validate_date(date_text):
    try:
        datetime.strptime(date_text, '%d.%m.%Y')
        return True
    except ValueError:
        return False

def validate_time(time_text):
    try:
        datetime.strptime(time_text, '%H:%M')
        return True
    except ValueError:
        return False

def generate_qr_code(text):
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    bio = BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# ========================
# 1. Команда /start
# ========================
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🛍️ Магазин", callback_data="shop"),
        InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders"),
        InlineKeyboardButton("📞 Контакты", callback_data="contacts"),
        InlineKeyboardButton("👨‍💼 Админ", callback_data="admin_panel")
    )
    
    await message.answer(
        f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
        "Выберите действие из меню ниже:",
        reply_markup=kb
    )

# ========================
# 2. Просмотр магазина
# ========================
@dp.callback_query_handler(lambda c: c.data == "shop")
async def show_shop(callback: types.CallbackQuery):
    products = get_products()
    
    kb = InlineKeyboardMarkup(row_width=1)
    for product in products:
        kb.add(InlineKeyboardButton(
            f"{product[1]} - {product[3]:,}₽", 
            callback_data=f"product_{product[0]}"
        ))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="main_menu"))
    
    await callback.message.edit_text(
        "🛍️ **Наш магазин услуг**\n\nВыберите услугу:",
        reply_markup=kb,
        parse_mode='Markdown'
    )

# ========================
# 3. Просмотр товара
# ========================
@dp.callback_query_handler(lambda c: c.data.startswith("product_"))
async def show_product(callback: types.CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    product = get_product(product_id)
    
    if not product:
        await callback.answer("Товар не найден")
        return
    
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("💰 Купить", callback_data=f"buy_{product_id}"))
    kb.add(InlineKeyboardButton("🔙 Назад", callback_data="shop"))
    
    await callback.message.delete()
    await bot.send_photo(
        callback.from_user.id,
        product[4],
        caption=f"🎁 **{product[1]}**\n\n📝 {product[2]}\n\n💵 **Цена: {product[3]:,}₽**",
        reply_markup=kb,
        parse_mode='Markdown'
    )

# ========================
# 4. Начало оформления заказа
# ========================
@dp.callback_query_handler(lambda c: c.data.startswith("buy_"))
async def start_order(callback: types.CallbackQuery, state: FSMContext):
    product_id = int(callback.data.split("_")[1])
    product = get_product(product_id)
    
    async with state.proxy() as data:
        data['product'] = product
        data['product_id'] = product_id
    
    await OrderStates.waiting_for_date.set()
    await callback.message.answer(
        f"🎁 Товар: **{product[1]}**\n💵 Сумма: **{product[3]:,}₽**\n\n"
        f"📅 Введите дату заказа в формате **ДД.ММ.ГГГГ**:\n"
        f"Пример: {datetime.now().strftime('%d.%m.%Y')}",
        parse_mode='Markdown'
    )

# ========================
# 5. Ввод даты заказа
# ========================
@dp.message_handler(state=OrderStates.waiting_for_date)
async def process_order_date(message: types.Message, state: FSMContext):
    if not validate_date(message.text):
        await message.answer("❌ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ:")
        return
    
    async with state.proxy() as data:
        data['order_date'] = message.text
    
    await OrderStates.next()
    await message.answer("⏰ Теперь введите время заказа в формате ЧЧ:ММ:\nПример: 14:30")

# ========================
# 6. Ввод времени заказа
# ========================
@dp.message_handler(state=OrderStates.waiting_for_time)
async def process_order_time(message: types.Message, state: FSMContext):
    if not validate_time(message.text):
        await message.answer("❌ Неверный формат времени. Введите в формате ЧЧ:ММ:")
        return
    
    async with state.proxy() as data:
        data['order_time'] = message.text
    
    # Показываем способы оплаты
    kb = InlineKeyboardMarkup(row_width=2)
    for payment in PAYMENT_METHODS:
        kb.add(InlineKeyboardButton(f"💳 {payment['name']}", callback_data=f"pay_{payment['id']}"))
    
    await OrderStates.next()
    await message.answer("💳 Выберите способ оплаты:", reply_markup=kb)

# ========================
# 7. Выбор способа оплаты
# ========================
@dp.callback_query_handler(lambda c: c.data.startswith("pay_"), state=OrderStates.waiting_for_payment)
async def process_payment(callback: types.CallbackQuery, state: FSMContext):
    payment_id = callback.data.split("_")[1]
    payment_method = next((pm for pm in PAYMENT_METHODS if pm["id"] == payment_id), None)
    
    async with state.proxy() as data:
        product = data['product']
        order_date = data['order_date']
        order_time = data['order_time']
    
    # Создаем заказ
    order_id = create_order(
        user_id=callback.from_user.id,
        username=callback.from_user.username or callback.from_user.first_name,
        product_id=product[0],
        product_name=product[1],
        amount=product[3],
        order_date=order_date,
        order_time=order_time,
        payment_method=payment_method['name']
    )
    
    # Для НСПК генерируем QR-код
    if payment_method['id'] == 'nspk':
        qr_text = f"НСПК|{order_id}|{product[3]}|{NSPK_ORGANIZATION['name']}"
        qr_img = generate_qr_code(qr_text)
        
        caption = (
            f"📱 **Оплата через QR НСПК**\n\n"
            f"🏢 **Организация:** {NSPK_ORGANIZATION['name']}\n"
            f"💳 **ИНН:** {NSPK_ORGANIZATION['inn']}\n"
            f"🏦 **Банк:** {NSPK_ORGANIZATION['bank']}\n\n"
            f"📋 **Детали заказа:**\n"
            f"• Номер: #{order_id}\n• Товар: {product[1]}\n"
            f"• Сумма: {product[3]:,}₽\n• Дата: {order_date}\n• Время: {order_time}\n\n"
            f"📞 После оплаты свяжитесь с администратором: {ADMIN_USERNAME}"
        )
        
        await bot.send_photo(callback.from_user.id, qr_img, caption=caption, parse_mode='Markdown')
    else:
        # Для банковских переводов
        text = (
            f"💳 **Оплата через {payment_method['name']}**\n\n"
            f"📋 **Детали заказа:**\n"
            f"• Номер: #{order_id}\n• Товар: {product[1]}\n"
            f"• Сумма: {product[3]:,}₽\n• Дата: {order_date}\n• Время: {order_time}\n\n"
            f"🏦 **Реквизиты для оплаты:**\n{payment_method['details']}\n\n"
            f"✅ **После оплаты:**\n"
            f"1. Сохраните чек/скриншот оплаты\n"
            f"2. Свяжитесь с администратором: {ADMIN_USERNAME}\n"
            f"3. Предоставьте номер заказа #{order_id}"
        )
        
        await callback.message.answer(text, parse_mode='Markdown')
    
    await state.finish()
    await callback.answer()

# ========================
# 8. Админ-панель
# ========================
@dp.callback_query_handler(lambda c: c.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа")
        return
    
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("➕ Ручной заказ", callback_data="manual_order"),
        InlineKeyboardButton("📊 Отчеты", callback_data="generate_report"),
        InlineKeyboardButton("🔙 Назад", callback_data="main_menu")
    )
    
    await callback.message.edit_text(
        f"👨‍💼 **Панель администратора**\n\n"
        f"📞 Контакт для клиентов: {ADMIN_USERNAME}",
        reply_markup=kb,
        parse_mode='Markdown'
    )

# ========================
# 9. Ручное добавление заказа (начало)
# ========================
@dp.callback_query_handler(lambda c: c.data == "manual_order")
async def start_manual_order(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа")
        return
    
    products = get_products()
    kb = InlineKeyboardMarkup(row_width=1)
    for product in products:
        kb.add(InlineKeyboardButton(
            f"{product[1]} - {product[3]:,}₽", 
            callback_data=f"mproduct_{product[0]}"
        ))
    
    await ManualOrderStates.waiting_for_product.set()
    await callback.message.edit_text(
        "🛒 **Добавление ручного заказа**\n\nВыберите товар:",
        reply_markup=kb,
        parse_mode='Markdown'
    )

# ========================
# 10. Генерация отчета
# ========================
@dp.callback_query_handler(lambda c: c.data == "generate_report")
async def generate_report(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Нет доступа")
        return
    
    orders = get_orders()
    total_amount = sum(order[5] for order in orders)
    
    report_text = f"📊 **ОТЧЕТ**\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
    report_text += f"💰 Общая сумма: {total_amount:,}₽\n📦 Заказов: {len(orders)}\n\n"
    
    for i, order in enumerate(orders, 1):
        report_text += f"{i}. {order[6]} {order[7]} - {order[4]} - {order[5]:,}₽ - {order[8]}\n"
    
    report_text += f"\n📞 Администратор: {ADMIN_USERNAME}"
    
    # Сохраняем в файл
    filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    await bot.send_document(callback.from_user.id, open(filename, 'rb'), caption="📊 Отчет по заказам")

# ========================
# 11. Контакты
# ========================
@dp.callback_query_handler(lambda c: c.data == "contacts")
async def show_contacts(callback: types.CallbackQuery):
    await callback.message.edit_text(
        f"📞 **Контакты**\n\n"
        f"Для связи с администратором:\n"
        f"👤 {ADMIN_USERNAME}\n\n"
        f"По всем вопросам покупок и поддержки обращайтесь к нам!",
        parse_mode='Markdown'
    )

# ========================
# 12. Главное меню
# ========================
@dp.callback_query_handler(lambda c: c.data == "main_menu")
async def main_menu(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🛍️ Магазин", callback_data="shop"),
        InlineKeyboardButton("📦 Мои заказы", callback_data="my_orders"),
        InlineKeyboardButton("📞 Контакты", callback_data="contacts"),
        InlineKeyboardButton("👨‍💼 Админ", callback_data="admin_panel")
    )
    
    await callback.message.edit_text(
        "Главное меню. Выберите действие:",
        reply_markup=kb
    )

# ========================
# Инициализация при запуске
# ========================
if __name__ == "__main__":
    init_db()
    executor.start_polling(dp, skip_updates=True)
