import asyncio
from telegram import Bot
from config.settings import settings

async def test():
    bot = Bot(token=settings.telegram_bot_token)
    await bot.send_message(chat_id=settings.telegram_chat_id, text="Test from Trend Bot!")
    print("SUCCESS — check your Telegram!")

asyncio.run(test())
