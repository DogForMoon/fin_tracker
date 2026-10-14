from sqlalchemy import text

from tests.bot_case import BotCase


class BotStorageTests(BotCase):
    async def test_handler_saves_real_draft_to_sqlite(self):
        tag, _ = self.store.create_tag(self.user.id, "Работа")
        await self.driver.text("/income")
        await self.driver.text("125,50")
        await self.driver.click("Работа")
        await self.driver.click("Далее")
        await self.driver.text("salary")
        self.assertEqual(self.rows(), [])
        await self.driver.click("Далее")
        row = self.rows()[0]
        self.assertEqual((row.kind, row.amount_kopecks, row.comment), ("income", 12550, "salary"))
        self.assertEqual([item.id for item in row.tags], [tag.id])
        self.assertIn("сохранена", self.driver.latest().text)

    async def test_actual_sqlite_error_no_partial_data_or_success_and_retry(self):
        self.store.create_tag(self.user.id, "tag")
        await self.driver.text("/expense")
        await self.driver.text("1")
        await self.driver.click("tag")
        await self.driver.click("Далее")
        finish = self.driver.button("Далее")
        with self.store.engine.begin() as connection:
            connection.execute(text("CREATE TRIGGER fail_bot_link BEFORE INSERT ON transaction_tags BEGIN SELECT RAISE(ABORT, 'test write failure'); END"))
        await self.driver.click(data=finish)
        self.assertEqual(self.rows(), [])
        self.assertIn("Ошибка записи", self.driver.latest().text)
        self.assertNotIn("Операция сохранена", self.driver.texts())
        with self.store.engine.begin() as connection:
            connection.execute(text("DROP TRIGGER fail_bot_link"))
        await self.driver.click(data=finish)
        self.assertEqual(len(self.rows()), 1)

    async def test_late_archive_revalidated_at_save(self):
        tag, _ = self.store.create_tag(self.user.id, "late")
        await self.driver.text("/expense")
        await self.driver.text("1")
        await self.driver.click("late")
        await self.driver.click("Далее")
        self.store.archive_tag(self.user.id, tag.id)
        await self.driver.click("Далее")
        self.assertEqual(self.rows(), [])
        self.assertIn("Архивный", self.driver.latest().text)
        self.assertNotIn("Операция сохранена", self.driver.texts())

    async def test_new_user_write_error_is_reported_and_rolls_back(self):
        with self.store.engine.begin() as connection:
            connection.execute(text("CREATE TRIGGER fail_user BEFORE INSERT ON users BEGIN SELECT RAISE(ABORT, 'test user failure'); END"))
        await self.driver.text("/income", user_id=303)
        self.assertIn("Ошибка записи", self.driver.latest(303).text)
        self.assertNotIn("сохранена", self.driver.texts(303))
        with self.store.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM users WHERE telegram_id=303")), 0)
