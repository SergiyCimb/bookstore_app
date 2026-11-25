from __future__ import annotations

from database.schema import get_connection, init_db
from repositories.book_repo import BookRepository
from repositories.customer_repo import CustomerRepository
from repositories.order_repo import OrderRepository
from repositories.user_repo import UserRepository


def seed_demo_data(reset_existing: bool = True) -> None:
    init_db()

    if reset_existing:
        with get_connection() as conn:
            conn.executescript(
                """
                DELETE FROM order_items;
                DELETE FROM orders;
                DELETE FROM books;
                DELETE FROM customers;
                DELETE FROM genres;
                DELETE FROM users;
                DELETE FROM sqlite_sequence;
                """
            )
            conn.commit()
        # Повторно викликаємо init_db(), щоб відновити базові жанри та стартового admin
        init_db()

    user_repo = UserRepository()
    book_repo = BookRepository()
    customer_repo = CustomerRepository()
    order_repo = OrderRepository()

    # 1. Користувачі (admin уже є після init_db() з паролем admin123)
    admin_row = user_repo.get_by_username("admin")
    admin_id = int(admin_row["id"]) if admin_row else 1

    manager_id = user_repo.create_user("manager", "manager123", "manager", is_active=True)
    cashier_id = user_repo.create_user("cashier", "cashier123", "cashier", is_active=True)
    user_repo.create_user("cashier_blocked", "cashier123", "cashier", is_active=False)

    # 2. Жанри (додаємо кілька додаткових до базових)
    genres = {g["name"]: int(g["id"]) for g in book_repo.list_genres()}
    for extra_genre in ["Історія", "Психологія", "Бізнес"]:
        if extra_genre not in genres:
            genres[extra_genre] = book_repo.add_genre(extra_genre)

    # 3. Книги з різними залишками (поріг за замовчуванням = 3:
    # > 3 -> "В наявності", 1..3 -> "Закінчується", 0 -> "Розпродано")
    b1 = book_repo.create_book(
        isbn="978-966-03-8412-1",
        title="Чистий код. Створення і рефакторинг",
        author="Роберт Мартін",
        genre_id=genres.get("Програмування"),
        price=680.00,
        stock_qty=12,
        low_stock_threshold=3,
    )
    b2 = book_repo.create_book(
        isbn="978-617-12-9045-8",
        title="Дюна",
        author="Френк Герберт",
        genre_id=genres.get("Фантастика"),
        price=520.00,
        stock_qty=2,
        low_stock_threshold=3,
    )
    b3 = book_repo.create_book(
        isbn="978-966-14-5521-4",
        title="Тіні забутих предків",
        author="Михайло Коцюбинський",
        genre_id=genres.get("Художня література"),
        price=290.00,
        stock_qty=0,
        low_stock_threshold=3,
    )
    b4 = book_repo.create_book(
        isbn="978-617-78-3109-2",
        title="Мислення, швидке й повільне",
        author="Даніель Канеман",
        genre_id=genres.get("Психологія"),
        price=610.00,
        stock_qty=7,
        low_stock_threshold=3,
    )
    b5 = book_repo.create_book(
        isbn="978-966-94-2018-6",
        title="Історія України: від давнини до сучасності",
        author="Олексій Гарань",
        genre_id=genres.get("Історія"),
        price=450.00,
        stock_qty=1,
        low_stock_threshold=3,
    )

    # 4. Постійні клієнти зі знижками
    c1 = customer_repo.create_customer("Олена Коваленко", "+380501234567", 5.0)
    c2 = customer_repo.create_customer("Андрій Мельник", "+380679876543", 10.0)
    customer_repo.create_customer("Ірина Шевченко", "+380935551122", 0.0)

    # 5. Кілька проведених чеків (атомарно списують залишки та формують звіти)
    order_repo.create_order_atomic(
        cashier_id=cashier_id,
        customer_id=c1,
        discount_percent=5.0,
        items=[
            {"book_id": b1, "quantity": 1, "unit_price": 680.00},
            {"book_id": b4, "quantity": 1, "unit_price": 610.00},
        ],
    )
    order_repo.create_order_atomic(
        cashier_id=cashier_id,
        customer_id=c2,
        discount_percent=10.0,
        items=[
            {"book_id": b2, "quantity": 1, "unit_price": 520.00},
        ],
    )
    order_repo.create_order_atomic(
        cashier_id=admin_id,
        customer_id=None,
        discount_percent=0.0,
        items=[
            {"book_id": b5, "quantity": 1, "unit_price": 450.00},
        ],
    )

    print("Тестову базу даних успішно заповнено!")
    print("Облікові записи для перевірки ролей:")
    print("  - admin / admin123 (адміністратор)")
    print("  - manager / manager123 (менеджер)")
    print("  - cashier / cashier123 (касир)")
    print("  - cashier_blocked / cashier123 (заблокований акаунт)")


if __name__ == "__main__":
    seed_demo_data(reset_existing=True)