from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import sessionmaker

from app.db.models import SessionModel
from app.schemas.auth import UserPublic
from app.services.user_service import UserService


class AuthService:
    """Gestiona login, logout y validacion de tokens persistidos en base de datos."""
    def __init__(
        self,
        user_service: UserService,
        session_factory: sessionmaker,
        session_ttl_minutes: int,
    ) -> None:
        self.user_service = user_service
        self._sf = session_factory
        self.session_ttl_minutes = session_ttl_minutes

    def login(self, username: str, password: str) -> tuple[str, datetime, UserPublic]:
        user = self.user_service.authenticate(username, password)
        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=self.session_ttl_minutes)
        with self._sf() as db:
            self._purge_expired(db)
            db.add(SessionModel(token=token, user_id=user.id, expires_at=expires_at))
            db.commit()
        return token, expires_at, user

    def logout(self, token: str) -> None:
        with self._sf() as db:
            db.query(SessionModel).filter(SessionModel.token == token).delete()
            db.commit()

    def authenticate_token(self, token: str) -> UserPublic:
        with self._sf() as db:
            self._purge_expired(db)
            session = db.query(SessionModel).filter(SessionModel.token == token).first()
            user_id: str | None = session.user_id if session else None
            db.commit()

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión no válida o expirada.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = self.user_service.get_by_id(user_id)
        if user is None or not user.is_active:
            with self._sf() as db:
                db.query(SessionModel).filter(SessionModel.token == token).delete()
                db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión no válida o expirada.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user.to_public()

    def _purge_expired(self, db) -> None:
        db.query(SessionModel).filter(SessionModel.expires_at <= datetime.utcnow()).delete()
