from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Any

from repositories.base import RepositoryError
from services.auth_service import AuthService
from services.catalog_service import CatalogService


class CatalogTab(ttk.Frame):
    """Вкладка каталогу книг, жанрів та контролю складських залишків (відповідає Рисунку 2.5)."""

    def __init__(
        self,
        parent: ttk.Notebook,
        catalog_service: CatalogService,
        auth_service: AuthService,
        on_data_changed: Any = None,
    ) -> None:
        super().__init__(parent, padding=12)
        self.catalog_service = catalog_service
        self.auth_service = auth_service
        self.on_data_changed = on_data_changed

        self.can_manage = self.auth_service.has_permission("catalog.manage")
        self._genre_map: dict[str, int | None] = {}
        self._books_cache: dict[int, dict[str, Any]] = {}
        self._selected_book_id: int | None = None

        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        # Верхня панель пошуку та фільтрації
        filter_bar = ttk.LabelFrame(self, text="Пошук та фільтрація", padding=10)
        filter_bar.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(filter_bar, text="Пошук (назва, автор, ISBN):").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filter_bar, textvariable=self.search_var, width=28)
        search_entry.pack(side=tk.LEFT, padx=(6, 12))
        search_entry.bind("<Return>", lambda _e: self.refresh_books())

        ttk.Label(filter_bar, text="Жанр:").pack(side=tk.LEFT)
        self.filter_genre_var = tk.StringVar(value="Усі жанри")
        self.filter_genre_combo = ttk.Combobox(
            filter_bar,
            textvariable=self.filter_genre_var,
            state="readonly",
            width=22,
        )
        self.filter_genre_combo.pack(side=tk.LEFT, padx=(6, 12))
        self.filter_genre_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_books())

        self.only_in_stock_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            filter_bar,
            text="Лише в наявності",
            variable=self.only_in_stock_var,
            command=self.refresh_books,
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(filter_bar, text="Знайти", command=self.refresh_books).pack(side=tk.LEFT)
        ttk.Button(filter_bar, text="Скинути", command=self._reset_filters).pack(side=tk.LEFT, padx=(6, 0))

        # Основна область: зліва таблиця, справа картка редагування
        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True)

        table_frame = ttk.Frame(body)
        table_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        columns = ("id", "isbn", "title", "author", "genre", "price", "stock", "status")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "id": "ID",
            "isbn": "ISBN",
            "title": "Назва",
            "author": "Автор",
            "genre": "Жанр",
            "price": "Ціна, грн",
            "stock": "Залишок",
            "status": "Статус",
        }
        widths = {
            "id": 45,
            "isbn": 115,
            "title": 210,
            "author": 150,
            "genre": 135,
            "price": 85,
            "stock": 75,
            "status": 105,
        }
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor=tk.W if col in ("title", "author", "genre") else tk.CENTER)

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_select_book)

        # Права панель картки книги
        form_frame = ttk.LabelFrame(body, text="Картка книги", padding=12)
        form_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self.isbn_var = tk.StringVar()
        self.title_var = tk.StringVar()
        self.author_var = tk.StringVar()
        self.form_genre_var = tk.StringVar()
        self.price_var = tk.StringVar(value="0.00")
        self.stock_var = tk.StringVar(value="0")
        self.threshold_var = tk.StringVar(value="3")

        fields = [
            ("ISBN:", self.isbn_var),
            ("Назва:", self.title_var),
            ("Автор:", self.author_var),
        ]
        for idx, (label_text, var) in enumerate(fields):
            ttk.Label(form_frame, text=label_text).grid(row=idx, column=0, sticky=tk.W, pady=(0, 6))
            ttk.Entry(form_frame, textvariable=var, width=26).grid(row=idx, column=1, sticky=tk.EW, pady=(0, 6), padx=(6, 0))

        ttk.Label(form_frame, text="Жанр:").grid(row=3, column=0, sticky=tk.W, pady=(0, 6))
        genre_row = ttk.Frame(form_frame)
        genre_row.grid(row=3, column=1, sticky=tk.EW, pady=(0, 6), padx=(6, 0))
        self.form_genre_combo = ttk.Combobox(genre_row, textvariable=self.form_genre_var, state="readonly", width=18)
        self.form_genre_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        add_genre_btn = ttk.Button(genre_row, text="+", width=3, command=self._on_add_genre)
        add_genre_btn.pack(side=tk.LEFT, padx=(4, 0))
        if not self.can_manage:
            add_genre_btn.state(["disabled"])

        num_fields = [
            ("Ціна (грн):", self.price_var, 4),
            ("Залишок (шт.):", self.stock_var, 5),
            ("Поріг мінімуму:", self.threshold_var, 6),
        ]
        for label_text, var, row_idx in num_fields:
            ttk.Label(form_frame, text=label_text).grid(row=row_idx, column=0, sticky=tk.W, pady=(0, 6))
            ttk.Entry(form_frame, textvariable=var, width=26).grid(row=row_idx, column=1, sticky=tk.EW, pady=(0, 6), padx=(6, 0))

        btn_box = ttk.Frame(form_frame)
        btn_box.grid(row=7, column=0, columnspan=2, sticky=tk.EW, pady=(10, 0))

        self.save_btn = ttk.Button(btn_box, text="Зберегти / Додати", command=self._on_save_book)
        self.save_btn.pack(fill=tk.X, pady=(0, 6))

        self.new_btn = ttk.Button(btn_box, text="Очистити форму", command=self._clear_form)
        self.new_btn.pack(fill=tk.X, pady=(0, 6))

        self.delete_btn = ttk.Button(btn_box, text="Видалити книгу", command=self._on_delete_book)
        self.delete_btn.pack(fill=tk.X)

        if not self.can_manage:
            self.save_btn.state(["disabled"])
            self.delete_btn.state(["disabled"])
            ttk.Label(
                form_frame,
                text="Режим перегляду (зміни доступні менеджеру/адміністратору).",
                foreground="#555555",
                wraplength=230,
            ).grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))

    def _reset_filters(self) -> None:
        self.search_var.set("")
        self.filter_genre_var.set("Усі жанри")
        self.only_in_stock_var.set(False)
        self.refresh_books()

    def refresh_all(self) -> None:
        genres = self.catalog_service.list_genres()
        self._genre_map = {"Без жанру": None}
        filter_values = ["Усі жанри"]
        form_values = ["Без жанру"]

        for g in genres:
            name = str(g["name"])
            gid = int(g["id"])
            self._genre_map[name] = gid
            filter_values.append(name)
            form_values.append(name)

        self.filter_genre_combo["values"] = filter_values
        if self.filter_genre_var.get() not in filter_values:
            self.filter_genre_var.set("Усі жанри")

        self.form_genre_combo["values"] = form_values
        if self.form_genre_var.get() not in form_values:
            self.form_genre_var.set("Без жанру")

        self.refresh_books()

    def refresh_books(self) -> None:
        selected_filter = self.filter_genre_var.get()
        genre_id = None if selected_filter == "Усі жанри" else self._genre_map.get(selected_filter)

        try:
            books = self.catalog_service.search_books(
                query=self.search_var.get(),
                genre_id=genre_id,
                only_in_stock=self.only_in_stock_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("Помилка завантаження", f"Не вдалося отримати каталог: {exc}", parent=self)
            return

        for row_id in self.tree.get_children():
            self.tree.delete(row_id)
        self._books_cache.clear()

        for b in books:
            bid = int(b["id"])
            self._books_cache[bid] = b
            self.tree.insert(
                "",
                tk.END,
                iid=str(bid),
                values=(
                    bid,
                    b["isbn"],
                    b["title"],
                    b["author"],
                    b["genre_name"],
                    f"{float(b['price']):.2f}",
                    b["stock_qty"],
                    b["availability_status"],
                ),
            )

    def _on_select_book(self, _event: Any) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        bid = int(selection[0])
        book = self._books_cache.get(bid)
        if not book:
            return

        self._selected_book_id = bid
        self.isbn_var.set(str(book["isbn"]))
        self.title_var.set(str(book["title"]))
        self.author_var.set(str(book["author"]))
        genre_name = str(book.get("genre_name") or "Без жанру")
        self.form_genre_var.set(genre_name if genre_name in self._genre_map else "Без жанру")
        self.price_var.set(f"{float(book['price']):.2f}")
        self.stock_var.set(str(book["stock_qty"]))
        self.threshold_var.set(str(book.get("low_stock_threshold", 3)))

    def _clear_form(self) -> None:
        self._selected_book_id = None
        self.isbn_var.set("")
        self.title_var.set("")
        self.author_var.set("")
        self.form_genre_var.set("Без жанру")
        self.price_var.set("0.00")
        self.stock_var.set("0")
        self.threshold_var.set("3")
        self.tree.selection_remove(self.tree.selection())

    def _on_add_genre(self) -> None:
        name = simpledialog.askstring("Новий жанр", "Введіть назву жанру:", parent=self)
        if not name:
            return
        try:
            self.catalog_service.add_genre(name)
            self.form_genre_var.set(name.strip())
            self.refresh_all()
            messagebox.showinfo("Успіх", "Жанр додано до довідника.", parent=self)
        except (ValueError, RepositoryError, Exception) as exc:
            messagebox.showerror("Помилка", str(exc), parent=self)

    def _on_save_book(self) -> None:
        genre_id = self._genre_map.get(self.form_genre_var.get())
        try:
            if self._selected_book_id is None:
                new_id = self.catalog_service.create_book(
                    isbn=self.isbn_var.get(),
                    title=self.title_var.get(),
                    author=self.author_var.get(),
                    genre_id=genre_id,
                    price=self.price_var.get(),  # type: ignore[arg-type]
                    stock_qty=self.stock_var.get(),  # type: ignore[arg-type]
                    low_stock_threshold=self.threshold_var.get(),  # type: ignore[arg-type]
                )
                self._selected_book_id = new_id
                messagebox.showinfo("Збережено", "Нову книгу додано до каталогу.", parent=self)
            else:
                self.catalog_service.update_book(
                    book_id=self._selected_book_id,
                    isbn=self.isbn_var.get(),
                    title=self.title_var.get(),
                    author=self.author_var.get(),
                    genre_id=genre_id,
                    price=self.price_var.get(),  # type: ignore[arg-type]
                    stock_qty=self.stock_var.get(),  # type: ignore[arg-type]
                    low_stock_threshold=self.threshold_var.get(),  # type: ignore[arg-type]
                )
                messagebox.showinfo("Оновлено", "Дані книги оновлено.", parent=self)

            self.refresh_books()
            if self.on_data_changed:
                self.on_data_changed()
        except (ValueError, RepositoryError, Exception) as exc:
            messagebox.showerror("Помилка валідації або запису", str(exc), parent=self)

    def _on_delete_book(self) -> None:
        if self._selected_book_id is None:
            messagebox.showwarning("Увага", "Оберіть книгу у списку для видалення.", parent=self)
            return
        confirm = messagebox.askyesno(
            "Підтвердження видалення",
            "Видалити вибрану книгу з каталогу?",
            parent=self,
        )
        if not confirm:
            return
        try:
            self.catalog_service.delete_book(self._selected_book_id)
            self._clear_form()
            self.refresh_books()
            if self.on_data_changed:
                self.on_data_changed()
            messagebox.showinfo("Видалено", "Книгу видалено з каталогу.", parent=self)
        except (ValueError, RepositoryError, Exception) as exc:
            messagebox.showerror("Помилка видалення", str(exc), parent=self)