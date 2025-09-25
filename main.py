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

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not API_TOKEN:
    logger.error("Не найден TELEGRAM_BOT_TOKEN. Добавь его в Railway Environment Variables.")
    exit(1)

# Настройки администратора (ЗАМЕНИТЕ НА СВОИ ДАННЫЕ)
ADMIN_IDS = [8341024077]  # Ваш Telegram ID
ADMIN_USERNAME = "@paymentprosu"  # Ваш username в Telegram

# Способы оплаты
PAYMENT_METHODS = [
    {
        "id": "sber",
        "name": "Сбербанк", 
        "details": "Номер карты: 1234 5678 9012 3456\nПолучатель: Иван Иванов"
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
                ("Дизайн", "UI/UX дизайн интерфейса", 2000, "https://via.placeholder.com/300x200.png?text=Дизайн")
            ]
            cursor.executemany('INSERT INTO products (name, description, price, photo_url) VALUES (?, ?, ?, ?)', products)
        
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")

# ========================
# Команда /start (простая версия для теста)
# ========================
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("🛍️ Магазин", callback_data="shop"),
        InlineKeyboardButton("📞 Контакты", callback_data="contacts")
    ]
    
    if message.from_user.id in ADMIN_IDS:
        buttons.append(InlineKeyboardButton("👨‍💼 Админ", callback_data="admin"))
    
    keyboard.add(*buttons)
    
    await message.reply(
        f"👋 Привет, {message.from_user.first_name}!\nВыберите действие:",
        reply_markup=keyboard
    )

# Простой обработчик для теста
@dp.callback_query_handler(lambda call: call.data == "shop")
async def show_shop(call: types.CallbackQuery):
    await call.answer()
    await call.message.answer("🛍️ Это раздел магазина!")

@dp.callback_query_handler(lambda call: call.data == "contacts")  
async def show_contacts(call: types.CallbackQuery):
    await call.answer()
    await call.message.answer(f"📞 Контакты: {paymentprosu}")

@dp.callback_query_handler(lambda call: call.data == "admin")
async def show_admin(call: types.CallbackQuery):
    await call.answer()
    if call.from_user.id in ADMIN_IDS:
        await call.message.answer("👨‍💼 Панель администратора")
    else:
        await call.message.answer("❌ Нет доступа")

# Обработчик любых сообщений
@dp.message_handler()
async def echo(message: types.Message):
    await message.answer("Используйте /start для начала работы")

# ========================
# ЗАПУСК БОТА - ДОЛЖЕН БЫТЬ В САМОМ КОНЦЕ ФАЙЛА!
# ========================
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("ЗАПУСК БОТА НА RAILWAY")
    logger.info("=" * 50)
    
    init_db()
    
    try:
        logger.info("Бот запускается...")
        executor.start_polling(dp, skip_updates=True)
    except Exception as e:
        logger.error(f"ОШИБКА ПРИ ЗАПУСКЕ: {e}")
