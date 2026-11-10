import sqlite3
import tempfile
import unittest
from pathlib import Path

import db
import division
import migrate


class MigrateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_path = db.DB_PATH
        db.DB_PATH = Path(self._tmp.name) / "beer.db"
        migrate.migrate()

    def tearDown(self):
        db.DB_PATH = self._old_path
        self._tmp.cleanup()

    def test_replay_and_second_run_keep_data(self):
        migrate.migrate()

        alice = division.add_person("Alice")
        crate = division.add_crate("Test", "2026-11-01", 24, 1500)
        division.record_consumption(alice, crate, 3)

        # Replaying the schema must not drop or duplicate anything.
        with db.connect() as conn:
            for path in sorted(migrate.MIGRATIONS.glob("*.sql")):
                conn.executescript(path.read_text())

        self.assertEqual(division.owed_by_person(), [("Alice", 188)])

    def test_purchase_summary_previews_the_close(self):
        alice = division.add_person("Alice")
        bob = division.add_person("Bob")
        crate = division.add_crate("Test", "2026-11-01", 24, 1500)
        division.record_consumption(alice, crate, 6)
        division.record_consumption(bob, crate, 3)

        summary = division.purchase_summary(crate, 50)
        self.assertEqual(summary["unaccounted"], 15)
        self.assertEqual(summary["total_cents"], 1550)
        self.assertEqual(summary["drinkers"],
                         [("Alice", 6, 869), ("Bob", 3, 681)])

    def test_legacy_marker_moves_out_of_sql_numbering(self):
        with db.connect() as conn:
            conn.execute("DELETE FROM schema_version")
            conn.execute("INSERT INTO schema_version (version) VALUES (2)")

        migrate.migrate()

        with db.connect() as conn:
            versions = {r["version"] for r in conn.execute(
                "SELECT version FROM schema_version")}
        self.assertIn(migrate.LEGACY_VERSION, versions)
        self.assertIn(2, versions)  # 002 is a real migration again

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
        self.assertEqual(division.remaining_for(alice, crate), 750)

        division.record_payment(alice, crate, 750)
        self.assertEqual(division.remaining_for(alice, crate), 0)
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

        division.delete_consumption(entry)
        self.assertEqual(division.list_consumption(crate), [])
        self.assertEqual(division.owed_by_person(), [])

    def test_edit_crate_books_the_difference(self):
        division.record_opening(18000)
        alice = division.add_person("Alice")
        crate = division.add_crate("Test", "2026-11-01", 24, 1500, 390)
        division.record_consumption(alice, crate, 12)

        division.edit_crate(crate, 24, 1400, 390)
        self.assertEqual(division.get_balance(), 18000 - 1400 - 390)
        self.assertEqual(division.remaining_for(alice, crate), 700)
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
            division.delete_consumption(entry)
        self.assertEqual(division.remaining_for(alice, crate), 0)  # rolled back

        division.close_purchase(crate, 0)
        with self.assertRaises(ValueError):
            division.edit_crate(crate, 24, 2000, 0)
        with self.assertRaises(ValueError):
            division.delete_consumption(entry)

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
