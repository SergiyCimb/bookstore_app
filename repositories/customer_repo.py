from __future__ import annotations

from typing import Any

from repositories.base import BaseRepository


class CustomerRepository(BaseRepository):
    def create_customer(
        self,
        full_name: str,
        phone: str,
        discount_percent: float = 0.0,
    ) -> int:
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO customers (full_name, phone, discount_percent)
                VALUES (?, ?, ?);
                """,
                (full_name.strip(), phone.strip(), float(discount_percent)),
            )
            return int(cursor.lastrowid)

    def update_customer(
        self,
        customer_id: int,
        full_name: str,
        phone: str,
        discount_percent: float,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE customers
                SET full_name = ?, phone = ?, discount_percent = ?
                WHERE id = ?;
                """,
                (full_name.strip(), phone.strip(), float(discount_percent), int(customer_id)),
            )

    def find_by_phone(self, phone: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT id, full_name, phone, discount_percent FROM customers WHERE phone = ?;",
                (phone.strip(),),
            ).fetchone()
            return dict(row) if row else None

    def list_customers(self, query: str = "") -> list[dict[str, Any]]:
        with self.connect() as conn:
            if query.strip():
                pattern = f"%{query.strip()}%"
                rows = conn.execute(
                    """
                    SELECT id, full_name, phone, discount_percent
                    FROM customers
                    WHERE full_name LIKE ? OR phone LIKE ?
                    ORDER BY full_name;
                    """,
                    (pattern, pattern),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, full_name, phone, discount_percent FROM customers ORDER BY full_name;"
                ).fetchall()
            return [dict(row) for row in rows]