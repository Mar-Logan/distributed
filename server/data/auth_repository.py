"""
Server-side authentication repository.

The existing ConRes database stores users as:

    id TEXT PRIMARY KEY
    username TEXT NOT NULL

"""

from server.data.db import get_connection


def _get_user_columns(cursor):
    cursor.execute("PRAGMA table_info(users)")
    return {row["name"] for row in cursor.fetchall()}


def validate_credentials(user_id=None, username=None, password=None):
    """
    Validates credentials against users.db.

    Returns a dictionary containing the stored user if valid, otherwise None.
    """

    username = (username or "").strip()
    user_id = (user_id or "").strip()
    password = (password or "").strip()

    if not username:
        return None

    conn = get_connection()
    cursor = conn.cursor()

    try:
        columns = _get_user_columns(cursor)

        if "password" in columns and password:
            cursor.execute(
                "SELECT * FROM users WHERE username = ? AND password = ?",
                (username, password)
            )
        else:
            cursor.execute(
                "SELECT * FROM users WHERE id = ? AND username = ?",
                (user_id, username)
            )

        user = cursor.fetchone()
        return dict(user) if user else None

    finally:
        conn.close()
