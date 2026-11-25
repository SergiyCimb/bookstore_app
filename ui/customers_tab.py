from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from repositories.base import RepositoryError
from services.auth_service import AuthService
from services.customer_service import CustomerService


class CustomersTab(ttk.Frame):
    """Вкладка обліку постійних клієнтів та персональних знижок."""

    def __init__(
        self,
        parent: ttk.Notebook,
        customer_service: CustomerService,
        auth_service: AuthService,
    ) -> None:
        super().__init__(parent, padding=12)
        self.customer_service = customer_service
        self.auth_service = auth_service
        self.can_manage = self.auth_service.has_permission("customers.manage")
        self._selected_id: int | None = None
        self._cache: dict[int, dict[str, Any]] = {}

        self._build_ui()
        self.refresh_customers()

    def _build_ui(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(top, text="Пошук (ПІБ або телефон):").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.search_var, width=28)
        entry.pack(side=tk.LEFT, padx=(6, 8))
        entry.bind("<Return>", lambda _e: self.refresh_customers())
        ttk.Button(top, text="Знайти", command=self.refresh_customers).pack(side=tk.LEFT)

        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True)

        cols = ("id", "full_name", "phone", "discount")
        self.tree = ttk.Treeview(body, columns=cols, show="headings", selectmode="browse")
        for col, title, w in [
            ("id", "ID", 45),
            ("full_name", "ПІБ клієнта", 240),
            ("phone", "Телефон", 140),
            ("discount", "Знижка, %", 100),
        ]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=w, anchor=tk.W if col == "full_name" else tk.CENTER)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        form = ttk.LabelFrame(body, text="Картка клієнта", padding=12)
        form.pack(side=tk.RIGHT, fill=tk.Y)

        self.name_var = tk.StringVar()
        self.phone_var = tk.StringVar()
        self.discount_var = tk.StringVar(value="0.0")

        ttk.Label(form, text="ПІБ:").grid(row=0, column=0, sticky=tk.W, pady=(0, 6))
        ttk.Entry(form, textvariable=self.name_var, width=24).grid(row=0, column=1, pady=(0, 6), padx=(6, 0))

        ttk.Label(form, text="Телефон:").grid(row=1, column=0, sticky=tk.W, pady=(0, 6))
        ttk.Entry(form, textvariable=self.phone_var, width=24).grid(row=1, column=1, pady=(0, 6), padx=(6, 0))

        ttk.Label(form, text="Знижка (%):").grid(row=2, column=0, sticky=tk.W, pady=(0, 10))
        ttk.Entry(form, textvariable=self.discount_var, width=24).grid(row=2, column=1, pady=(0, 10), padx=(6, 0))

        self.save_btn = ttk.Button(form, text="Зберегти клієнта", command=self._on_save)
        self.save_btn.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=(0, 6))

        ttk.Button(form, text="Новий клієнт", command=self._clear).grid(
            row=4, column=0, columnspan=2, sticky=tk.EW
        )
        if not self.can_manage:
            self.save_btn.state(["disabled"])

    def refresh_customers(self) -> None:
        rows = self.customer_service.list_customers(self.search_var.get())
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._cache.clear()

        for r in rows:
            cid = int(r["id"])
            self._cache[cid] = r
            self.tree.insert(
                "",
                tk.END,
                iid=str(cid),
                values=(cid, r["full_name"], r["phone"], f"{float(r['discount_percent']):.1f}"),
            )

    def _on_select(self, _e: Any) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        cust = self._cache.get(int(sel[0]))
        if not cust:
            return
        self._selected_id = int(cust["id"])
        self.name_var.set(str(cust["full_name"]))
        self.phone_var.set(str(cust["phone"]))
        self.discount_var.set(f"{float(cust['discount_percent']):.1f}")

    def _clear(self) -> None:
        self._selected_id = None
        self.name_var.set("")
        self.phone_var.set("")
        self.discount_var.set("0.0")
        self.tree.selection_remove(self.tree.selection())

    def _on_save(self) -> None:
        try:
            if self._selected_id is None:
                self.customer_service.create_customer(
                    self.name_var.get(),
                    self.phone_var.get(),
                    self.discount_var.get(),  # type: ignore[arg-type]
                )
            else:
                self.customer_service.update_customer(
                    self._selected_id,
                    self.name_var.get(),
                    self.phone_var.get(),
                    self.discount_var.get(),  # type: ignore[arg-type]
                )
            self._clear()
            self.refresh_customers()
            messagebox.showinfo("Збережено", "Дані клієнта збережено.", parent=self)
        except (ValueError, RepositoryError, Exception) as exc:
            messagebox.showerror("Помилка", str(exc), parent=self)