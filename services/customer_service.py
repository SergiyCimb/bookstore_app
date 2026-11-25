from __future__ import annotations

import re
from typing import Any

from repositories.customer_repo import CustomerRepository
from services.auth_service import AuthService

_PHONE_RE = re.compile(r"^\+?[0-9\s\-()]{7,20}$")


class CustomerService:
    def __init__(
        self,
        customer_repo: CustomerRepository | None = None,
        auth_service: AuthService | None = None,
    ) -> None:
        self.customer_repo = customer_repo or CustomerRepository()
        self.auth_service = auth_service

    @staticmethod
    def _validate_customer(full_name: str, phone: str, discount_percent: float) -> tuple[str, str, float]:
        clean_name = full_name.strip()
        clean_phone = phone.strip()

        if len(clean_name) < 2:
            raise ValueError("ПІБ або назва клієнта повинні містити щонайменше 2 символи.")
        if not _PHONE_RE.match(clean_phone):
            raise ValueError("Некоректний формат номера телефону.")

        try:
            discount_val = round(float(discount_percent), 2)
        except (TypeError, ValueError) as exc:
            raise ValueError("Знижка має бути числовим значенням.") from exc

        if discount_val < 0.0 or discount_val > 100.0:
            raise ValueError("Знижка клієнта має бути в межах від 0% до 100%.")

        return clean_name, clean_phone, discount_val

    def list_customers(self, query: str = "") -> list[dict[str, Any]]:
        if self.auth_service is not None:
            self.auth_service.require_permission("customers.view")
        return self.customer_repo.list_customers(query)

    def find_by_phone(self, phone: str) -> dict[str, Any] | None:
        if self.auth_service is not None:
            self.auth_service.require_permission("customers.view")
        clean_phone = phone.strip()
        if not clean_phone:
            raise ValueError("Введіть номер телефону для пошуку клієнта.")
        return self.customer_repo.find_by_phone(clean_phone)

    def create_customer(self, full_name: str, phone: str, discount_percent: float = 0.0) -> int:
        if self.auth_service is not None:
            self.auth_service.require_permission("customers.manage")
        clean_name, clean_phone, discount_val = self._validate_customer(
            full_name, phone, discount_percent
        )
        return self.customer_repo.create_customer(clean_name, clean_phone, discount_val)

    def update_customer(
        self,
        customer_id: int,
        full_name: str,
        phone: str,
        discount_percent: float,
    ) -> None:
        if self.auth_service is not None:
            self.auth_service.require_permission("customers.manage")
        clean_name, clean_phone, discount_val = self._validate_customer(
            full_name, phone, discount_percent
        )
        self.customer_repo.update_customer(customer_id, clean_name, clean_phone, discount_val)