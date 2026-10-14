import unittest
from datetime import UTC, datetime

from fin_tracker.bot.dialog import Draft
from fin_tracker.db import TagData, TransactionData


class DialogTests(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 10, 14, 20, 59, 59, tzinfo=UTC)

    def test_unique_token_and_date_at_start(self):
        first = Draft.new("income", self.at)
        second = Draft.new("income", self.at)
        self.assertNotEqual(first.token, second.token)
        self.assertEqual(first.occurred_at, self.at)
        self.assertEqual(first.stage, "amount")
        self.assertTrue(first.matches(first.token, "amount"))
        self.assertFalse(first.matches(second.token, "amount"))
        self.assertFalse(first.matches(first.token, "comment"))

    def test_back_and_next_retain_date_kind_amount_tags_comment(self):
        draft = Draft.new("expense", self.at)
        draft.set_amount("125.5")
        draft.next()
        self.assertEqual(draft.stage, "tags")
        tag = TagData("tag", "user", "Еда", False)
        draft.toggle_tag(tag)
        draft.next()
        draft.set_comment("note")
        draft.back()
        draft.back()
        draft.back()
        self.assertEqual(draft.stage, "type")
        draft.set_kind("income")
        draft.next()
        draft.next()
        draft.next()
        self.assertEqual(draft.stage, "comment")
        self.assertEqual((draft.kind, draft.amount_kopecks, draft.tag_ids, draft.comment, draft.occurred_at), ("income", 12550, ["tag"], "note", self.at))
        self.assertEqual(draft.next(), "save")

    def test_invalid_amount_leaves_stage_and_existing_amount(self):
        draft = Draft.new("income", self.at)
        with self.assertRaises(ValueError):
            draft.next()
        self.assertEqual(draft.stage, "amount")
        draft.set_amount("1")
        with self.assertRaises(ValueError):
            draft.set_amount("1.001")
        self.assertEqual((draft.amount_kopecks, draft.stage), (100, "amount"))

    def test_comment_replace_clear_is_draft_only(self):
        transaction = TransactionData("txn", "user", "income", 100, self.at, "original", ())
        draft = Draft.edit(transaction)
        self.assertEqual(draft.stage, "type")
        self.assertEqual(draft.comment, "original")
        draft.set_comment("replacement")
        self.assertEqual(draft.comment, "replacement")
        draft.stage = "comment"
        draft.clear_comment()
        self.assertIsNone(draft.comment)
        self.assertEqual(draft.stage, "comment")
        self.assertEqual(transaction.comment, "original")
        self.assertEqual(draft.occurred_at, transaction.occurred_at)

    def test_optional_tags_comment_skipped(self):
        draft = Draft.new("expense", self.at)
        draft.set_amount("0,01")
        draft.next()
        draft.next()
        self.assertEqual(draft.next(), "save")
        self.assertEqual(draft.tag_ids, [])
        self.assertIsNone(draft.comment)

    def test_archived_tag_retention_and_permanent_removal(self):
        tag = TagData("tag", "user", "Еда", True)
        transaction = TransactionData("txn", "user", "income", 100, self.at, None, (tag,))
        draft = Draft.edit(transaction)
        draft.set_amount("2")
        self.assertIn(tag.id, draft.tag_ids)
        self.assertIn(tag.id, draft.retained_tag_ids)
        self.assertTrue(draft.toggle_tag(tag))
        self.assertNotIn(tag.id, draft.tag_ids)
        self.assertNotIn(tag.id, draft.retained_tag_ids)
        with self.assertRaises(ValueError):
            draft.toggle_tag(tag)
        revived = TagData(tag.id, tag.user_id, tag.name, False)
        draft.toggle_tag(revived)
        self.assertIn(tag.id, draft.tag_ids)

    def test_new_archived_tag_and_invalid_kind_rejected(self):
        draft = Draft.new("income", self.at)
        with self.assertRaises(ValueError):
            draft.toggle_tag(TagData("old", "user", "Old", True))
        self.assertEqual(draft.tag_ids, [])
        with self.assertRaises(ValueError):
            draft.set_kind("unsupported")
