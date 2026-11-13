from contextlib import contextmanager
from pathlib import Path
import os
import sqlite3
import sys


def _data_dir():
    """Per-user data folder, so the database survives reinstalls and upgrades."""
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / "BierKoning"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "BierKoning"
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "bierkoning"


DB_PATH = _data_dir() / "beer.db"


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()
