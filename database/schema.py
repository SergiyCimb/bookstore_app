from __future__ import annotations

import hmac
import hashlib
import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "bookstore.db"


def hash_password(password: str, salt_hex: str | None = None) -> str:
    """Повертає рядок формату '<salt_hex>:<hash_hex>' із використанням PBKDF2-HMAC-SHA256."""
    if salt_hex is None:
        salt_hex = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        100_000,
    )
    return f"{salt_hex}:{dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Перевіряє пароль проти збереженого хешу '<salt_hex>:<hash_hex>'."""
    try:
        salt_hex, expected_hex = stored_hash.split(":", 1)
    except ValueError:
        return False
    actual = hash_password(password, salt_hex).split(":", 1)[1]
    return hmac.compare_digest(actual, expected_hex)


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS genres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    isbn TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    genre_id INTEGER REFERENCES genres(id) ON DELETE SET NULL,
    price REAL NOT NULL CHECK (price >= 0),
    stock_qty INTEGER NOT NULL DEFAULT 0 CHECK (stock_qty >= 0),
    low_stock_threshold INTEGER NOT NULL DEFAULT 3 CHECK (low_stock_threshold >= 0)
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    discount_percent REAL NOT NULL DEFAULT 0.0 CHECK (discount_percent >= 0 AND discount_percent <= 100)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'manager', 'cashier')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    cashier_id INTEGER NOT NULL REFERENCES users(id),
    customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL,
    discount_percent REAL NOT NULL DEFAULT 0.0 CHECK (discount_percent >= 0 AND discount_percent <= 100),
    subtotal REAL NOT NULL CHECK (subtotal >= 0),
    total_amount REAL NOT NULL CHECK (total_amount >= 0)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    book_id INTEGER NOT NULL REFERENCES books(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price >= 0),
    line_total REAL NOT NULL CHECK (line_total >= 0)
);

CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
CREATE INDEX IF NOT EXISTS idx_books_author ON books(author);
CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
"""


def get_connection(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Відкриває з'єднання з SQLite та вмикає перевірку зовнішніх ключів."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Path | str = DEFAULT_DB_PATH, seed_defaults: bool = True) -> None:
    """Створює таблиці та, за потреби, додає стартові довідники й облікові записи."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)

        if seed_defaults:
            default_genres = [
                "Художня література",
                "Науково-популярна",
                "Технічна література",
                "Історія та біографії",
            ]
            for genre in default_genres:
                conn.execute(
                    "INSERT OR IGNORE INTO genres (name) VALUES (?);",
                    (genre,),
                )

            # Базовий адміністратор для першого входу (змініть пароль після першого запуску)
            conn.execute(
                """
                INSERT OR IGNORE INTO users (username, password_hash, role, is_active)
                VALUES (?, ?, 'admin', 1);
                """,
                ("admin", hash_password("admin123")),
            )