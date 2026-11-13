import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

import db
import division


def remaining(person_id, crate):
    return sum(d["remaining"] for d in division.owed_details()
               if (d["person_id"], d["purchase_id"]) == (person_id, crate))


def anyone_owes():
    return any(d["remaining"] for d in division.owed_details())


class DivisionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_path = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "beer.db"
        db.init()

    def tearDown(self):
        db.DB_PATH = self._old_path
        self._tmp.cleanup()

    def test_init_again_keeps_data(self):
        alice = division.add_person("Alice")
        crate = division.add_crate("Test", "2026-11-01", 24, 1500)
        division.record_consumption(alice, crate, 3)

        db.init()  # runs on every start; must not drop or duplicate anything

        self.assertEqual(remaining(alice, crate), 188)

    def test_purchase_summary_previews_the_close(self):
        alice = division.add_person("Alice")
        bob = division.add_person("Bob")
        crate = division.add_crate("Test", "2026-11-01", 24, 1500, 390)
        division.record_consumption(alice, crate, 6)
        division.record_consumption(bob, crate, 3)

        summary = division.purchase_summary(crate, 50)
        self.assertEqual(summary["unaccounted"], 15)
        self.assertEqual(summary["total_cents"], 1550)
        self.assertEqual(summary["drinkers"],
                         [("Alice", 6, 869), ("Bob", 3, 681)])

        # The preview refuses what the close would refuse.
        with self.assertRaises(ValueError):
            division.purchase_summary(crate, 391)  # more than the deposit
        division.close_purchase(crate, 50)
        with self.assertRaises(ValueError):
            division.purchase_summary(crate, 0)  # already closed

    def test_paid_open_share_never_ends_up_overpaid(self):
        division.record_opening(18000)
        people = [division.add_person(n) for n in ("A", "B", "C")]
        crate = division.add_crate("Test", "2026-11-01", 3, 1001)
        for person in people:
            division.record_consumption(person, crate, 1)
            division.record_payment(person, crate,
                                    remaining(person, crate))

        division.close_purchase(crate, 0)
        for person in people:
            self.assertGreaterEqual(remaining(person, crate), 0)
        self.assertFalse(anyone_owes())
        sheet = division.balance_sheet()
        self.assertEqual(sheet["difference"], 0)
        self.assertEqual(sheet["rounding"], -1)  # 3 x 334 = 1002 for 1001

    def test_consumption_is_dated_with_the_local_day(self):
        alice = division.add_person("Alice")
        crate = division.add_crate("Test", "2026-11-01", 24, 1500)
        division.record_consumption(alice, crate, 1)
        with db.connect() as conn:
            day = conn.execute("SELECT consumed_on FROM consumption").fetchone()[0]
        self.assertEqual(day, date.today().isoformat())

    def test_entry_must_belong_to_the_crate(self):
        alice = division.add_person("Alice")
        crate_a = division.add_crate("Test", "2026-11-01", 24, 1500)
        crate_b = division.add_crate("Test", "2026-11-01", 24, 1500)
        division.record_consumption(alice, crate_b, 3)
        entry = division.list_consumption(crate_b)[0]["consumption_id"]

        with self.assertRaises(ValueError):
            division.delete_consumption(crate_a, entry)
        self.assertEqual(len(division.list_consumption(crate_b)), 1)

    def test_cash_balance_and_payments(self):
        division.record_opening(18000)
        alice = division.add_person("Alice")
        bob = division.add_person("Bob")
        crate = division.add_crate("Test", "2026-11-01", 24, 1500, 390)

        # Untouched crate: cash + stock + deposit still equals the opening.
        sheet = division.balance_sheet()
        self.assertEqual(sheet["difference"], 0)
        self.assertEqual((sheet["inventory"], sheet["deposits"]), (1500, 390))

        division.record_consumption(alice, crate, 12)
        division.record_consumption(bob, crate, 12)
        self.assertEqual(remaining(alice, crate), 750)

        division.record_payment(alice, crate, 750)
        self.assertEqual(remaining(alice, crate), 0)
        with self.assertRaises(ValueError):
            division.record_payment(alice, crate, 1)

        division.close_purchase(crate, 0)
        self.assertEqual(division.get_balance(), 18000 - 1500 + 750)
        self.assertEqual(division.balance_sheet()["difference"], 0)

        with self.assertRaises(ValueError):
            division.record_opening(1)

    def test_delete_consumption_on_open_crate(self):
        alice = division.add_person("Alice")
        crate = division.add_crate("Test", "2026-11-01", 24, 1500)
        division.record_consumption(alice, crate, 3)
        entry = division.list_consumption(crate)[0]["consumption_id"]

        division.delete_consumption(crate, entry)
        self.assertEqual(division.list_consumption(crate), [])
        self.assertFalse(anyone_owes())

    def test_edit_crate_books_the_difference(self):
        division.record_opening(18000)
        alice = division.add_person("Alice")
        crate = division.add_crate("Test", "2026-11-01", 24, 1500, 390)
        division.record_consumption(alice, crate, 12)

        division.edit_crate(crate, 24, 1400, 390)
        self.assertEqual(division.get_balance(), 18000 - 1400 - 390)
        self.assertEqual(remaining(alice, crate), 700)
        self.assertEqual(division.balance_sheet()["difference"], 0)

        with self.assertRaises(ValueError):
            division.edit_crate(crate, 11, 1400, 390)  # below recorded

    def test_corrections_refused_when_closed_or_overpaid(self):
        alice = division.add_person("Alice")
        crate = division.add_crate("Test", "2026-11-01", 24, 1500)
        division.record_consumption(alice, crate, 12)
        entry = division.list_consumption(crate)[0]["consumption_id"]

        division.record_payment(alice, crate, 750)
        with self.assertRaises(ValueError):
            division.edit_crate(crate, 24, 1000, 0)  # share drops below paid
        with self.assertRaises(ValueError):
            division.delete_consumption(crate, entry)
        self.assertEqual(remaining(alice, crate), 0)  # rolled back

        division.close_purchase(crate, 0)
        with self.assertRaises(ValueError):
            division.edit_crate(crate, 24, 2000, 0)
        with self.assertRaises(ValueError):
            division.delete_consumption(crate, entry)

    def test_cash_only_added(self):
        division.record_opening(18000)
        with self.assertRaises(ValueError):
            division.add_cash(-100)
        self.assertEqual(division.get_balance(), 18000)

    def test_case_insensitive_names_and_deactivation(self):
        crate = division.add_crate("Grolsch", "2026-11-01", 24, 1500)
        division.add_crate("grolsch", "2026-11-02", 24, 1400)
        self.assertEqual(len(division.list_products()), 1)

        alice = division.add_person("Alice")
        with self.assertRaises(sqlite3.IntegrityError):
            division.add_person("alice")

        division.set_person_active(alice, False)
        self.assertEqual(division.list_people(True), [])
        with self.assertRaises(ValueError):
            division.record_consumption(alice, crate, 1)


if __name__ == "__main__":
    unittest.main()
