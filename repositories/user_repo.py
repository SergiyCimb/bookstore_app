from __future__ import annotations

from typing import Any

from database.schema import hash_password
from repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def get_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, username, password_hash, role, is_active
                FROM users
                WHERE id = ?;
                """,
                (int(user_id),),
            ).fetchone()
            return dict(row) if row else None

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, username, password_hash, role, is_active
                FROM users
                WHERE username = ?;
                """,
                (username.strip(),),
            ).fetchone()
            return dict(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, username, role, is_active FROM users ORDER BY id;"
            ).fetchall()
            return [dict(row) for row in rows]

    def create_user(self, username: str, password: str, role: str, is_active: bool = True) -> int:
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO users (username, password_hash, role, is_active)
                VALUES (?, ?, ?, ?);
                """,
                (username.strip(), hash_password(password), role, 1 if is_active else 0),
            )
            return int(cursor.lastrowid)

    def update_user(
        self,
        user_id: int,
        username: str,
        role: str,
        is_active: bool,
        new_password: str | None = None,
    ) -> None:
        with self.transaction() as conn:
            if new_password:
                conn.execute(
                    """
                    UPDATE users
                    SET username = ?, password_hash = ?, role = ?, is_active = ?
                    WHERE id = ?;
                    """,
                    (
                        username.strip(),
                        hash_password(new_password),
                        role,
                        1 if is_active else 0,
                        int(user_id),
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE users
                    SET username = ?, role = ?, is_active = ?
                    WHERE id = ?;
                    """,
                    (
                        username.strip(),
                        role,
                        1 if is_active else 0,
                        int(user_id),
                    ),
                )

    def set_user_active(self, user_id: int, is_active: bool) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE users SET is_active = ? WHERE id = ?;",
                (1 if is_active else 0, int(user_id)),
            )

    def delete_user(self, user_id: int) -> None:
        with self.transaction() as conn:
            conn.execute("DELETE FROM users WHERE id = ?;", (int(user_id),))