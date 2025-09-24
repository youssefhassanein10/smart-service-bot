import os
from aiogram import Bot, Dispatcher, executor, types

API_TOKEN = os.getenv("API_TOKEN")  # токен берём из Railway переменной

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await message.answer("Привет 👋! Я твой магазин-бот. Скоро добавим корзину и оплату!")

if name == "__main__":
    executor.start_polling(dp, skip_updates=True)
