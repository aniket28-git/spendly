import sqlite3
import os
from werkzeug.security import generate_password_hash

DATABASE = os.path.join(os.path.dirname(__file__), '..', 'expense_tracker.db')


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            email         TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            title      TEXT NOT NULL,
            amount     REAL NOT NULL,
            category   TEXT NOT NULL DEFAULT 'Other',
            date       DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recurring_expenses (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            title      TEXT NOT NULL,
            amount     REAL NOT NULL,
            category   TEXT NOT NULL DEFAULT 'Other',
            frequency  TEXT NOT NULL,
            next_due   DATE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def get_spending_summary(db, user_id, start_date=None, end_date=None):
    if start_date and end_date:
        agg = db.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM expenses"
            " WHERE user_id = ? AND date BETWEEN ? AND ?",
            (user_id, start_date, end_date)
        ).fetchone()
        top_row = db.execute(
            "SELECT category FROM expenses"
            " WHERE user_id = ? AND date BETWEEN ? AND ?"
            " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id, start_date, end_date)
        ).fetchone()
    else:
        agg = db.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM expenses"
            " WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        top_row = db.execute(
            "SELECT category FROM expenses"
            " WHERE user_id = ?"
            " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id,)
        ).fetchone()
    return {
        "period_count": agg[0],
        "period_total": round(float(agg[1]), 2),
        "top_category": top_row["category"] if top_row else None,
    }


def seed_db():
    conn = get_db()
    existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing:
        conn.close()
        return

    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123"))
    )
    user_id = cursor.lastrowid

    conn.executemany(
        "INSERT INTO expenses (user_id, title, amount, category, date) VALUES (?, ?, ?, ?, ?)",
        [
            (user_id, "Dinner at restaurant",  850.00,  "Food & Dining",    "2026-05-02"),
            (user_id, "Weekly groceries",       1200.00, "Grocery",          "2026-05-05"),
            (user_id, "Metro monthly pass",     500.00,  "Transport",        "2026-05-07"),
            (user_id, "New headphones",         2999.00, "Shopping",         "2026-05-10"),
            (user_id, "Netflix subscription",   649.00,  "Entertainment",    "2026-05-12"),
            (user_id, "Udemy Python course",    399.00,  "Self Learning",    "2026-05-15"),
            (user_id, "Pharmacy",               320.00,  "Health",           "2026-05-20"),
            (user_id, "Electricity bill",       1450.00, "Bills & Utilities","2026-05-25"),
        ]
    )
    conn.commit()
    conn.close()
