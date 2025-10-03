# db.py
import os
import sqlite3
import hashlib
from datetime import datetime
from typing import Optional, List, Dict

APP_DB = os.path.join(os.path.dirname(__file__), "expenses.db")
DEFAULT_CATEGORIES = ["Food", "Bills", "Transport", "Entertainment", "Groceries", "Other"]

def get_db_connection():
    con = sqlite3.connect(APP_DB)
    con.row_factory = sqlite3.Row
    return con

def initialize_db():
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password_hash TEXT,
        created_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        date TEXT,
        type TEXT,
        category TEXT,
        amount REAL,
        description TEXT,
        created_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        name TEXT,
        UNIQUE(user_id, name),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    con.commit()
    con.close()

# Password hashing with PBKDF2
def hash_password(password: str, salt: bytes = None) -> str:
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
    return salt.hex() + dk.hex()

def verify_password(stored_hex: str, password_attempt: str) -> bool:
    try:
        salt = bytes.fromhex(stored_hex[:32])
        stored_dk = stored_hex[32:]
        dk = hashlib.pbkdf2_hmac('sha256', password_attempt.encode('utf-8'), salt, 100_000)
        return dk.hex() == stored_dk
    except Exception:
        return False

# User functions
def create_user(username: str, password: str) -> Optional[int]:
    con = get_db_connection()
    cur = con.cursor()
    try:
        h = hash_password(password)
        cur.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                    (username, h, datetime.utcnow().isoformat()))
        con.commit()
        uid = cur.lastrowid
        # seed default categories for this user
        for cat in DEFAULT_CATEGORIES:
            cur.execute("INSERT OR IGNORE INTO categories (user_id, name) VALUES (?, ?)", (uid, cat))
        con.commit()
        return uid
    except sqlite3.IntegrityError:
        return None
    finally:
        con.close()

def authenticate_user(username: str, password: str) -> Optional[int]:
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("SELECT id, password_hash FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    con.close()
    if not row:
        return None
    if verify_password(row["password_hash"], password):
        return row["id"]
    return None

# Category functions
def get_categories(user_id: int) -> List[str]:
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("SELECT name FROM categories WHERE user_id=? ORDER BY name", (user_id,))
    rows = [r["name"] for r in cur.fetchall()]
    if not rows:
        # seed defaults
        for cat in DEFAULT_CATEGORIES:
            cur.execute("INSERT OR IGNORE INTO categories (user_id, name) VALUES (?, ?)", (user_id, cat))
        con.commit()
        cur.execute("SELECT name FROM categories WHERE user_id=? ORDER BY name", (user_id,))
        rows = [r["name"] for r in cur.fetchall()]
    con.close()
    return rows

def add_category(user_id: int, name: str) -> bool:
    con = get_db_connection()
    cur = con.cursor()
    try:
        cur.execute("INSERT INTO categories (user_id, name) VALUES (?, ?)", (user_id, name))
        con.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        con.close()

def remove_category(user_id: int, name: str):
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("DELETE FROM categories WHERE user_id=? AND name=?", (user_id, name))
    con.commit()
    con.close()

# Transaction functions
def add_transaction(user_id: int, date_str: str, ttype: str, category: str, amount: float, description: str):
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO transactions (user_id, date, type, category, amount, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, date_str, ttype, category, amount, description, datetime.utcnow().isoformat()))
    con.commit()
    con.close()

def list_transactions(user_id: int):
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY date DESC, id DESC", (user_id,))
    rows = cur.fetchall()
    con.close()
    return rows

def delete_transaction(user_id: int, txid: int):
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (txid, user_id))
    con.commit()
    con.close()

def get_summary(user_id: int, start_date: str, end_date: str) -> Dict[str, float]:
    con = get_db_connection()
    cur = con.cursor()
    cur.execute("""
        SELECT type, SUM(amount) as s FROM transactions
        WHERE user_id=? AND date BETWEEN ? AND ?
        GROUP BY type
    """, (user_id, start_date, end_date))
    res = {r["type"]: r["s"] or 0.0 for r in cur.fetchall()}
    con.close()
    return res

# initialize database at import
initialize_db()
