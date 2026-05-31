import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            sources TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


def create_user(username, password_hash):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_user_by_username(username):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_chat(user_id, question, answer, sources):
    import json
    conn = get_conn()
    conn.execute(
        "INSERT INTO chat_history (user_id, question, answer, sources) VALUES (?, ?, ?, ?)",
        (user_id, question, answer, json.dumps(sources, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()


def get_history(user_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, question, answer, sources, created_at FROM chat_history WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    import json
    return [
        {
            "id": r["id"],
            "question": r["question"],
            "answer": r["answer"],
            "sources": json.loads(r["sources"]) if r["sources"] else [],
            "created_at": r["created_at"],
        }
        for r in rows
    ]
