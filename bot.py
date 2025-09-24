import os
from aiogram import Bot, Dispatcher, executor, types

# Берем токен из Railway переменной окружения
API_TOKEN = os.getenv("API_TOKEN")

# Проверяем, есть ли токен
if not API_TOKEN:
    raise ValueError("Не найден API_TOKEN. Добавь его в Railway Variables.")

# Создаем объекты бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Команда /start
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await message.answer("Привет 👋! Я твой магазин-бот. Скоро добавим корзину и оплату!")

# Команда /help
@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
    await message.answer("Я пока тестовый бот. Используй /start, чтобы поздороваться 🙂")

if name == "__main__":
    executor.start_polling(dp, skip_updates=True)
