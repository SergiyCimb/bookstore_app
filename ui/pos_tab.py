from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from repositories.base import RepositoryError
from services.auth_service import AuthService
from services.catalog_service import CatalogService
from services.pos_service import PosService


class PosTab(ttk.Frame):
    """Вкладка каси: підбір книг, клієнт зі знижкою, кошик і проведення чека (відповідає Рисунку 2.6)."""

    def __init__(
        self,
        parent: ttk.Notebook,
        pos_service: PosService,
        catalog_service: CatalogService,
        auth_service: AuthService,
        on_order_completed: Any = None,
    ) -> None:
        super().__init__(parent, padding=12)
        self.pos_service = pos_service
        self.catalog_service = catalog_service
        self.auth_service = auth_service
        self.on_order_completed = on_order_completed

        self.can_checkout = self.auth_service.has_permission("pos.checkout")
        self._catalog_map: dict[int, dict[str, Any]] = {}

        self._build_ui()
        self.refresh_catalog()
        self._refresh_cart_ui()

    def _build_ui(self) -> None:
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # Ліва частина: пошук та каталог доступних книг
        left_frame = ttk.LabelFrame(main_pane, text="Каталог книг для продажу", padding=10)
        main_pane.add(left_frame, weight=3)

        search_row = ttk.Frame(left_frame)
        search_row.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(search_row, text="Пошук / Штрих-код / ISBN:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_row, textvariable=self.search_var, width=26)
        search_entry.pack(side=tk.LEFT, padx=(6, 8))
        search_entry.bind("<Return>", lambda _e: self.refresh_catalog())
        ttk.Button(search_row, text="Знайти", command=self.refresh_catalog).pack(side=tk.LEFT)

        cols = ("id", "isbn", "title", "price", "stock", "status")
        self.catalog_tree = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="browse")
        headers = {
            "id": "ID",
            "isbn": "ISBN",
            "title": "Назва книги",
            "price": "Ціна",
            "stock": "Залишок",
            "status": "Статус",
        }
        widths = {"id": 40, "isbn": 110, "title": 230, "price": 80, "stock": 70, "status": 105}
        for c in cols:
            self.catalog_tree.heading(c, text=headers[c])
            self.catalog_tree.column(c, width=widths[c], anchor=tk.W if c == "title" else tk.CENTER)

        self.catalog_tree.pack(fill=tk.BOTH, expand=True)
        self.catalog_tree.bind("<Double-1>", lambda _e: self._on_add_to_cart())

        add_bar = ttk.Frame(left_frame)
        add_bar.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(add_bar, text="Кількість:").pack(side=tk.LEFT)
        self.qty_var = tk.StringVar(value="1")
        ttk.Entry(add_bar, textvariable=self.qty_var, width=6).pack(side=tk.LEFT, padx=(6, 10))

        self.add_btn = ttk.Button(add_bar, text="Додати до кошика", command=self._on_add_to_cart)
        self.add_btn.pack(side=tk.LEFT)
        if not self.can_checkout:
            self.add_btn.state(["disabled"])

        # Права частина: клієнт, кошик та підсумок чека
        right_frame = ttk.Frame(main_pane, padding=(10, 0, 0, 0))
        main_pane.add(right_frame, weight=2)

        customer_box = ttk.LabelFrame(right_frame, text="Постійний клієнт та знижка", padding=10)
        customer_box.pack(fill=tk.X, pady=(0, 8))

        c_row = ttk.Frame(customer_box)
        c_row.pack(fill=tk.X)

        ttk.Label(c_row, text="Телефон:").pack(side=tk.LEFT)
        self.phone_var = tk.StringVar()
        phone_entry = ttk.Entry(c_row, textvariable=self.phone_var, width=18)
        phone_entry.pack(side=tk.LEFT, padx=(6, 6))
        phone_entry.bind("<Return>", lambda _e: self._on_attach_customer())

        ttk.Button(c_row, text="Застосувати", command=self._on_attach_customer).pack(side=tk.LEFT)
        ttk.Button(c_row, text="Скинути", command=self._on_clear_customer).pack(side=tk.LEFT, padx=(4, 0))

        self.customer_info_var = tk.StringVar(value="Клієнт не обраний (знижка 0%)")
        ttk.Label(customer_box, textvariable=self.customer_info_var, foreground="#2b4c7e").pack(
            anchor=tk.W, pady=(6, 0)
        )

        cart_box = ttk.LabelFrame(right_frame, text="Кошик покупки", padding=10)
        cart_box.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        cart_cols = ("book_id", "title", "qty", "price", "total")
        self.cart_tree = ttk.Treeview(cart_box, columns=cart_cols, show="headings", selectmode="browse")
        c_headers = {"book_id": "ID", "title": "Книга", "qty": "К-сть", "price": "Ціна", "total": "Сума"}
        c_widths = {"book_id": 40, "title": 165, "qty": 55, "price": 75, "total": 85}
        for c in cart_cols:
            self.cart_tree.heading(c, text=c_headers[c])
            self.cart_tree.column(c, width=c_widths[c], anchor=tk.W if c == "title" else tk.CENTER)

        self.cart_tree.pack(fill=tk.BOTH, expand=True)
        ttk.Button(cart_box, text="Видалити позицію з кошика", command=self._on_remove_item).pack(
            anchor=tk.E, pady=(6, 0)
        )

        summary_box = ttk.LabelFrame(right_frame, text="Підсумок чека", padding=10)
        summary_box.pack(fill=tk.X)

        self.subtotal_var = tk.StringVar(value="Проміжна сума: 0.00 грн")
        self.discount_var = tk.StringVar(value="Знижка: 0.00 грн (0.0%)")
        self.total_var = tk.StringVar(value="До сплати: 0.00 грн")

        ttk.Label(summary_box, textvariable=self.subtotal_var).pack(anchor=tk.W)
        ttk.Label(summary_box, textvariable=self.discount_var).pack(anchor=tk.W, pady=(2, 4))
        ttk.Label(summary_box, textvariable=self.total_var, font=("TkDefaultFont", 11, "bold")).pack(
            anchor=tk.W, pady=(0, 8)
        )

        self.checkout_btn = ttk.Button(summary_box, text="Провести продаж", command=self._on_checkout)
        self.checkout_btn.pack(fill=tk.X)
        if not self.can_checkout:
            self.checkout_btn.state(["disabled"])

    def refresh_catalog(self) -> None:
        books = self.catalog_service.search_books(query=self.search_var.get())
        for row_id in self.catalog_tree.get_children():
            self.catalog_tree.delete(row_id)
        self._catalog_map.clear()

        for b in books:
            bid = int(b["id"])
            self._catalog_map[bid] = b
            self.catalog_tree.insert(
                "",
                tk.END,
                iid=str(bid),
                values=(
                    bid,
                    b["isbn"],
                    b["title"],
                    f"{float(b['price']):.2f}",
                    b["stock_qty"],
                    b["availability_status"],
                ),
            )

    def _on_add_to_cart(self) -> None:
        selection = self.catalog_tree.selection()
        if not selection:
            messagebox.showwarning("Увага", "Оберіть книгу в каталозі.", parent=self)
            return
        book_id = int(selection[0])
        try:
            qty = int(self.qty_var.get())
            self.pos_service.add_to_cart(book_id=book_id, quantity=qty)
            self._refresh_cart_ui()
        except ValueError as exc:
            messagebox.showerror("Неможливо додати до кошика", str(exc), parent=self)

    def _on_remove_item(self) -> None:
        selection = self.cart_tree.selection()
        if not selection:
            return
        self.pos_service.remove_from_cart(int(selection[0]))
        self._refresh_cart_ui()

    def _on_attach_customer(self) -> None:
        try:
            customer = self.pos_service.attach_customer_by_phone(self.phone_var.get())
            self.customer_info_var.set(
                f"{customer['full_name']} ({customer['phone']}) — знижка {float(customer['discount_percent']):.1f}%"
            )
            self._refresh_cart_ui()
        except ValueError as exc:
            messagebox.showwarning("Клієнта не знайдено", str(exc), parent=self)

    def _on_clear_customer(self) -> None:
        self.pos_service.clear_customer()
        self.phone_var.set("")
        self.customer_info_var.set("Клієнт не обраний (знижка 0%)")
        self._refresh_cart_ui()

    def _refresh_cart_ui(self) -> None:
        for row_id in self.cart_tree.get_children():
            self.cart_tree.delete(row_id)

        for item in self.pos_service.get_cart_items():
            self.cart_tree.insert(
                "",
                tk.END,
                iid=str(item.book_id),
                values=(
                    item.book_id,
                    item.title,
                    item.quantity,
                    f"{item.unit_price:.2f}",
                    f"{item.line_total:.2f}",
                ),
            )

        totals = self.pos_service.get_totals()
        customer = totals["customer"]
        if customer is None:
            self.customer_info_var.set("Клієнт не обраний (знижка 0%)")
        else:
            self.customer_info_var.set(
                f"{customer['full_name']} ({customer['phone']}) — знижка {float(customer['discount_percent']):.1f}%"
            )

        self.subtotal_var.set(f"Проміжна сума: {totals['subtotal']:.2f} грн")
        self.discount_var.set(
            f"Знижка: {totals['discount_amount']:.2f} грн ({totals['discount_percent']:.1f}%)"
        )
        self.total_var.set(f"До сплати: {totals['total_amount']:.2f} грн")

    def _on_checkout(self) -> None:
        try:
            order_id = self.pos_service.checkout()
            self.phone_var.set("")
            self.qty_var.set("1")
            self._refresh_cart_ui()
            self.refresh_catalog()
            if self.on_order_completed:
                self.on_order_completed()
            messagebox.showinfo(
                "Продаж проведено",
                f"Чек №{order_id} успішно проведено, складські залишки оновлено.",
                parent=self,
            )
        except (ValueError, RepositoryError, Exception) as exc:
            messagebox.showerror("Помилка проведення продажу", str(exc), parent=self)