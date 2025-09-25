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

# ========================
# НАСТРОЙКИ АДМИНИСТРАТОРА
# ========================

# ЗАМЕНИТЕ на ваш реальный Telegram ID (узнайте через /myid)
ADMIN_IDS = [8341024077]  

# Контакт для связи (username без @)
ADMIN_CONTACT = "Paymentprosu"

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
# Функция проверки администратора
# ========================
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

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
# КОМАНДА ДЛЯ ПОЛУЧЕНИЯ ID
# ========================
@dp.message_handler(commands=['myid'])
async def get_my_id(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    admin_status = is_admin(user_id)
    
    response = (
        f"👤 **Ваши данные:**\n"
        f"• **ID:** `{user_id}`\n"
        f"• **Username:** @{username if username else 'нет'}\n"
        f"• **Имя:** {first_name}\n"
        f"• **Статус админа:** {'✅ ДА' if admin_status else '❌ НЕТ'}\n\n"
        f"**Контакт поддержки:** @{ADMIN_CONTACT}\n\n"
        f"**Чтобы стать админом:**\n"
        f"1. Скопируйте ваш ID: `{user_id}`\n"
        f"2. Замените `123456789` в коде на этот ID\n"
        f"3. Перезапустите бота"
    )
    
    await message.answer(response, parse_mode='Markdown')

# ========================
# Команда /start
# ========================
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("🛍️ Магазин", callback_data="menu_shop"),
        InlineKeyboardButton("📞 Контакты", callback_data="menu_contacts")
    ]
    
    # Проверяем, является ли пользователь админом
    if is_admin(user_id):
        buttons.append(InlineKeyboardButton("👨‍💼 Админ", callback_data="menu_admin"))
        logger.info(f"Пользователь {user_id} распознан как администратор")
    
    keyboard.add(*buttons)
    
    await message.reply(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"Выберите действие из меню ниже:",
        reply_markup=keyboard
    )

# ========================
# ГЛАВНЫЙ ОБРАБОТЧИК CALLBACK-ЗАПРОСОВ
# ========================
@dp.callback_query_handler(lambda call: True)
async def handle_all_callbacks(call: types.CallbackQuery):
    try:
        logger.info(f"Получен callback: {call.data} от пользователя {call.from_user.id}")
        
        # Всегда отвечаем на callback сначала
        await call.answer()
        
        if call.data == "menu_contacts":
            await handle_contacts(call)
        elif call.data == "menu_admin":
            await handle_admin(call)
        elif call.data == "menu_shop":
            await handle_shop(call)
        elif call.data == "menu_main":
            await handle_main_menu(call)
        elif call.data.startswith("product_"):
            await handle_product(call)
        else:
            await call.message.answer("Неизвестная команда")
            
    except Exception as e:
        logger.error(f"Ошибка в обработчике callback: {e}")
        await call.message.answer("Произошла ошибка. Попробуйте позже.")

# ========================
# ОБРАБОТЧИК КОНТАКТОВ
# ========================
async def handle_contacts(call: types.CallbackQuery):
    logger.info(f"Обрабатываем контакты для пользователя {call.from_user.id}")
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_main"))
    
    contact_text = (
        f"📞 **Контакты**\n\n"
        f"Для связи с администратором:\n"
        f"👤 @{the_boss_manger}\n\n"
        f"📧 **По всем вопросам:**\n"
        f"• Покупки услуг\n• Техническая поддержка\n• Сотрудничество\n\n"
        f"⏰ **Время ответа:** 1-2 часа\n"
        f"🕒 **Рабочее время:** 10:00 - 22:00"
    )
    
    try:
        await call.message.edit_text(
            contact_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        logger.info("Сообщение с контактами успешно отправлено")
    except Exception as e:
        logger.error(f"Ошибка при отправке контактов: {e}")
        # Если не удалось отредактировать, отправляем новое сообщение
        await call.message.answer(contact_text, parse_mode='Markdown')

# ========================
# ОБРАБОТЧИК АДМИН-ПАНЕЛИ
# ========================
async def handle_admin(call: types.CallbackQuery):
    user_id = call.from_user.id
    
    if is_admin(user_id):
        logger.info(f"Пользователь {user_id} зашел в админ-панель")
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_main"))
        
        admin_text = (
            f"👨‍💼 **Панель администратора**\n\n"
            f"📊 **Статистика:**\n"
            f"• Ваш ID: `{8341024077}`\n"
            f"• Контакт: @{Paymentprosu}\n\n"
            f"⚙️ **Доступные функции:**\n"
            f"• Просмотр заказов\n• Управление товарами\n• Статистика продаж"
        )
        
        await call.message.edit_text(
            admin_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    else:
        await call.answer("❌ У вас нет прав администратора", show_alert=True)

# ========================
# ОБРАБОТЧИК МАГАЗИНА
# ========================
async def handle_shop(call: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("💰 Товар 1 - 1000₽", callback_data="product_1"))
    keyboard.add(InlineKeyboardButton("💰 Товар 2 - 2000₽", callback_data="product_2"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="menu_main"))
    
    await call.message.edit_text(
        "🛍️ **Магазин услуг**\n\nВыберите товар:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

# ========================
# ОБРАБОТЧИК ГЛАВНОГО МЕНЮ
# ========================
async def handle_main_menu(call: types.CallbackQuery):
    user_id = call.from_user.id
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("🛍️ Магазин", callback_data="menu_shop"),
        InlineKeyboardButton("📞 Контакты", callback_data="menu_contacts")
    ]
    
    if is_admin(user_id):
        buttons.append(InlineKeyboardButton("👨‍💼 Админ", callback_data="menu_admin"))
    
    keyboard.add(*buttons)
    
    await call.message.edit_text(
        "Главное меню. Выберите действие:",
        reply_markup=keyboard
    )

# ========================
# ОБРАБОТЧИК ТОВАРОВ
# ========================
async def handle_product(call: types.CallbackQuery):
    product_id = call.data.split("_")[1]
    
    if product_id == "1":
        await call.message.answer("🎁 **Товар 1**\nЦена: 1000₽\nОписание: Веб-разработка")
    elif product_id == "2":
        await call.message.answer("🎁 **Товар 2**\nЦена: 2000₽\nОписание: Дизайн")

# ========================
# ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ
# ========================
@dp.message_handler()
async def handle_messages(message: types.Message):
    if message.text.startswith('/'):
        await message.answer("Используйте /start для начала работы или /myid чтобы узнать ваш ID")
    else:
        await message.answer(f"Для связи с администратором: @{the_boss_manger}")

# ========================
# ЗАПУСК БОТА
# ========================
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("ЗАПУСК БОТА")
    logger.info(f"Контакт поддержки: @{the_boss_manger}")
    logger.info("=" * 50)
    
    init_db()
    
    try:
        logger.info("Бот запускается...")
        executor.start_polling(dp, skip_updates=True)
    except Exception as e:
        logger.error(f"ОШИБКА ПРИ ЗАПУСКЕ: {e}")
