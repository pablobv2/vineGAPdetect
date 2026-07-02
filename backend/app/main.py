"""Punto de entrada de la API FastAPI de vineGAPdetect.

El modulo compone la aplicacion backend: inicializa la base de datos SQLite,
crea los servicios de usuarios, autenticacion, gestion de jobs, inferencia y
explicabilidad, configura CORS para el frontend y registra todas las rutas bajo
el prefijo de API. El ciclo de vida inicia el worker de trabajos al arrancar y
lo detiene al cerrar la aplicacion.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.db.database import init_db
from app.services.auth_service import AuthService
from app.services.inference_service import InferenceService
from app.services.job_manager import JobManager
from app.services.model_registry import ModelRegistry
from app.services.user_service import UserService
from app.services.xai_service import XAIService


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine, session_factory = init_db(settings.database_url)

    model_registry = ModelRegistry(settings)
    job_manager = JobManager(
        cleanup_seconds=settings.job_cleanup_seconds,
        cleanup_interval_seconds=settings.job_cleanup_interval_seconds,
    )
    user_service = UserService(session_factory, legacy_users_file=settings.users_file_path)
    auth_service = AuthService(user_service, session_factory, session_ttl_minutes=settings.auth_session_ttl_minutes)
    xai_service = XAIService(model_registry)
    inference_service = InferenceService(model_registry, session_factory=session_factory)

    app.state.model_registry = model_registry
    app.state.job_manager = job_manager
    app.state.user_service = user_service
    app.state.auth_service = auth_service
    app.state.inference_service = inference_service
    app.state.xai_service = xai_service

    job_manager.start()
    yield
    job_manager.stop()
    engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)
