import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from fin_tracker.db import Store


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "test.sqlite3"
        self.store = Store(self.path)
        self.user = self.store.ensure_user(101)
        self.other = self.store.ensure_user(202)
        self.at = datetime(2026, 10, 14, 20, 59, tzinfo=UTC)

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def create(self, **kwargs):
        return self.store.create_transaction(self.user.id, "income", 12550, self.at, **kwargs)

    def test_schema_foreign_keys_uniqueness_and_cascade(self):
        self.assertEqual(set(inspect(self.store.engine).get_table_names()), {"users", "tags", "transactions", "transaction_tags"})
        tag, _ = self.store.create_tag(self.user.id, "еда")
        transaction = self.create(tag_ids=[tag.id])
        with self.store.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("PRAGMA foreign_keys")), 1)
        with self.assertRaises(IntegrityError), self.store.engine.begin() as connection:
            connection.execute(text("INSERT INTO transaction_tags (transaction_id,tag_id) SELECT transaction_id,tag_id FROM transaction_tags"))
        with self.assertRaises(IntegrityError), self.store.engine.begin() as connection:
            connection.execute(text("INSERT INTO transaction_tags (transaction_id,tag_id) VALUES ('missing', 'missing')"))
        with self.assertRaises(IntegrityError), self.store.engine.begin() as connection:
            connection.execute(text("INSERT INTO users (id,telegram_id) VALUES ('duplicate-user', 101)"))
        with self.assertRaises(IntegrityError), self.store.engine.begin() as connection:
            connection.execute(text("INSERT INTO tags (id,user_id,name,normalized_name,is_archived) SELECT 'duplicate-tag',user_id,name,normalized_name,is_archived FROM tags"))
        self.store.delete_transaction(self.user.id, transaction.id)
        with self.store.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT count(*) FROM transaction_tags")), 0)
        self.assertEqual(self.store.get_tag(self.user.id, tag.id).name, "еда")

    def test_reopen_preserves_user_and_exact_transaction(self):
        tag, _ = self.store.create_tag(self.user.id, "Работа")
        amount = 10**100 + 1
        transaction = self.store.create_transaction(self.user.id, "expense", amount, self.at, [tag.id], "text")
        self.store.close()
        self.store = Store(self.path)
        self.assertEqual(self.store.ensure_user(101).id, self.user.id)
        loaded = self.store.get_transaction(self.user.id, transaction.id)
        self.assertEqual((loaded.amount_kopecks, loaded.kind, loaded.occurred_at, loaded.comment), (amount, "expense", self.at, "text"))
        self.assertEqual([item.id for item in loaded.tags], [tag.id])
        self.assertIsInstance(loaded.amount_kopecks, int)
        with self.store.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT typeof(amount_kopecks) FROM transactions")), "text")
            self.assertEqual(connection.scalar(text("SELECT amount_kopecks FROM transactions")), str(amount))

    def test_all_owner_boundaries(self):
        tag, _ = self.store.create_tag(self.user.id, "Secret")
        transaction = self.create(tag_ids=[tag.id], comment="private")
        self.assertEqual(self.store.list_transactions(self.other.id), [])
        self.assertEqual(self.store.list_tags(self.other.id, include_archived=True), [])
        actions = [
            lambda: self.store.get_transaction(self.other.id, transaction.id),
            lambda: self.store.delete_transaction(self.other.id, transaction.id),
            lambda: self.store.update_transaction(self.other.id, transaction.id, "expense", 1),
            lambda: self.store.get_tag(self.other.id, tag.id),
            lambda: self.store.rename_tag(self.other.id, tag.id, "stolen"),
            lambda: self.store.archive_tag(self.other.id, tag.id),
            lambda: self.store.create_transaction(self.other.id, "income", 100, self.at, [tag.id]),
        ]
        for action in actions:
            with self.subTest(action=action), self.assertRaises((LookupError, ValueError)):
                action()
        self.assertEqual(self.store.get_transaction(self.user.id, transaction.id).comment, "private")
        self.assertEqual(self.store.get_tag(self.user.id, tag.id).name, "Secret")

    def test_tag_lifecycle_conflicts_and_history(self):
        tag, restored = self.store.create_tag(self.user.id, " Еда ")
        self.assertFalse(restored)
        with self.assertRaises(ValueError):
            self.store.create_tag(self.user.id, "ЕДА")
        independent, _ = self.store.create_tag(self.other.id, "еда")
        self.assertNotEqual(tag.id, independent.id)
        transaction = self.create(tag_ids=[tag.id])
        self.store.rename_tag(self.user.id, tag.id, "Продукты")
        self.assertEqual(self.store.get_transaction(self.user.id, transaction.id).tags[0].name, "Продукты")
        conflict, _ = self.store.create_tag(self.user.id, "Другое")
        for archived in (False, True):
            if archived:
                self.store.archive_tag(self.user.id, conflict.id)
            with self.subTest(archived=archived), self.assertRaises(ValueError):
                self.store.rename_tag(self.user.id, tag.id, " ДРУГОЕ ")
        self.store.archive_tag(self.user.id, tag.id)
        self.assertEqual(self.store.list_tags(self.user.id), [])
        self.assertTrue(self.store.get_transaction(self.user.id, transaction.id).tags[0].is_archived)
        revived, restored = self.store.create_tag(self.user.id, " ПРОДУКТЫ ")
        self.assertTrue(restored)
        self.assertEqual((revived.id, revived.name), (tag.id, "Продукты"))
        self.assertEqual(self.store.get_transaction(self.user.id, transaction.id).tags[0].id, tag.id)

    def test_archive_assignment_and_retention(self):
        tag, _ = self.store.create_tag(self.user.id, "old")
        original = self.create(tag_ids=[tag.id])
        self.store.archive_tag(self.user.id, tag.id)
        with self.assertRaises(ValueError):
            self.create(tag_ids=[tag.id])
        changed = self.store.update_transaction(self.user.id, original.id, "expense", 999, [tag.id], retained_archived_tag_ids=[tag.id])
        self.assertEqual(changed.tags[0].id, tag.id)
        self.assertEqual(changed.occurred_at, original.occurred_at)
        self.store.update_transaction(self.user.id, original.id, "expense", 999, [])
        with self.assertRaises(ValueError):
            self.store.update_transaction(self.user.id, original.id, "expense", 999, [tag.id], retained_archived_tag_ids=[tag.id])

    def test_real_link_failure_rolls_back_create_and_update(self):
        tag, _ = self.store.create_tag(self.user.id, "tag")
        original = self.create(comment="original")
        with self.store.engine.begin() as connection:
            connection.execute(text("CREATE TRIGGER fail_link BEFORE INSERT ON transaction_tags BEGIN SELECT RAISE(ABORT, 'injected link failure'); END"))
        with self.assertRaises(IntegrityError):
            self.create(tag_ids=[tag.id])
        self.assertEqual(len(self.store.list_transactions(self.user.id)), 1)
        with self.assertRaises(IntegrityError):
            self.store.update_transaction(self.user.id, original.id, "expense", 1, [tag.id], "changed")
        loaded = self.store.get_transaction(self.user.id, original.id)
        self.assertEqual((loaded.kind, loaded.amount_kopecks, loaded.comment, loaded.tags), ("income", 12550, "original", ()))

    def test_moscow_day_half_open_filters_and_any_tag_without_duplicates(self):
        first, _ = self.store.create_tag(self.user.id, "a")
        second, _ = self.store.create_tag(self.user.id, "b")
        for timestamp, kind in [(datetime(2026, 10, 13, 20, 59, 59, tzinfo=UTC), "income"), (datetime(2026, 10, 13, 21, tzinfo=UTC), "expense"), (datetime(2026, 10, 14, 20, 59, 59, tzinfo=UTC), "income"), (datetime(2026, 10, 14, 21, tzinfo=UTC), "income")]:
            self.store.create_transaction(self.user.id, kind, 101, timestamp, [first.id, second.id], "both")
        self.store.archive_tag(self.user.id, first.id)
        rows = self.store.list_transactions(self.user.id, start=date(2026, 10, 14), end=date(2026, 10, 15), tag_ids=[first.id, second.id])
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({row.id for row in rows}), 2)
        self.assertEqual({row.occurred_at for row in rows}, {datetime(2026, 10, 13, 21, tzinfo=UTC), datetime(2026, 10, 14, 20, 59, 59, tzinfo=UTC)})
        self.assertEqual(len(self.store.list_transactions(self.user.id, start=date(2026, 10, 14), end=date(2026, 10, 15), kind="expense", tag_ids=[first.id])), 1)
        self.assertEqual(self.store.list_transactions(self.other.id, tag_ids=[first.id]), [])
