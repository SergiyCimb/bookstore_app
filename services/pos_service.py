from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from repositories.book_repo import BookRepository
from repositories.customer_repo import CustomerRepository
from repositories.order_repo import OrderRepository
from services.auth_service import AuthService
from services.catalog_service import CatalogService


@dataclass
class CartItem:
    book_id: int
    isbn: str
    title: str
    unit_price: float
    quantity: int
    available_stock: int

    @property
    def line_total(self) -> float:
        return round(self.unit_price * self.quantity, 2)


class PosService:
    def __init__(
        self,
        order_repo: OrderRepository | None = None,
        book_repo: BookRepository | None = None,
        customer_repo: CustomerRepository | None = None,
        auth_service: AuthService | None = None,
    ) -> None:
        self.order_repo = order_repo or OrderRepository()
        self.book_repo = book_repo or BookRepository()
        self.customer_repo = customer_repo or CustomerRepository()
        self.auth_service = auth_service

        self.cart: dict[int, CartItem] = {}
        self.selected_customer: dict[str, Any] | None = None

    def clear_cart(self) -> None:
        self.cart.clear()
        self.selected_customer = None

    def attach_customer_by_phone(self, phone: str) -> dict[str, Any]:
        if self.auth_service is not None:
            self.auth_service.require_permission("pos.checkout")
        clean_phone = phone.strip()
        if not clean_phone:
            raise ValueError("Введіть номер телефону клієнта.")
        customer = self.customer_repo.find_by_phone(clean_phone)
        if customer is None:
            raise ValueError(f"Клієнта з номером «{clean_phone}» не знайдено.")
        self.selected_customer = customer
        return customer

    def clear_customer(self) -> None:
        self.selected_customer = None

    def add_to_cart(self, book_id: int, quantity: int = 1) -> list[CartItem]:
        if self.auth_service is not None:
            self.auth_service.require_permission("pos.checkout")

        qty = int(quantity)
        if qty <= 0:
            raise ValueError("Кількість примірників має бути більшою за нуль.")

        book = self.book_repo.get_by_id(book_id)
        if book is None:
            raise ValueError("Вибрану книгу не знайдено в каталозі.")

        stock = int(book["stock_qty"])
        threshold = int(book.get("low_stock_threshold", 3))
        status = CatalogService.resolve_stock_status(stock, threshold)
        if stock <= 0 or status == "Розпродано":
            raise ValueError(f"Книгу «{book['title']}» розпродано — додавання до кошика заблоковано.")

        current_in_cart = self.cart[book_id].quantity if book_id in self.cart else 0
        desired_total = current_in_cart + qty
        if desired_total > stock:
            raise ValueError(
                f"Недостатньо залишку для «{book['title']}»: доступно {stock} шт., у кошику вже {current_in_cart} шт."
            )

        self.cart[book_id] = CartItem(
            book_id=int(book["id"]),
            isbn=str(book["isbn"]),
            title=str(book["title"]),
            unit_price=float(book["price"]),
            quantity=desired_total,
            available_stock=stock,
        )
        return self.get_cart_items()

    def remove_from_cart(self, book_id: int) -> list[CartItem]:
        self.cart.pop(int(book_id), None)
        return self.get_cart_items()

    def get_cart_items(self) -> list[CartItem]:
        return list(self.cart.values())

    def get_totals(self) -> dict[str, Any]:
        subtotal = round(sum(item.line_total for item in self.cart.values()), 2)
        discount_percent = (
            float(self.selected_customer["discount_percent"])
            if self.selected_customer is not None
            else 0.0
        )
        discount_amount = round(subtotal * (discount_percent / 100.0), 2)
        total_amount = round(subtotal - discount_amount, 2)
        return {
            "subtotal": subtotal,
            "discount_percent": discount_percent,
            "discount_amount": discount_amount,
            "total_amount": total_amount,
            "customer": self.selected_customer,
        }

    def checkout(self) -> int:
        if self.auth_service is not None:
            self.auth_service.require_permission("pos.checkout")

        if not self.cart:
            raise ValueError("Кошик порожній. Додайте хоча б одну книгу перед оформленням чека.")

        cashier_id = self.auth_service.current_user.id if (self.auth_service and self.auth_service.current_user) else 1
        totals = self.get_totals()
        customer_id = int(self.selected_customer["id"]) if self.selected_customer is not None else None

        items_payload = [
            {
                "book_id": item.book_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
            }
            for item in self.cart.values()
        ]

        order_id = self.order_repo.create_order_atomic(
            cashier_id=cashier_id,
            customer_id=customer_id,
            discount_percent=float(totals["discount_percent"]),
            items=items_payload,
        )
        self.clear_cart()
        return order_id

    def list_orders(self, limit: int = 100) -> list[dict[str, Any]]:
        if self.auth_service is not None:
            self.auth_service.require_permission("orders.view")
        return self.order_repo.list_orders(limit=limit)

    def get_order_items(self, order_id: int) -> list[dict[str, Any]]:
        if self.auth_service is not None:
            self.auth_service.require_permission("orders.view")
        return self.order_repo.get_order_items(order_id)

    def get_sales_summary(self) -> dict[str, Any]:
        if self.auth_service is not None:
            self.auth_service.require_permission("reports.view")
        return self.order_repo.get_sales_summary()