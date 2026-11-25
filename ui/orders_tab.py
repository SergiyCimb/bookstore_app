from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from services.auth_service import AuthError, AuthService
from services.pos_service import PosService


class OrdersTab(ttk.Frame):
    """Вкладка історії замовлень, деталізації чеків та базової звітності з продажів."""

    def __init__(
        self,
        parent: ttk.Notebook,
        pos_service: PosService,
        auth_service: AuthService,
    ) -> None:
        super().__init__(parent, padding=12)
        self.pos_service = pos_service
        self.auth_service = auth_service

        self._build_ui()
        self.refresh_data()

    def _build_ui(self) -> None:
        summary_frame = ttk.LabelFrame(self, text="Зведені показники продажів", padding=10)
        summary_frame.pack(fill=tk.X, pady=(0, 10))

        self.orders_count_var = tk.StringVar(value="Кількість чеків: 0")
        self.total_revenue_var = tk.StringVar(value="Загальна виручка: 0.00 грн")
        self.avg_check_var = tk.StringVar(value="Середній чек: 0.00 грн")

        ttk.Label(summary_frame, textvariable=self.orders_count_var, font=("TkDefaultFont", 10, "bold")).pack(
            side=tk.LEFT, padx=(0, 24)
        )
        ttk.Label(summary_frame, textvariable=self.total_revenue_var, font=("TkDefaultFont", 10, "bold")).pack(
            side=tk.LEFT, padx=(0, 24)
        )
        ttk.Label(summary_frame, textvariable=self.avg_check_var, font=("TkDefaultFont", 10, "bold")).pack(
            side=tk.LEFT
        )
        ttk.Button(summary_frame, text="Оновити", command=self.refresh_data).pack(side=tk.RIGHT)

        pane = ttk.PanedWindow(self, orient=tk.VERTICAL)
        pane.pack(fill=tk.BOTH, expand=True)

        orders_box = ttk.LabelFrame(pane, text="Історія чеків", padding=8)
        pane.add(orders_box, weight=2)

        o_cols = ("id", "created_at", "cashier", "customer", "discount", "total")
        self.orders_tree = ttk.Treeview(orders_box, columns=o_cols, show="headings", selectmode="browse")
        for col, title, w in [
            ("id", "№ чека", 65),
            ("created_at", "Дата і час", 155),
            ("cashier", "Касир", 120),
            ("customer", "Клієнт", 170),
            ("discount", "Знижка, %", 85),
            ("total", "Сума, грн", 100),
        ]:
            self.orders_tree.heading(col, text=title)
            self.orders_tree.column(col, width=w, anchor=tk.W if col in ("cashier", "customer") else tk.CENTER)
        self.orders_tree.pack(fill=tk.BOTH, expand=True)
        self.orders_tree.bind("<<TreeviewSelect>>", self._on_select_order)

        items_box = ttk.LabelFrame(pane, text="Позиції вибраного чека", padding=8)
        pane.add(items_box, weight=1)

        i_cols = ("isbn", "title", "qty", "price", "total")
        self.items_tree = ttk.Treeview(items_box, columns=i_cols, show="headings", selectmode="browse")
        for col, title, w in [
            ("isbn", "ISBN", 120),
            ("title", "Назва книги", 260),
            ("qty", "К-сть", 70),
            ("price", "Ціна, грн", 95),
            ("total", "Сума, грн", 105),
        ]:
            self.items_tree.heading(col, text=title)
            self.items_tree.column(col, width=w, anchor=tk.W if col == "title" else tk.CENTER)
        self.items_tree.pack(fill=tk.BOTH, expand=True)

    def refresh_data(self) -> None:
        try:
            summary = self.pos_service.get_sales_summary()
            orders = self.pos_service.list_orders()
        except AuthError as exc:
            messagebox.showwarning("Обмеження доступу", str(exc), parent=self)
            return

        self.orders_count_var.set(f"Кількість чеків: {int(summary['orders_count'])}")
        self.total_revenue_var.set(f"Загальна виручка: {float(summary['total_revenue']):.2f} грн")
        self.avg_check_var.set(f"Середній чек: {float(summary['avg_check']):.2f} грн")

        for iid in self.orders_tree.get_children():
            self.orders_tree.delete(iid)
        for iid in self.items_tree.get_children():
            self.items_tree.delete(iid)

        for o in orders:
            oid = int(o["id"])
            self.orders_tree.insert(
                "",
                tk.END,
                iid=str(oid),
                values=(
                    oid,
                    o["created_at"],
                    o["cashier_name"],
                    o["customer_name"] or "Роздрібний покупець",
                    f"{float(o['discount_percent']):.1f}",
                    f"{float(o['total_amount']):.2f}",
                ),
            )

    def _on_select_order(self, _e: Any) -> None:
        sel = self.orders_tree.selection()
        if not sel:
            return
        oid = int(sel[0])
        for iid in self.items_tree.get_children():
            self.items_tree.delete(iid)
        try:
            items = self.pos_service.get_order_items(oid)
        except AuthError as exc:
            messagebox.showwarning("Обмеження доступу", str(exc), parent=self)
            return

        for it in items:
            self.items_tree.insert(
                "",
                tk.END,
                values=(
                    it["isbn"],
                    it["title"],
                    it["quantity"],
                    f"{float(it['unit_price']):.2f}",
                    f"{float(it['line_total']):.2f}",
                ),
            )