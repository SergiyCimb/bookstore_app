from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from database.schema import init_db
from repositories.book_repo import BookRepository
from repositories.customer_repo import CustomerRepository
from repositories.order_repo import OrderRepository
from repositories.user_repo import UserRepository
from services.auth_service import AuthService
from services.catalog_service import CatalogService
from services.customer_service import CustomerService
from services.pos_service import PosService
from ui.login_window import LoginWindow
from ui.main_window import MainWindow


class BookstoreApp:
    def __init__(self) -> None:
        init_db()

        book_repo = BookRepository()
        customer_repo = CustomerRepository()
        order_repo = OrderRepository()
        user_repo = UserRepository()

        self.auth_service = AuthService(user_repo=user_repo)
        self.catalog_service = CatalogService(book_repo=book_repo, auth_service=self.auth_service)
        self.customer_service = CustomerService(
            customer_repo=customer_repo, auth_service=self.auth_service
        )
        self.pos_service = PosService(
            order_repo=order_repo,
            book_repo=book_repo,
            customer_repo=customer_repo,
            auth_service=self.auth_service,
        )

        self.root = tk.Tk()
        self.root.title("Книгарня — Автоматизація обліку та продажів")
        self.root.geometry("1120x680")
        self.root.minsize(960, 580)

        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.current_view: MainWindow | None = None
        self.root.withdraw()
        self._show_login_flow()

    def _show_login_flow(self) -> None:
        login_win = LoginWindow(self.root, self.auth_service)
        self.root.wait_window(login_win)

        if login_win.session_user is None:
            self.root.destroy()
            return

        if self.current_view is not None:
            self.current_view.destroy()

        self.current_view = MainWindow(
            root=self.root,
            user=login_win.session_user,
            auth_service=self.auth_service,
            catalog_service=self.catalog_service,
            customer_service=self.customer_service,
            pos_service=self.pos_service,
            on_logout=self._on_logout,
        )
        self.root.deiconify()

    def _on_logout(self) -> None:
        if self.current_view is not None:
            self.current_view.destroy()
            self.current_view = None
        self.root.withdraw()
        self._show_login_flow()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    app = BookstoreApp()
    app.run()