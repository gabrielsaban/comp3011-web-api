from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import AuthError, AuthUser, decode_access_token
from app.database import get_session

DbSession = Annotated[AsyncSession, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthUser:
    if credentials is None:
        raise AuthError(
            status_code=401,
            code="UNAUTHORIZED",
            message="Missing bearer token.",
        )
    return decode_access_token(credentials.credentials)


def require_editor(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if user.role not in {"editor", "admin"}:
        raise AuthError(
            status_code=403,
            code="FORBIDDEN",
            message="Editor role required.",
        )
    return user


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if user.role != "admin":
        raise AuthError(
            status_code=403,
            code="FORBIDDEN",
            message="Admin role required.",
        )
    return user


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
EditorUser = Annotated[AuthUser, Depends(require_editor)]
AdminUser = Annotated[AuthUser, Depends(require_admin)]
