from __future__ import annotations

from typing import Any

from repositories.base import BaseRepository, InsufficientStockError


class OrderRepository(BaseRepository):
    def create_order_atomic(
        self,
        cashier_id: int,
        customer_id: int | None,
        discount_percent: float,
        items: list[dict[str, Any]],
    ) -> int:
        """
        Створює замовлення, записує позиції та списує залишки книг в одній транзакції.
        Кожен елемент `items` повинен містити: `book_id`, `quantity`, `unit_price`.
        """
        if not items:
            raise ValueError("Чек не може бути порожнім.")

        discount = max(0.0, min(100.0, float(discount_percent)))
        subtotal = 0.0
        prepared_lines: list[tuple[int, int, float, float]] = []

        for item in items:
            book_id = int(item["book_id"])
            qty = int(item["quantity"])
            unit_price = float(item["unit_price"])
            if qty <= 0 or unit_price < 0:
                raise ValueError("Некоректна кількість або ціна позиції.")
            line_total = round(qty * unit_price, 2)
            subtotal = round(subtotal + line_total, 2)
            prepared_lines.append((book_id, qty, unit_price, line_total))

        total_amount = round(subtotal * (1.0 - discount / 100.0), 2)

        with self.transaction() as conn:
            # Перевірка та списання залишків для кожної позиції
            for book_id, qty, _, _ in prepared_lines:
                cursor = conn.execute(
                    """
                    UPDATE books
                    SET stock_qty = stock_qty - ?
                    WHERE id = ? AND stock_qty >= ?;
                    """,
                    (qty, book_id, qty),
                )
                if cursor.rowcount == 0:
                    raise InsufficientStockError(
                        f"Недостатньо залишку на складі для книги id={book_id} (потрібно {qty} шт.)."
                    )

            order_cursor = conn.execute(
                """
                INSERT INTO orders (cashier_id, customer_id, discount_percent, subtotal, total_amount)
                VALUES (?, ?, ?, ?, ?);
                """,
                (int(cashier_id), customer_id, discount, subtotal, total_amount),
            )
            order_id = int(order_cursor.lastrowid)

            conn.executemany(
                """
                INSERT INTO order_items (order_id, book_id, quantity, unit_price, line_total)
                VALUES (?, ?, ?, ?, ?);
                """,
                [(order_id, book_id, qty, unit_price, line_total) for book_id, qty, unit_price, line_total in prepared_lines],
            )
            return order_id

    def list_orders(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT o.id, o.created_at, u.username AS cashier_name,
                       c.full_name AS customer_name, o.discount_percent,
                       o.subtotal, o.total_amount
                FROM orders o
                JOIN users u ON u.id = o.cashier_id
                LEFT JOIN customers c ON c.id = o.customer_id
                ORDER BY o.id DESC
                LIMIT ?;
                """,
                (int(limit),),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_order_items(self, order_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT oi.id, b.isbn, b.title, oi.quantity, oi.unit_price, oi.line_total
                FROM order_items oi
                JOIN books b ON b.id = oi.book_id
                WHERE oi.order_id = ?
                ORDER BY oi.id;
                """,
                (int(order_id),),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_sales_summary(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS orders_count,
                    COALESCE(SUM(total_amount), 0.0) AS total_revenue,
                    COALESCE(AVG(total_amount), 0.0) AS avg_check
                FROM orders;
                """
            ).fetchone()
            return dict(row) if row else {"orders_count": 0, "total_revenue": 0.0, "avg_check": 0.0}