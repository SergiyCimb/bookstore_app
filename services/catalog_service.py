from __future__ import annotations

from typing import Any

from repositories.book_repo import BookRepository
from services.auth_service import AuthService


class CatalogService:
    def __init__(
        self,
        book_repo: BookRepository | None = None,
        auth_service: AuthService | None = None,
    ) -> None:
        self.book_repo = book_repo or BookRepository()
        self.auth_service = auth_service

    @staticmethod
    def resolve_stock_status(stock_qty: int, low_stock_threshold: int = 3) -> str:
        qty = int(stock_qty)
        threshold = max(0, int(low_stock_threshold))
        if qty <= 0:
            return "Розпродано"
        if qty <= threshold:
            return "Закінчується"
        return "В наявності"

    @staticmethod
    def _validate_book_fields(
        isbn: str,
        title: str,
        author: str,
        price: float,
        stock_qty: int,
        low_stock_threshold: int,
    ) -> tuple[str, str, str, float, int, int]:
        clean_isbn = isbn.strip()
        clean_title = title.strip()
        clean_author = author.strip()

        if len(clean_isbn) < 5:
            raise ValueError("Код ISBN повинен містити щонайменше 5 символів.")
        if not clean_title:
            raise ValueError("Назва книги не може бути порожньою.")
        if not clean_author:
            raise ValueError("Поле автора не може бути порожнім.")

        try:
            price_val = round(float(price), 2)
        except (TypeError, ValueError) as exc:
            raise ValueError("Ціна повинна бути числовим значенням.") from exc
        if price_val < 0:
            raise ValueError("Ціна книги не може бути від'ємною.")

        try:
            qty_val = int(stock_qty)
            threshold_val = int(low_stock_threshold)
        except (TypeError, ValueError) as exc:
            raise ValueError("Кількість і поріг залишку мають бути цілими числами.") from exc

        if qty_val < 0:
            raise ValueError("Кількість на складі не може бути від'ємною.")
        if threshold_val < 0:
            raise ValueError("Поріг мінімального залишку не може бути від'ємним.")

        return clean_isbn, clean_title, clean_author, price_val, qty_val, threshold_val

    def _enrich_book(self, book: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(book)
        enriched["genre_name"] = enriched.get("genre_name") or "Без жанру"
        enriched["availability_status"] = self.resolve_stock_status(
            int(enriched["stock_qty"]),
            int(enriched.get("low_stock_threshold", 3)),
        )
        return enriched

    def list_genres(self) -> list[dict[str, Any]]:
        return self.book_repo.list_genres()

    def add_genre(self, name: str) -> int:
        if self.auth_service is not None:
            self.auth_service.require_permission("catalog.manage")
        clean_name = name.strip()
        if len(clean_name) < 2:
            raise ValueError("Назва жанру повинна містити щонайменше 2 символи.")
        return self.book_repo.add_genre(clean_name)

    def search_books(
        self,
        query: str = "",
        genre_id: int | None = None,
        only_in_stock: bool = False,
    ) -> list[dict[str, Any]]:
        rows = self.book_repo.search_books(
            query=query,
            genre_id=genre_id,
            only_in_stock=only_in_stock,
        )
        return [self._enrich_book(row) for row in rows]

    def get_book(self, book_id: int) -> dict[str, Any] | None:
        book = self.book_repo.get_by_id(book_id)
        return self._enrich_book(book) if book else None

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
        if self.auth_service is not None:
            self.auth_service.require_permission("catalog.manage")
        clean_isbn, clean_title, clean_author, price_val, qty_val, threshold_val = (
            self._validate_book_fields(isbn, title, author, price, stock_qty, low_stock_threshold)
        )
        return self.book_repo.create_book(
            isbn=clean_isbn,
            title=clean_title,
            author=clean_author,
            genre_id=genre_id,
            price=price_val,
            stock_qty=qty_val,
            low_stock_threshold=threshold_val,
        )

    def update_book(
        self,
        book_id: int,
        isbn: str,
        title: str,
        author: str,
        genre_id: int | None,
        price: float,
        stock_qty: int,
        low_stock_threshold: int = 3,
    ) -> None:
        if self.auth_service is not None:
            self.auth_service.require_permission("catalog.manage")
        clean_isbn, clean_title, clean_author, price_val, qty_val, threshold_val = (
            self._validate_book_fields(isbn, title, author, price, stock_qty, low_stock_threshold)
        )
        self.book_repo.update_book(
            book_id=book_id,
            isbn=clean_isbn,
            title=clean_title,
            author=clean_author,
            genre_id=genre_id,
            price=price_val,
            stock_qty=qty_val,
            low_stock_threshold=threshold_val,
        )

    def delete_book(self, book_id: int) -> None:
        if self.auth_service is not None:
            self.auth_service.require_permission("catalog.manage")
        self.book_repo.delete_book(book_id)