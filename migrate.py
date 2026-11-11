import re
from decimal import Decimal
from pathlib import Path

from db import connect

MIGRATIONS = Path(__file__).with_name("migrations")
# shortcut: SQL versions must stay below 1000; use a separate migration-name
# table if that range is ever exhausted.
LEGACY_VERSION = 1000


def _tables(conn):
    return {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}


def _prepare_legacy(conn):
    """The old consumption table was never written to; make room for the new one."""
    if "consumption" not in _tables(conn):
        return
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(consumption)")}
    if "consumption_id" not in columns:
        conn.execute("DROP TABLE consumption")


def _canonical(name):
    base = re.sub(r"\d+$", "", name.strip())
    key = re.sub(r"[^a-z0-9]", "", base.lower())
    return {
        "hertogjan": "Hertogjan",
        "grolsch": "Grolsch",
        "grolschpils": "Grolsch",
        "deklok": "De Klok",
        "leffe": "Leffe",
        "grolschalvrij": "Grolsch 0.0",
        "birramorreti": "Birra Moretti",
        "bavaria": "Bavaria",
        "groslchradler": "Grolsch Radler",
    }.get(key, base)


def _import_legacy(conn):
    if "beer" not in _tables(conn):
        return
    rows = conn.execute("""
        SELECT b.beer_id, b.name, b.purchase_date, b.quantity, b.price,
               COALESCE(s.value, 0) AS deposit, b.status
        FROM beer b
        LEFT JOIN statiegeld s ON s.beer_id = b.beer_id
    """).fetchall()
    for r in rows:
        name = _canonical(r["name"])
        conn.execute("INSERT OR IGNORE INTO product (name) VALUES (?)", (name,))
        conn.execute("""
            INSERT OR IGNORE INTO legacy_purchase
              (legacy_id, product_name, purchased_on, bottles,
               total_price_cents, deposit_cents, old_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            r["beer_id"], name, r["purchase_date"], r["quantity"],
            int(Decimal(str(r["price"])) * 100),
            int(Decimal(str(r["deposit"])) * 100),
            r["status"],
        ))


def migrate():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
              version    INTEGER PRIMARY KEY,
              applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        done = {r["version"] for r in conn.execute(
            "SELECT version FROM schema_version")}

        # Version 2 used to be the legacy import. Move it out of the SQL
        # numbering so a future 002_*.sql cannot collide with it.
        if 2 in done and LEGACY_VERSION not in done:
            conn.execute("UPDATE schema_version SET version = ? WHERE version = 2",
                         (LEGACY_VERSION,))
            done.remove(2)
            done.add(LEGACY_VERSION)

        _prepare_legacy(conn)

        for path in sorted(MIGRATIONS.glob("*.sql")):
            version = int(path.name.split("_", 1)[0])
            if version in done:
                continue
            # One transaction: the schema change and its version row land
            # together or not at all, so a failed migration can be re-run.
            conn.executescript(
                f"BEGIN;\n{path.read_text()}\n"
                f"INSERT INTO schema_version (version) VALUES ({version});\n"
                "COMMIT;")
            done.add(version)

        if LEGACY_VERSION not in done:
            _import_legacy(conn)
            conn.execute("INSERT INTO schema_version (version) VALUES (?)",
                         (LEGACY_VERSION,))


if __name__ == "__main__":
    migrate()
    print("Database ready.")
