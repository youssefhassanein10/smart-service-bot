import os
import logging
from aiogram import Bot, Dispatcher, executor, types

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not API_TOKEN:
    logger.error("❌ ТОКЕН НЕ НАЙДЕН!")
    logger.error("Добавьте TELEGRAM_BOT_TOKEN в Environment Variables на Railway")
else:
    logger.info("✅ Токен найден!")
    logger.info(f"Длина токена: {len(API_TOKEN)}")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    logger.info(f"Получена команда /start от {message.from_user.id}")
    await message.answer("✅ Бот работает! Тест пройден!")

@dp.message_handler(commands=['test'])
async def send_test(message: types.Message):
    await message.answer("Тестовое сообщение!")

@dp.message_handler()
async def echo(message: types.Message):
    await message.answer(f"Вы сказали: {message.text}")

if __name__ == "__main__":
    if API_TOKEN:
        logger.info("🚀 Запускаю бота...")
        executor.start_polling(dp, skip_updates=True)
    else:
        logger.error("❌ Токен не найден, бот не запущен")
