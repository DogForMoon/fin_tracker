"""Запуск Telegram-бота финансового учёта."""

import asyncio
import sys

from aiogram import Bot
from aiogram.utils.token import TokenValidationError

from fin_tracker.bot import create_dispatcher
from fin_tracker.config import Config
from fin_tracker.db import Store


async def run(config: Config) -> None:
    store = Store(config.database_path)
    try:
        async with Bot(config.token) as bot:
            await create_dispatcher(store).start_polling(bot)
    finally:
        store.close()


def main() -> None:
    try:
        config = Config.from_env()
        asyncio.run(run(config))
    except (ValueError, TokenValidationError):
        print("Проверьте BOT_TOKEN: нужен корректный токен Telegram-бота.", file=sys.stderr)
        raise SystemExit(1) from None
