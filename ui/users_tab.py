from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from repositories.base import RepositoryError
from services.auth_service import AuthError, AuthService


class UsersTab(ttk.Frame):
    """Вкладка адміністрування облікових записів користувачів (роль admin)."""

    def __init__(self, parent: ttk.Notebook, auth_service: AuthService) -> None:
        super().__init__(parent, padding=12)
        self.auth_service = auth_service
        self._selected_id: int | None = None
        self._users_cache: dict[int, dict[str, Any]] = {}

        self._build_ui()
        self.refresh_users()

    def _build_ui(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(top, text="Оновити список", command=self.refresh_users).pack(side=tk.LEFT)

        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True)

        cols = ("id", "username", "role", "status")
        self.tree = ttk.Treeview(body, columns=cols, show="headings", selectmode="browse")
        for col, title, w in [
            ("id", "ID", 45),
            ("username", "Логін", 180),
            ("role", "Роль", 120),
            ("status", "Стан", 110),
        ]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=w, anchor=tk.CENTER)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        self.tree.bind("<<TreeviewSelect>>", self._on_select_user)

        form = ttk.LabelFrame(body, text="Картка користувача", padding=12)
        form.pack(side=tk.RIGHT, fill=tk.Y)

        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.role_var = tk.StringVar(value="cashier")
        self.active_var = tk.BooleanVar(value=True)

        ttk.Label(form, text="Логін:").grid(row=0, column=0, sticky=tk.W, pady=(0, 6))
        ttk.Entry(form, textvariable=self.username_var, width=22).grid(
            row=0, column=1, pady=(0, 6), padx=(6, 0)
        )

        self.password_label_var = tk.StringVar(value="Пароль:")
        ttk.Label(form, textvariable=self.password_label_var).grid(row=1, column=0, sticky=tk.W, pady=(0, 6))
        ttk.Entry(form, textvariable=self.password_var, show="•", width=22).grid(
            row=1, column=1, pady=(0, 6), padx=(6, 0)
        )

        ttk.Label(form, text="Роль:").grid(row=2, column=0, sticky=tk.W, pady=(0, 6))
        ttk.Combobox(
            form,
            textvariable=self.role_var,
            values=["cashier", "manager", "admin"],
            state="readonly",
            width=20,
        ).grid(row=2, column=1, pady=(0, 6), padx=(6, 0))

        ttk.Checkbutton(form, text="Обліковий запис активний", variable=self.active_var).grid(
            row=3, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )

        self.save_btn = ttk.Button(form, text="Створити користувача", command=self._on_save_user)
        self.save_btn.grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=(0, 6))

        ttk.Button(form, text="Очистити форму", command=self._clear_form).grid(
            row=5, column=0, columnspan=2, sticky=tk.EW, pady=(0, 6)
        )

        self.delete_btn = ttk.Button(form, text="Видалити користувача", command=self._on_delete_user)
        self.delete_btn.grid(row=6, column=0, columnspan=2, sticky=tk.EW)
        self.delete_btn.state(["disabled"])

    def refresh_users(self) -> None:
        try:
            users = self.auth_service.list_users()
        except AuthError as exc:
            messagebox.showwarning("Доступ заборонено", str(exc), parent=self)
            return

        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._users_cache.clear()

        for u in users:
            uid = int(u["id"])
            self._users_cache[uid] = u
            status_text = "Активний" if int(u["is_active"]) == 1 else "Заблокований"
            self.tree.insert("", tk.END, iid=str(uid), values=(uid, u["username"], u["role"], status_text))

    def _on_select_user(self, _e: Any) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        uid = int(sel[0])
        user = self._users_cache.get(uid)
        if not user:
            return

        self._selected_id = uid
        self.username_var.set(str(user["username"]))
        self.password_var.set("")
        self.role_var.set(str(user["role"]))
        self.active_var.set(bool(int(user["is_active"])))
        self.password_label_var.set("Новий пароль:")
        self.save_btn.configure(text="Зберегти зміни")
        self.delete_btn.state(["!disabled"])

    def _clear_form(self) -> None:
        self._selected_id = None
        self.username_var.set("")
        self.password_var.set("")
        self.role_var.set("cashier")
        self.active_var.set(True)
        self.password_label_var.set("Пароль:")
        self.save_btn.configure(text="Створити користувача")
        self.delete_btn.state(["disabled"])
        self.tree.selection_remove(self.tree.selection())

    def _on_save_user(self) -> None:
        try:
            if self._selected_id is None:
                self.auth_service.create_user(
                    username=self.username_var.get(),
                    password=self.password_var.get(),
                    role=self.role_var.get(),
                    is_active=self.active_var.get(),
                )
                self._clear_form()
                self.refresh_users()
                messagebox.showinfo("Успіх", "Обліковий запис створено.", parent=self)
            else:
                self.auth_service.update_user(
                    user_id=self._selected_id,
                    username=self.username_var.get(),
                    role=self.role_var.get(),
                    is_active=self.active_var.get(),
                    new_password=self.password_var.get(),
                )
                self._clear_form()
                self.refresh_users()
                messagebox.showinfo("Успіх", "Дані користувача оновлено.", parent=self)
        except (ValueError, AuthError, RepositoryError, Exception) as exc:
            messagebox.showerror("Помилка", str(exc), parent=self)

    def _on_delete_user(self) -> None:
        if self._selected_id is None:
            messagebox.showwarning("Увага", "Оберіть користувача у списку.", parent=self)
            return

        user = self._users_cache.get(self._selected_id)
        username = str(user["username"]) if user else f"ID {self._selected_id}"
        confirm = messagebox.askyesno(
            "Підтвердження видалення",
            f"Видалити користувача «{username}»?",
            parent=self,
        )
        if not confirm:
            return

        try:
            self.auth_service.delete_user(self._selected_id)
            self._clear_form()
            self.refresh_users()
            messagebox.showinfo("Видалено", "Обліковий запис видалено.", parent=self)
        except (ValueError, AuthError, RepositoryError, Exception) as exc:
            messagebox.showerror("Помилка видалення", str(exc), parent=self)