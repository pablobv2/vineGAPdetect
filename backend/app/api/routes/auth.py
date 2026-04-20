from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.api.dependencies.auth import bearer_scheme, get_current_user
from app.schemas.auth import LoginRequest, MessageResponse, SessionResponse, UserPublic

router = APIRouter()


@router.post("/login", response_model=SessionResponse)
def login(request: Request, payload: LoginRequest) -> SessionResponse:
    token, expires_at, user = request.app.state.auth_service.login(payload.username, payload.password)
    return SessionResponse(access_token=token, expires_at=expires_at, user=user)


@router.get("/me", response_model=UserPublic)
def me(current_user: UserPublic = Depends(get_current_user)) -> UserPublic:
    return current_user


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    current_user: UserPublic = Depends(get_current_user),
) -> MessageResponse:
    request.app.state.auth_service.logout(credentials.credentials)
    return MessageResponse(detail=f"Sesión cerrada para {current_user.username}.")
