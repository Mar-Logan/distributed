"""
Server-side SQLite connection helper.

The TCP server is the only part of DistRes that should access users.db
directly. Clients authenticate by sending JSON requests to the server.
"""

import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "users.db"


def get_connection():
    """Opens a connection to the server-owned SQLite database."""

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn
