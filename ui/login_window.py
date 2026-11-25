from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from services.auth_service import AuthError, AuthService, SessionUser


class LoginWindow(tk.Toplevel):
    """Вікно входу користувача в систему (відповідає Рисунку 2.7)."""

    def __init__(self, parent: tk.Tk, auth_service: AuthService) -> None:
        super().__init__(parent)
        self.auth_service = auth_service
        self.session_user: SessionUser | None = None

        self.title("Вхід до системи — Книгарня")
        self.resizable(False, False)

        self._build_ui()
        self._center_window(380, 230)
        self.deiconify()
        self.lift()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
        self.username_entry.focus_set()

    def _center_window(self, width: int, height: int) -> None:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=20)
        container.pack(fill=tk.BOTH, expand=True)

        title_lbl = ttk.Label(
            container,
            text="Автентифікація користувача",
            font=("TkDefaultFont", 13, "bold"),
        )
        title_lbl.pack(anchor=tk.W, pady=(0, 12))

        form = ttk.Frame(container)
        form.pack(fill=tk.X)

        ttk.Label(form, text="Логін:").grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        self.username_var = tk.StringVar()
        self.username_entry = ttk.Entry(form, textvariable=self.username_var, width=28)
        self.username_entry.grid(row=0, column=1, sticky=tk.EW, pady=(0, 8), padx=(8, 0))
        self.username_entry.bind("<Return>", lambda _e: self.password_entry.focus_set())

        ttk.Label(form, text="Пароль:").grid(row=1, column=0, sticky=tk.W, pady=(0, 12))
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(form, textvariable=self.password_var, show="•", width=28)
        self.password_entry.grid(row=1, column=1, sticky=tk.EW, pady=(0, 12), padx=(8, 0))
        self.password_entry.bind("<Return>", lambda _e: self._on_login())

        form.columnconfigure(1, weight=1)

        btns = ttk.Frame(container)
        btns.pack(fill=tk.X, pady=(6, 0))

        cancel_btn = ttk.Button(btns, text="Вихід", command=self._on_cancel)
        cancel_btn.pack(side=tk.RIGHT)

        login_btn = ttk.Button(btns, text="Увійти", command=self._on_login)
        login_btn.pack(side=tk.RIGHT, padx=(0, 8))

    def _on_login(self) -> None:
        try:
            user = self.auth_service.login(
                self.username_var.get(),
                self.password_var.get(),
            )
        except AuthError as exc:
            messagebox.showerror("Помилка входу", str(exc), parent=self)
            self.password_var.set("")
            self.password_entry.focus_set()
            return
        except Exception as exc:
            messagebox.showerror("Системна помилка", f"Не вдалося виконати вхід: {exc}", parent=self)
            return

        self.session_user = user
        self.grab_release()
        self.destroy()

    def _on_cancel(self) -> None:
        self.session_user = None
        self.grab_release()
        self.destroy()