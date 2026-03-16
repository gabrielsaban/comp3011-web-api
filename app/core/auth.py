from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

import jwt
from fastapi import HTTPException
from jwt import ExpiredSignatureError, InvalidTokenError

from app.config import settings

Role = Literal["editor", "admin"]


@dataclass(frozen=True, slots=True)
class AuthUser:
    sub: str
    role: Role


class AuthError(HTTPException):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
        super().__init__(status_code=status_code, detail=message, headers=headers)
        self.code = code
        self.message = message


def create_access_token(
    subject: str,
    role: Role,
    expires_minutes: int | None = None,
) -> str:
    ttl_minutes = expires_minutes if expires_minutes is not None else settings.jwt_expire_minutes
    expires_at = datetime.now(UTC) + timedelta(minutes=ttl_minutes)
    payload = {"sub": subject, "role": role, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> AuthUser:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "role", "exp"]},
        )
    except ExpiredSignatureError as exc:
        raise AuthError(
            status_code=401,
            code="UNAUTHORIZED",
            message="Token has expired.",
        ) from exc
    except InvalidTokenError as exc:
        raise AuthError(
            status_code=401,
            code="UNAUTHORIZED",
            message="Invalid authentication token.",
        ) from exc

    subject = payload.get("sub")
    role = payload.get("role")
    if not isinstance(subject, str):
        raise AuthError(
            status_code=401,
            code="UNAUTHORIZED",
            message="Invalid token subject.",
        )
    if role not in {"editor", "admin"}:
        raise AuthError(
            status_code=401,
            code="UNAUTHORIZED",
            message="Invalid token role.",
        )

    return AuthUser(sub=subject, role=cast(Role, role))
