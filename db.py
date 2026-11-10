from contextlib import contextmanager
from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).with_name("beer.db")


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()
