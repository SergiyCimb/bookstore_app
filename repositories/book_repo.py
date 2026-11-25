from __future__ import annotations

from typing import Any

from repositories.base import BaseRepository, InsufficientStockError


class BookRepository(BaseRepository):
    def list_genres(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT id, name FROM genres ORDER BY name;").fetchall()
            return [dict(row) for row in rows]

    def add_genre(self, name: str) -> int:
        with self.transaction() as conn:
            cursor = conn.execute("INSERT INTO genres (name) VALUES (?);", (name.strip(),))
            return int(cursor.lastrowid)

    def create_book(
        self,
        isbn: str,
        title: str,
        author: str,
        genre_id: int | None,
        price: float,
        stock_qty: int,
        low_stock_threshold: int = 3,
    ) -> int:
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO books (isbn, title, author, genre_id, price, stock_qty, low_stock_threshold)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    isbn.strip(),
                    title.strip(),
                    author.strip(),
                    genre_id,
                    float(price),
                    int(stock_qty),
                    int(low_stock_threshold),
                ),
            )
            return int(cursor.lastrowid)

    def update_book(
        self,
        book_id: int,
        isbn: str,
        title: str,
        author: str,
        genre_id: int | None,
        price: float,
        stock_qty: int,
        low_stock_threshold: int,
    ) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE books
                SET isbn = ?, title = ?, author = ?, genre_id = ?,
                    price = ?, stock_qty = ?, low_stock_threshold = ?
                WHERE id = ?;
                """,
                (
                    isbn.strip(),
                    title.strip(),
                    author.strip(),
                    genre_id,
                    float(price),
                    int(stock_qty),
                    int(low_stock_threshold),
                    int(book_id),
                ),
            )

    def delete_book(self, book_id: int) -> None:
        with self.transaction() as conn:
            conn.execute("DELETE FROM books WHERE id = ?;", (int(book_id),))

    def get_by_id(self, book_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT b.id, b.isbn, b.title, b.author, b.genre_id,
                       g.name AS genre_name, b.price, b.stock_qty, b.low_stock_threshold
                FROM books b
                LEFT JOIN genres g ON g.id = b.genre_id
                WHERE b.id = ?;
                """,
                (int(book_id),),
            ).fetchone()
            return dict(row) if row else None

    def search_books(
        self,
        query: str = "",
        genre_id: int | None = None,
        only_in_stock: bool = False,
    ) -> list[dict[str, Any]]:
        sql = [
            """
            SELECT b.id, b.isbn, b.title, b.author, b.genre_id,
                   g.name AS genre_name, b.price, b.stock_qty, b.low_stock_threshold
            FROM books b
            LEFT JOIN genres g ON g.id = b.genre_id
            WHERE 1=1
            """
        ]
        params: list[Any] = []

        cleaned = query.strip()
        if cleaned:
            like_pattern = f"%{cleaned}%"
            sql.append("AND (b.title LIKE ? OR b.author LIKE ? OR b.isbn LIKE ?)")
            params.extend([like_pattern, like_pattern, like_pattern])

        if genre_id is not None:
            sql.append("AND b.genre_id = ?")
            params.append(int(genre_id))

        if only_in_stock:
            sql.append("AND b.stock_qty > 0")

        sql.append("ORDER BY b.title;")

        with self.connect() as conn:
            rows = conn.execute("\n".join(sql), params).fetchall()
            return [dict(row) for row in rows]

    def decrement_stock(self, book_id: int, qty: int, conn=None) -> None:
        """Атомарно зменшує залишок книги в межах переданої транзакції."""
        if qty <= 0:
            raise ValueError("Кількість для списання має бути більшою за нуль.")

        with self.transaction(conn) as tx:
            cursor = tx.execute(
                """
                UPDATE books
                SET stock_qty = stock_qty - ?
                WHERE id = ? AND stock_qty >= ?;
                """,
                (int(qty), int(book_id), int(qty)),
            )
            if cursor.rowcount == 0:
                raise InsufficientStockError(
                    f"Недостатньо примірників книги (id={book_id}) для списання {qty} шт."
                )