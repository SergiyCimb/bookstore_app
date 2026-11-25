from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from services.auth_service import AuthService, SessionUser
from services.catalog_service import CatalogService
from services.customer_service import CustomerService
from services.pos_service import PosService
from ui.catalog_tab import CatalogTab
from ui.customers_tab import CustomersTab
from ui.orders_tab import OrdersTab
from ui.pos_tab import PosTab
from ui.users_tab import UsersTab


class MainWindow(ttk.Frame):
    """Головне вікно з навігацією по вкладках та розмежуванням доступу за ролями."""

    def __init__(
        self,
        root: tk.Tk,
        user: SessionUser,
        auth_service: AuthService,
        catalog_service: CatalogService,
        customer_service: CustomerService,
        pos_service: PosService,
        on_logout: Any = None,
    ) -> None:
        super().__init__(root, padding=10)
        self.root = root
        self.user = user
        self.auth_service = auth_service
        self.catalog_service = catalog_service
        self.customer_service = customer_service
        self.pos_service = pos_service
        self.on_logout = on_logout

        self.pack(fill=tk.BOTH, expand=True)
        self._build_header()
        self._build_tabs()

    def _build_header(self) -> None:
        header = ttk.Frame(self, padding=(4, 2, 4, 8))
        header.pack(fill=tk.X)

        ttk.Label(
            header,
            text="Система автоматизації обліку та продажів книгарні",
            font=("TkDefaultFont", 12, "bold"),
        ).pack(side=tk.LEFT)

        right = ttk.Frame(header)
        right.pack(side=tk.RIGHT)

        ttk.Label(
            right,
            text=f"Користувач: {self.user.username} | Роль: {self.user.role}",
        ).pack(side=tk.LEFT, padx=(0, 12))

        ttk.Button(right, text="Вийти з акаунта", command=self._handle_logout).pack(side=tk.LEFT)

    def _build_tabs(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.catalog_tab: CatalogTab | None = None
        self.pos_tab: PosTab | None = None
        self.customers_tab: CustomersTab | None = None
        self.orders_tab: OrdersTab | None = None
        self.users_tab: UsersTab | None = None

        if self.auth_service.has_permission("catalog.view"):
            self.catalog_tab = CatalogTab(
                self.notebook,
                catalog_service=self.catalog_service,
                auth_service=self.auth_service,
                on_data_changed=self._on_catalog_updated,
            )
            self.notebook.add(self.catalog_tab, text="Каталог книг")

        if self.auth_service.has_permission("pos.checkout"):
            self.pos_tab = PosTab(
                self.notebook,
                pos_service=self.pos_service,
                catalog_service=self.catalog_service,
                auth_service=self.auth_service,
                on_order_completed=self._on_order_completed,
            )
            self.notebook.add(self.pos_tab, text="Каса")

        if self.auth_service.has_permission("customers.view"):
            self.customers_tab = CustomersTab(
                self.notebook,
                customer_service=self.customer_service,
                auth_service=self.auth_service,
            )
            self.notebook.add(self.customers_tab, text="Клієнти")

        if self.auth_service.has_permission("orders.view"):
            self.orders_tab = OrdersTab(
                self.notebook,
                pos_service=self.pos_service,
                auth_service=self.auth_service,
            )
            self.notebook.add(self.orders_tab, text="Чеки та звіти")

        if self.auth_service.has_permission("users.manage"):
            self.users_tab = UsersTab(
                self.notebook,
                auth_service=self.auth_service,
            )
            self.notebook.add(self.users_tab, text="Користувачі")

    def _on_catalog_updated(self) -> None:
        if self.pos_tab is not None:
            self.pos_tab.refresh_catalog()

    def _on_order_completed(self) -> None:
        if self.catalog_tab is not None:
            self.catalog_tab.refresh_books()
        if self.orders_tab is not None:
            self.orders_tab.refresh_data()

    def _handle_logout(self) -> None:
        self.pos_service.clear_cart()
        self.auth_service.logout()
        if self.on_logout:
            self.on_logout()