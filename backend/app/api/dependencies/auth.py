from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.schemas.auth import UserPublic, UserRole


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserPublic:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Debe iniciar sesión para acceder a este recurso.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return request.app.state.auth_service.authenticate_token(credentials.credentials)


def require_roles(*roles: UserRole) -> Callable[[UserPublic], UserPublic]:
    allowed = set(roles)

    def dependency(current_user: UserPublic = Depends(get_current_user)) -> UserPublic:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos suficientes para realizar esta acción.",
            )
        return current_user

    return dependency


require_admin = require_roles(UserRole.admin)
require_operator_or_admin = require_roles(UserRole.admin, UserRole.operator)
