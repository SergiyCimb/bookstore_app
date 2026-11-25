from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from database.schema import DEFAULT_DB_PATH, get_connection


class RepositoryError(Exception):
    """Базовий виняток рівня доступу до даних."""


class IntegrityConflictError(RepositoryError):
    """Порушення обмежень цілісності (унікальність, зовнішні ключі, CHECK)."""


class InsufficientStockError(RepositoryError):
    """Недостатній залишок товару на складі під час проведення операції."""


class BaseRepository:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        return get_connection(self.db_path)

    @contextmanager
    def transaction(self, conn: sqlite3.Connection | None = None) -> Iterator[sqlite3.Connection]:
        """Виконує блок запитів в одній транзакції з автоматичним COMMIT або ROLLBACK."""
        owns_connection = conn is None
        active_conn = conn if conn is not None else self.connect()
        try:
            yield active_conn
            if owns_connection:
                active_conn.commit()
        except sqlite3.IntegrityError as exc:
            if owns_connection:
                active_conn.rollback()
            raise IntegrityConflictError(f"Помилка цілісності бази даних: {exc}") from exc
        except Exception:
            if owns_connection:
                active_conn.rollback()
            raise
        finally:
            if owns_connection:
                active_conn.close()