from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password, verify_password
from app.db.models import UserModel
from app.schemas.auth import CreateUserRequest, UpdateUserRequest, UserPublic, UserRole


# ── Internal representation (keeps AuthService unchanged) ───────────

@dataclass
class StoredUser:
    id: str
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    password_hash: str
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None

    def to_public(self) -> UserPublic:
        return UserPublic(
            id=self.id,
            username=self.username,
            full_name=self.full_name,
            role=self.role,
            is_active=self.is_active,
            created_at=self.created_at,
            updated_at=self.updated_at,
            last_login_at=self.last_login_at,
        )


def _to_stored(row: UserModel) -> StoredUser:
    return StoredUser(
        id=row.id,
        username=row.username,
        full_name=row.full_name,
        role=UserRole(row.role),
        is_active=row.is_active,
        password_hash=row.password_hash,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_login_at=row.last_login_at,
    )


def _to_public(row: UserModel) -> UserPublic:
    return UserPublic(
        id=row.id,
        username=row.username,
        full_name=row.full_name,
        role=UserRole(row.role),
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_login_at=row.last_login_at,
    )


# ── Service ─────────────────────────────────────────────────────────

class UserService:
    def __init__(
        self,
        session_factory: sessionmaker,
        legacy_users_file: Path | None = None,
    ) -> None:
        self._sf = session_factory
        self._ensure_users(legacy_users_file)

    # ── Public read API ─────────────────────────────────────────────

    def list_users(self) -> list[UserPublic]:
        with self._sf() as db:
            rows = db.query(UserModel).order_by(UserModel.username).all()
            return [_to_public(r) for r in rows]

    def get_public_user(self, user_id: str) -> UserPublic:
        with self._sf() as db:
            row = db.get(UserModel, user_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Usuario no encontrado.")
            return _to_public(row)

    def get_by_username(self, username: str) -> StoredUser | None:
        normalized = username.strip().lower()
        with self._sf() as db:
            row = db.query(UserModel).filter(UserModel.username.ilike(normalized)).first()
            return _to_stored(row) if row else None

    def get_by_id(self, user_id: str) -> StoredUser | None:
        with self._sf() as db:
            row = db.get(UserModel, user_id)
            return _to_stored(row) if row else None

    # ── Auth ────────────────────────────────────────────────────────

    def authenticate(self, username: str, password: str) -> UserPublic:
        user = self.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario o contraseña incorrectos.",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El usuario está desactivado. Contacte con un administrador.",
            )
        now = datetime.utcnow()
        with self._sf() as db:
            row = db.get(UserModel, user.id)
            if row:
                row.last_login_at = now
                row.updated_at = now
                db.commit()
        user.last_login_at = now
        user.updated_at = now
        return user.to_public()

    # ── Write API ───────────────────────────────────────────────────

    def create_user(self, payload: CreateUserRequest) -> UserPublic:
        username = payload.username.strip()
        full_name = payload.full_name.strip()
        if not username:
            raise HTTPException(status_code=422, detail="El nombre de usuario es obligatorio.")
        if not full_name:
            raise HTTPException(status_code=422, detail="El nombre completo es obligatorio.")

        with self._sf() as db:
            if db.query(UserModel).filter(UserModel.username.ilike(username)).first():
                raise HTTPException(status_code=409, detail="Ya existe un usuario con ese nombre.")
            now = datetime.utcnow()
            row = UserModel(
                id=str(uuid4()),
                username=username,
                full_name=full_name,
                role=payload.role.value,
                is_active=payload.is_active,
                password_hash=hash_password(payload.password),
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.commit()
            return _to_public(row)

    def update_user(self, user_id: str, payload: UpdateUserRequest, actor_id: str) -> UserPublic:
        with self._sf() as db:
            row = db.get(UserModel, user_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Usuario no encontrado.")

            if payload.full_name is not None:
                full_name = payload.full_name.strip()
                if not full_name:
                    raise HTTPException(status_code=422, detail="El nombre completo es obligatorio.")
                row.full_name = full_name

            if payload.role is not None:
                if user_id == actor_id and payload.role != UserRole.admin:
                    raise HTTPException(
                        status_code=400,
                        detail="No puede retirarse a sí mismo el rol de administrador.",
                    )
                row.role = payload.role.value

            if payload.is_active is not None:
                if user_id == actor_id and not payload.is_active:
                    raise HTTPException(status_code=400, detail="No puede desactivar su propia cuenta.")
                row.is_active = payload.is_active

            row.updated_at = datetime.utcnow()
            db.commit()
            return _to_public(row)

    def reset_password(self, user_id: str, new_password: str) -> UserPublic:
        with self._sf() as db:
            row = db.get(UserModel, user_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Usuario no encontrado.")
            row.password_hash = hash_password(new_password)
            row.updated_at = datetime.utcnow()
            db.commit()
            return _to_public(row)

    def delete_user(self, user_id: str, actor_id: str) -> StoredUser:
        with self._sf() as db:
            row = db.get(UserModel, user_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Usuario no encontrado.")
            if row.id == actor_id:
                raise HTTPException(status_code=400, detail="No puede eliminar su propia cuenta.")
            if row.role == "admin":
                admin_count = db.query(UserModel).filter(UserModel.role == "admin").count()
                if admin_count <= 1:
                    raise HTTPException(status_code=400, detail="No se puede eliminar el último administrador.")
            stored = _to_stored(row)
            db.delete(row)
            db.commit()
            return stored

    # ── Bootstrap / migration ────────────────────────────────────────

    def _ensure_users(self, legacy_file: Path | None) -> None:
        with self._sf() as db:
            if db.query(UserModel).count() > 0:
                self._migrate_removed_roles(db)
                return
            rows = self._load_from_json(legacy_file) if legacy_file and legacy_file.exists() else []
            if not rows:
                rows = self._default_rows()
            for row in rows:
                db.add(row)
            db.commit()

    def _migrate_removed_roles(self, db) -> None:
        changed = (
            db.query(UserModel)
            .filter(UserModel.role == "viewer")
            .update({
                UserModel.role: UserRole.operator.value,
                UserModel.updated_at: datetime.utcnow(),
            })
        )
        if changed:
            db.commit()

    def _load_from_json(self, path: Path) -> list[UserModel]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            rows: list[UserModel] = []
            for item in data.get("users", []):
                role = str(item["role"])
                if role == "viewer":
                    role = UserRole.operator.value
                rows.append(UserModel(
                    id=str(item["id"]),
                    username=str(item["username"]),
                    full_name=str(item["full_name"]),
                    role=role,
                    is_active=bool(item["is_active"]),
                    password_hash=str(item["password_hash"]),
                    created_at=datetime.fromisoformat(str(item["created_at"])),
                    updated_at=datetime.fromisoformat(str(item["updated_at"])),
                    last_login_at=(
                        datetime.fromisoformat(str(item["last_login_at"]))
                        if item.get("last_login_at") else None
                    ),
                ))
            return rows
        except Exception:
            return []

    def _default_rows(self) -> list[UserModel]:
        now = datetime.utcnow()
        return [
            UserModel(id=str(uuid4()), username="admin",     full_name="Administrador del sistema",
                      role="admin",    is_active=True, password_hash=hash_password("admin123"),
                      created_at=now, updated_at=now),
            UserModel(id=str(uuid4()), username="operario1", full_name="Operario de campo",
                      role="operator", is_active=True, password_hash=hash_password("operario123"),
                      created_at=now, updated_at=now),
        ]
