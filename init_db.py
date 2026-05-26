from core.db import get_connection


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL
        )
    """)

    sample_users = [
        ("1001", "alice"),
        ("1002", "bob"),
        ("1003", "charlie"),
        ("1004", "diana"),
        ("1005", "eve"),
        ("1006", "frank"),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO users (id, username)
        VALUES (?, ?)
    """, sample_users)

    conn.commit()
    conn.close()
    print("Database initialised successfully.")


if __name__ == "__main__":
    init_database()