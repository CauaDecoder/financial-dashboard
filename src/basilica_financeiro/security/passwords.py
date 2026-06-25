from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def hash_password(password: str) -> str:
    """Hash a password with Argon2id."""
    if len(password) < 10:
        raise ValueError("A senha precisa ter pelo menos 10 caracteres")
    return _HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a password against an Argon2id hash."""
    try:
        return _HASHER.verify(password_hash, password)
    except VerifyMismatchError:
        return False
