import unittest
from unittest.mock import patch

import main


class AskTests(unittest.TestCase):
    def test_int_reprompts_until_known_id(self):
        with patch("builtins.input", side_effect=["x", "9", "2"]):
            self.assertEqual(main.ask_int("ID", valid={2}), 2)

    def test_cents_reprompts_until_valid_amount(self):
        with patch("builtins.input", side_effect=["abc", "-1", "20", "12.5"]):
            self.assertEqual(main.ask_cents("Pay", maximum=1500), 1250)

    def test_date_reprompts_until_iso(self):
        with patch("builtins.input", side_effect=["11-11-2026", "2026-11-11"]):
            self.assertEqual(main.ask_date("Date"), "2026-11-11")


if __name__ == "__main__":
    unittest.main()
