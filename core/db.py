"""
Database connection helper for the user login store.

Provides a single reusable function to open the SQLite database.
"""

import sqlite3

DATABASE_NAME = "users.db"


def get_connection():
    """Opens a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn