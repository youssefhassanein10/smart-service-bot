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
    # Не вызываем исключение, чтобы приложение могло запуститься
    # raise ValueError("Не найден API_TOKEN. Добавь его в Render Environment Variables.")

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
    }
]

# Инициализация бота только если токен есть
if API_TOKEN:
    bot = Bot(token=API_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(bot, storage=storage)
else:
    bot = None
    dp = None

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
        logger.info("База данных инициализирована успешно")
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
async def start_command(message: types.Message):
    if not bot:
        await message.answer("Бот временно недоступен. Попробуйте позже.")
        return
        
    kb = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("🛍️ Магазин", callback_data="shop"),
        InlineKeyboardButton("📞 Контакты", callback_data="contacts")
    ]
    
    if message.from_user.id in ADMIN_IDS:
        buttons.append(InlineKeyboardButton("👨‍💼 Админ", callback_data="admin_panel"))
    
    kb.add(*buttons)
    
    await message.answer(
        f"👋 Добро пожаловать, {message.from_user.first_name}!\n\n"
        "Выберите действие из меню ниже:",
        reply_markup=kb
    )

# Остальные хендлеры остаются без изменений...
# [Вставьте здесь все остальные функции из вашего оригинального кода]

# ========================
# Запуск бота
# ========================
def main():
    init_db()
    if API_TOKEN:
        logger.info("Бот запускается...")
        executor.start_polling(dp, skip_updates=True)
    else:
        logger.error("API_TOKEN не установлен. Бот не может быть запущен.")

if __name__ == "__main__":
    main()
