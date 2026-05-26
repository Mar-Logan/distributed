"""
Authentication helper for validating user credentials.

Checks whether a given ID and username exist in the database.
"""

from core.db import get_connection


def validate_user(user_id, username):
    """Returns True if the user ID and username match a database record."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE id = ? AND username = ?",
        (user_id, username)
    )
    user = cursor.fetchone()
    conn.close()

    return user is not None