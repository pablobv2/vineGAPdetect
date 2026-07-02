from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion central de API, rutas de datos, modelo, trabajos y valores por defecto.

    Reune en una unica clase los parametros que condicionan el despliegue:
    prefijo de API, origen permitido para CORS, ubicacion de SQLite, carpeta de
    artefactos historicos, ruta del modelo YOLO, dispositivo de inferencia y
    valores por defecto usados en inferencia y explicabilidad.
    """
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "VineDetect API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"

    frontend_origin: str = "http://localhost:5173"
    users_file_relative_path: str = "backend/data/users.json"
    database_relative_path: str = "backend/data/vinedetect.db"
    history_artifact_dir_relative_path: str = "backend/data/history_artifacts"
    auth_session_ttl_minutes: int = 480

    max_upload_mb: int = 1024
    job_cleanup_seconds: int = 1800
    job_cleanup_interval_seconds: int = 60
    worker_count: int = 1

    default_confidence_threshold: float = 0.55
    default_overlap_ratio: float = 0.2
    default_typical_vine_width: float = 1.5
    default_slice_size: int = 640
    default_xai_confidence_threshold: float = 0.55
    default_xai_imgsz: int = 640

    device: str = ""
    model_relative_path: str = "ml/models/trained/best.pt"
    yolo_cam_relative_path: str = "ml/scripts"

    @property
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[3]

    def _resolve_model_config_path(self) -> Path:
        raw_path = self.model_relative_path.strip()
        if not raw_path:
            raw_path = "ml/models/trained/best.pt"

        path = Path(raw_path)
        if path.is_absolute():
            return path.resolve()

        # Handle Windows-style rooted paths like "\vineGAPdetect-main\...".
        if raw_path.startswith(("\\", "/")):
            raw_path = raw_path.lstrip("\\/")
            path = Path(raw_path)

        return (self.repo_root / path).resolve()

    def _model_fallback_candidates(self) -> list[Path]:
        return [
            (self.repo_root / "ml/models/trained/best.pt").resolve(),
            (self.repo_root / "ml/results/vineGAPdetect_Training/nano_640px/weights/best.pt").resolve(),
        ]

    @property
    def model_path(self) -> Path:
        configured = self._resolve_model_config_path()
        if configured.exists():
            return configured

        for candidate in self._model_fallback_candidates():
            if candidate.exists():
                return candidate
        return configured

    @property
    def yolo_cam_path(self) -> Path:
        return (self.repo_root / self.yolo_cam_relative_path).resolve()

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def allowed_origins(self) -> list[str]:
        origins: list[str] = []
        for host in ("localhost", "127.0.0.1"):
            for port in ("5173", "5174", "5175", "5176"):
                origins.append(f"http://{host}:{port}")
        if self.frontend_origin not in origins:
            origins.append(self.frontend_origin)
        return origins

    @property
    def database_url(self) -> str:
        db_path = (self.repo_root / self.database_relative_path).resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"

    @property
    def history_artifact_dir(self) -> Path:
        path = (self.repo_root / self.history_artifact_dir_relative_path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def user_storage_quota_bytes(self) -> int:
        return 5 * 1024 * 1024 * 1024  # 5 GB per user

    @property
    def users_file_path(self) -> Path:
        return (self.repo_root / self.users_file_relative_path).resolve()


settings = Settings()
