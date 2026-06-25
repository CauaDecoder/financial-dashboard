from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

T = TypeVar("T")


def record_audit(
    connection: sqlite3.Connection,
    *,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: str | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    origin: str,
    result: str,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_log
            (user_id, action, entity, entity_id, before_json, after_json, origin, result)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            action,
            entity,
            entity_id,
            json.dumps(before, ensure_ascii=True) if before is not None else None,
            json.dumps(after, ensure_ascii=True) if after is not None else None,
            origin,
            result,
        ),
    )
    connection.commit()


def audited_action(*, action: str, entity: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(connection: sqlite3.Connection, *args: Any, **kwargs: Any) -> T:
            actor_user_id = kwargs.get("actor_user_id")
            try:
                result = func(connection, *args, **kwargs)
            except Exception:
                record_audit(
                    connection,
                    user_id=actor_user_id if isinstance(actor_user_id, int) else None,
                    action=action,
                    entity=entity,
                    entity_id=None,
                    before=None,
                    after=None,
                    origin="local",
                    result="failed",
                )
                raise
            record_audit(
                connection,
                user_id=actor_user_id if isinstance(actor_user_id, int) else None,
                action=action,
                entity=entity,
                entity_id=None,
                before=None,
                after=None,
                origin="local",
                result="success",
            )
            return result

        return wrapper

    return decorator
