from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.dependencies.auth import require_admin
from app.schemas.auth import (
    CreateUserRequest,
    MessageResponse,
    ResetPasswordRequest,
    UpdateUserRequest,
    UserPublic,
)

router = APIRouter()


@router.get("", response_model=list[UserPublic], dependencies=[Depends(require_admin)])
def list_users(request: Request) -> list[UserPublic]:
    return request.app.state.user_service.list_users()


@router.get("/{user_id}", response_model=UserPublic, dependencies=[Depends(require_admin)])
def get_user(request: Request, user_id: str) -> UserPublic:
    return request.app.state.user_service.get_public_user(user_id)


@router.post("", response_model=UserPublic, dependencies=[Depends(require_admin)])
def create_user(request: Request, payload: CreateUserRequest) -> UserPublic:
    return request.app.state.user_service.create_user(payload)


@router.patch("/{user_id}", response_model=UserPublic, dependencies=[Depends(require_admin)])
def update_user(
    request: Request,
    user_id: str,
    payload: UpdateUserRequest,
    admin_user: UserPublic = Depends(require_admin),
) -> UserPublic:
    return request.app.state.user_service.update_user(user_id, payload, actor_id=admin_user.id)


@router.post("/{user_id}/reset-password", response_model=MessageResponse, dependencies=[Depends(require_admin)])
def reset_password(
    request: Request,
    user_id: str,
    payload: ResetPasswordRequest,
) -> MessageResponse:
    user = request.app.state.user_service.reset_password(user_id, payload.new_password)
    return MessageResponse(detail=f"Contraseña actualizada para {user.username}.")


@router.delete("/{user_id}", response_model=MessageResponse, dependencies=[Depends(require_admin)])
def delete_user(
    request: Request,
    user_id: str,
    admin_user: UserPublic = Depends(require_admin),
) -> MessageResponse:
    user = request.app.state.user_service.delete_user(user_id, actor_id=admin_user.id)
    return MessageResponse(detail=f"Usuario {user.username} eliminado correctamente.")
