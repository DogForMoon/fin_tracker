import tempfile
import unittest
from pathlib import Path

from fin_tracker.bot import create_dispatcher
from fin_tracker.db import Store
from tests.telegram_boundary import TelegramDriver


class BotCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "bot-test.sqlite3"
        self.store = Store(self.path)
        self.driver = TelegramDriver(create_dispatcher(self.store))
        self.user = self.store.ensure_user(101)

    async def asyncTearDown(self):
        await self.driver.close()
        self.store.close()
        self.directory.cleanup()

    async def restart(self):
        await self.driver.close()
        self.store.close()
        self.store = Store(self.path)
        self.driver = TelegramDriver(create_dispatcher(self.store))

    def rows(self, user_id=None):
        return self.store.list_transactions(user_id or self.user.id)
