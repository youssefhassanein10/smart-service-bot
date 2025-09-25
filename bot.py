import os
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN:
    raise ValueError("Не найден API_TOKEN. Добавь его в Render Environment Variables.")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ========================
# 1. Список товаров
# ========================
products = {
    1: {
        "name": "Товар 1",
        "price": 500,
        "desc": "Описание товара 1",
        "photo": "https://via.placeholder.com/300x200.png?text=Товар+1"
    },
    2: {
        "name": "Товар 2",
        "price": 750,
        "desc": "Описание товара 2",
        "photo": "https://via.placeholder.com/300x200.png?text=Товар+2"
    },
    3: {
        "name": "Товар 3",
        "price": 1200,
        "desc": "Описание товара 3",
        "photo": "https://via.placeholder.com/300x200.png?text=Товар+3"
    }
}

# ========================
# 2. Команда /start
# ========================
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    kb = InlineKeyboardMarkup()
    for pid, item in products.items():
        kb.add(InlineKeyboardButton(item["name"], callback_data=f"product_{pid}"))
    await message.answer("Добро пожаловать в магазин 🛍️\nВыберите товар:", reply_markup=kb)

# ========================
# 3. Просмотр товара
# ========================
@dp.callback_query_handler(lambda c: c.data.startswith("product_"))
async def show_product(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    product = products[pid]

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Добавить в корзину", callback_data=f"add_{pid}"))

    await bot.send_photo(
        callback.from_user.id,
        product["photo"],
        caption=f"📦 {product['name']}\n💰 Цена: {product['price']} ₽\n\n{product['desc']}",
        reply_markup=kb
    )

# ========================
# 4. Добавление в корзину (пока тест)
# ========================
@dp.callback_query_handler(lambda c: c.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    pid = int(callback.data.split("_")[1])
    product = products[pid]
    await callback.answer(f"{product['name']} добавлен в корзину ✅", show_alert=True)

# ========================
# Запуск
# ========================
if name == "__main__":
    executor.start_polling(dp, skip_updates=True)
