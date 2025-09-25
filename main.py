import os
import logging
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    logger.error("Не найден API_TOKEN. Добавь его в Render Environment Variables.")
    exit(1)

# Настройки администратора
ADMIN_USERNAME = "paymentprosu"
ADMIN_IDS = [8341024077]  # Замени на свой ID Telegram

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
    }
]

# Инициализация бота
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Состояния для FSM
class OrderStates(StatesGroup):
    waiting_for_date = State()
    waiting_for_time = State()
    waiting_for_payment = State()

# ========================
# Инициализация базы данных
# ========================
def init_db():
    try:
        conn = sqlite3.connect('shop.db', check_same_thread=False)
        cursor = conn.cursor()
        
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
                ("Консультация", "Техническая консультация 1 час", 3000, "https://via.placeholder.com/300x200.png?text=Консультация")
            ]
            cursor.executemany('INSERT INTO products (name, description, price, photo_url) VALUES (?, ?, ?, ?)', products)
        
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")

def get_products():
    conn = sqlite3.connect('shop.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE is_active = TRUE')
    products = cursor.fetchall()
    conn.close()
    return products

def get_product(product_id):
    conn = sqlite3.connect('shop.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()
    conn.close()
    return product

def create_order(user_id, username, product_id, product_name, amount, order_date, order_time, payment_method):
    conn = sqlite3.connect('shop.db', check_same_thread=False)
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

# ========================
# Команда /start
# ========================
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("🛍️ Магазин", callback_data="menu_shop"),
        InlineKeyboardButton("📞 Контакты", callback_data="menu_contacts")
    ]
    
    if message.from_user.id in ADMIN_IDS:
        buttons.append(InlineKeyboardButton("👨‍💼 Админ", callback_data="menu_admin"))
    
    keyboard.add(*buttons)
    
    await message.reply(
        f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
        "Выберите действие из меню ниже:",
        reply_markup=keyboard
    )

# ========================
# Главный обработчик callback запросов
# ========================
@dp.callback_query_handler(lambda call: True)
async def handle_callback_query(call: types.CallbackQuery, state: FSMContext):
    try:
        # Всегда отвечаем на callback сначала
        await call.answer()
        
        logger.info(f"Обрабатываем callback: {call.data}")
        
        if call.data == "menu_shop":
            await show_shop_menu(call.message)
        elif call.data == "menu_contacts":
            await show_contacts(call.message)
        elif call.data == "menu_admin":
            await show_admin_panel(call.message)
        elif call.data == "menu_main":
            await show_main_menu(call.message)
        elif call.data.startswith("product_"):
            product_id = int(call.data.split("_")[1])
            await show_product(call.message, product_id)
        elif call.data.startswith("buy_"):
            product_id = int(call.data.split("_")[1])
            await start_order(call.message, state, product_id)
        elif call.data.startswith("pay_"):
            await process_payment(call, state)
        else:
            await call.message.answer("Неизвестная команда")
            
    except Exception as e:
        logger.error(f"Ошибка в обработчике callback: {e}")
        await call.message.answer("Произошла ошибка. Попробуйте позже.")

# ========================
# Показать главное меню
# ========================
async def show_main_menu(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("🛍️ Магазин", callback_data="menu_shop"),
        InlineKeyboardButton("📞 Контакты", callback_data="menu_contacts")
    ]
    
    if message.from_user.id in ADMIN_IDS:
        buttons.append(InlineKeyboardButton("👨‍💼 Админ", callback_data="menu_admin"))
    
    keyboard.add(*buttons)
    
    await message.edit_text(
        "Главное меню. Выберите действие:",
        reply_markup=keyboard
    )

# ========================
# Показать магазин
# ========================
async def show_shop_menu(message: types.Message):
    products = get_products()
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    for product in products:
        keyboard.add(InlineKeyboardButton(
            f"{product[1]} - {product[3]:,}₽", 
            callback_data=f"product_{product[0]}"
        ))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_main"))
    
    await message.edit_text(
        "🛍️ **Наш магазин услуг**\n\nВыберите услугу:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

# ========================
# Показать товар
# ========================
async def show_product(message: types.Message, product_id: int):
    product = get_product(product_id)
    
    if not product:
        await message.answer("Товар не найден")
        return
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("💰 Купить", callback_data=f"buy_{product_id}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_shop"))
    
    # Удаляем предыдущее сообщение и отправляем новое с фото
    await message.delete()
    await bot.send_photo(
        message.chat.id,
        product[4],
        caption=f"🎁 **{product[1]}**\n\n📝 {product[2]}\n\n💵 **Цена: {product[3]:,}₽**",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

# ========================
# Начать заказ
# ========================
async def start_order(message: types.Message, state: FSMContext, product_id: int):
    product = get_product(product_id)
    
    if not product:
        await message.answer("Товар не найден")
        return
    
    async with state.proxy() as data:
        data['product'] = product
        data['product_id'] = product_id
    
    await OrderStates.waiting_for_date.set()
    await message.answer(
        f"🎁 Товар: **{product[1]}**\n💵 Сумма: **{product[3]:,}₽**\n\n"
        f"📅 Введите дату заказа в формате **ДД.ММ.ГГГГ**:\n"
        f"Пример: {datetime.now().strftime('%d.%m.%Y')}",
        parse_mode='Markdown'
    )

# ========================
# Обработка даты
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
# Обработка времени
# ========================
@dp.message_handler(state=OrderStates.waiting_for_time)
async def process_order_time(message: types.Message, state: FSMContext):
    if not validate_time(message.text):
        await message.answer("❌ Неверный формат времени. Введите в формате ЧЧ:ММ:")
        return
    
    async with state.proxy() as data:
        data['order_time'] = message.text
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    for payment in PAYMENT_METHODS:
        keyboard.add(InlineKeyboardButton(f"💳 {payment['name']}", callback_data=f"pay_{payment['id']}"))
    
    await OrderStates.next()
    await message.answer("💳 Выберите способ оплаты:", reply_markup=keyboard)

# ========================
# Обработка оплаты
# ========================
async def process_payment(call: types.CallbackQuery, state: FSMContext):
    payment_id = call.data.split("_")[1]
    payment_method = next((pm for pm in PAYMENT_METHODS if pm["id"] == payment_id), None)
    
    if not payment_method:
        await call.message.answer("Способ оплаты не найден")
        return
    
    async with state.proxy() as data:
        product = data['product']
        order_date = data['order_date']
        order_time = data['order_time']
    
    order_id = create_order(
        user_id=call.from_user.id,
        username=call.from_user.username or call.from_user.first_name,
        product_id=product[0],
        product_name=product[1],
        amount=product[3],
        order_date=order_date,
        order_time=order_time,
        payment_method=payment_method['name']
    )
    
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
    
    await call.message.answer(text, parse_mode='Markdown')
    await state.finish()

# ========================
# Показать контакты
# ========================
async def show_contacts(message: types.Message):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_main"))
    
    await message.edit_text(
        f"📞 **Контакты**\n\n"
        f"Для связи с администратором:\n"
        f"👤 {ADMIN_USERNAME}\n\n"
        f"По всем вопросам покупок и поддержки обращайтесь к нам!",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

# ========================
# Показать админ-панель
# ========================
async def show_admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа")
        return
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_main"))
    
    await message.edit_text(
        f"👨‍💼 **Панель администратора**\n\n"
        f"📞 Контакт для клиентов: {paymentprosu}",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

# ========================
# Обработка неизвестных сообщений
# ========================
@dp.message_handler()
async def unknown_message(message: types.Message):
    await message.answer("Используйте команду /start для начала работы")

# ========================
# Запуск бота
# ========================
if name == "__main__":
    try:
        init_db()
        logger.info("Бот запускается...")
        executor.start_polling(dp, skip_updates=True)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
