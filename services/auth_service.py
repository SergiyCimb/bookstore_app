from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from database.schema import verify_password
from repositories.user_repo import UserRepository


class AuthError(Exception):
    """Помилка автентифікації або недостатньо прав доступу."""


@dataclass(frozen=True)
class SessionUser:
    id: int
    username: str
    role: str


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "cashier": {"catalog.view", "pos.checkout", "customers.view", "customers.manage"},
    "manager": {
        "catalog.view",
        "catalog.manage",
        "customers.view",
        "customers.manage",
        "orders.view",
        "reports.view",
    },
    "admin": {
        "catalog.view",
        "catalog.manage",
        "customers.view",
        "customers.manage",
        "orders.view",
        "reports.view",
        "users.manage",
    },
}


class AuthService:
    def __init__(self, user_repo: UserRepository | None = None) -> None:
        self.user_repo = user_repo or UserRepository()
        self.current_user: SessionUser | None = None

    def login(self, username: str, password: str) -> SessionUser:
        clean_username = username.strip()
        if not clean_username or not password:
            raise AuthError("Введіть логін та пароль.")

        user = self.user_repo.get_by_username(clean_username)
        if user is None or not verify_password(password, user["password_hash"]):
            raise AuthError("Невірний логін або пароль.")

        if not bool(user["is_active"]):
            raise AuthError("Обліковий запис деактивовано. Зверніться до адміністратора.")

        session = SessionUser(
            id=int(user["id"]),
            username=str(user["username"]),
            role=str(user["role"]),
        )
        self.current_user = session
        return session

    def logout(self) -> None:
        self.current_user = None

    def has_permission(self, permission: str) -> bool:
        if self.current_user is None:
            return False
        allowed = ROLE_PERMISSIONS.get(self.current_user.role, set())
        return permission in allowed

    def require_permission(self, permission: str) -> None:
        if not self.has_permission(permission):
            raise AuthError(f"Недостатньо прав для виконання операції: {permission}.")

    def _ensure_not_last_active_admin(
        self,
        target_user_id: int,
        future_role: str,
        future_active: bool,
    ) -> None:
        target = self.user_repo.get_by_id(target_user_id)
        if target is None:
            raise ValueError("Вибраного користувача не знайдено.")

        was_active_admin = target["role"] == "admin" and bool(target["is_active"])
        will_stay_active_admin = future_role == "admin" and future_active

        if was_active_admin and not will_stay_active_admin:
            other_active_admins = [
                u
                for u in self.user_repo.list_users()
                if int(u["id"]) != int(target_user_id)
                and u["role"] == "admin"
                and bool(u["is_active"])
            ]
            if not other_active_admins:
                raise ValueError("У системі повинен залишатися хоча б один активний адміністратор.")

    def list_users(self) -> list[dict[str, Any]]:
        self.require_permission("users.manage")
        return self.user_repo.list_users()

    def create_user(self, username: str, password: str, role: str, is_active: bool = True) -> int:
        self.require_permission("users.manage")
        clean_username = username.strip()
        if len(clean_username) < 3:
            raise ValueError("Логін повинен містити щонайменше 3 символи.")
        if len(password) < 6:
            raise ValueError("Пароль повинен містити щонайменше 6 символів.")
        if role not in ROLE_PERMISSIONS:
            raise ValueError("Некоректна роль користувача.")
        return self.user_repo.create_user(clean_username, password, role, is_active=is_active)

    def update_user(
        self,
        user_id: int,
        username: str,
        role: str,
        is_active: bool,
        new_password: str = "",
    ) -> None:
        self.require_permission("users.manage")
        clean_username = username.strip()
        if len(clean_username) < 3:
            raise ValueError("Логін повинен містити щонайменше 3 символи.")
        if role not in ROLE_PERMISSIONS:
            raise ValueError("Некоректна роль користувача.")

        if self.current_user is not None and self.current_user.id == int(user_id):
            if not is_active:
                raise ValueError("Неможливо деактивувати власний активний обліковий запис.")
            if role != self.current_user.role:
                raise ValueError("Неможливо змінити роль власного поточного сеансу.")

        self._ensure_not_last_active_admin(user_id, role, is_active)

        password_to_set: str | None = None
        if new_password:
            if len(new_password) < 6:
                raise ValueError("Новий пароль повинен містити щонайменше 6 символів.")
            password_to_set = new_password

        self.user_repo.update_user(
            user_id=user_id,
            username=clean_username,
            role=role,
            is_active=is_active,
            new_password=password_to_set,
        )

    def set_user_active(self, user_id: int, is_active: bool) -> None:
        self.require_permission("users.manage")
        if self.current_user is not None and self.current_user.id == int(user_id) and not is_active:
            raise ValueError("Неможливо деактивувати власний активний обліковий запис.")
        self._ensure_not_last_active_admin(
            user_id,
            future_role="admin" if is_active else "",
            future_active=is_active,
        )
        self.user_repo.set_user_active(user_id, is_active)

    def delete_user(self, user_id: int) -> None:
        self.require_permission("users.manage")
        if self.current_user is not None and self.current_user.id == int(user_id):
            raise ValueError("Неможливо видалити обліковий запис, під яким виконано вхід.")

        self._ensure_not_last_active_admin(user_id, future_role="", future_active=False)
        self.user_repo.delete_user(user_id)