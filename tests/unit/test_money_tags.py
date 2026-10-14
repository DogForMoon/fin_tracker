import unittest

from fin_tracker.money import format_amount, parse_amount
from fin_tracker.tags import normalize_tag_name


class MoneyTests(unittest.TestCase):
    def test_valid_forms_and_minimum(self):
        for value, expected in [("125", 12500), ("125.5", 12550), ("125,50", 12550), ("0,01", 1), ("0001.01", 101)]:
            with self.subTest(value=value):
                self.assertEqual(parse_amount(value), expected)

    def test_rejects_invalid_forms_without_rounding(self):
        for value in ["0", "0.00", "-1", "+1", "1.", "1,234", "1e3", " ", "word", "", "1 ", " 1", "1\n", "١", "１２", "1.2.3", "1,2.3"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_amount(value)

    def test_exact_large_amount_up_to_telegram_message_size(self):
        value = "9" * 4093 + ".01"
        expected = int("9" * 4093) * 100 + 1
        self.assertEqual(parse_amount(value), expected)
        self.assertEqual(format_amount(expected), "9" * 4093 + ",01 ₽")
        self.assertGreater(expected, 2**63 - 1)
        self.assertEqual(parse_amount("9" * 4096), int("9" * 4096) * 100)
        self.assertEqual(parse_amount("0" * 4095 + "1"), 100)

    def test_display_always_two_places(self):
        for amount, expected in [(1, "0,01 ₽"), (12500, "125,00 ₽"), (12550, "125,50 ₽")]:
            with self.subTest(amount=amount):
                self.assertEqual(format_amount(amount), expected)


class TagNameTests(unittest.TestCase):
    def test_strip_casefold_preserve_inner_spaces(self):
        self.assertEqual(normalize_tag_name(" ЕДА "), "еда")
        self.assertEqual(normalize_tag_name("  Дом  и еда  "), "дом  и еда")
        self.assertEqual(normalize_tag_name("Straße"), "strasse")

    def test_blank_name_rejected(self):
        for value in ["", " ", "\t\n"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_tag_name(value)
