from pathlib import Path

from db import connect

MIGRATIONS = Path(__file__).with_name("migrations")


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


if __name__ == "__main__":
    migrate()
    print("Database ready.")
