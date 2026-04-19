from fastapi import APIRouter, Request

from app.core.config import settings
from app.schemas.api import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    registry = request.app.state.model_registry
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=settings.app_version,
        device=registry.device,
        model_loaded=registry.is_model_available(),
        yolo_cam_available=registry.yolo_cam_available,
        model_path=str(registry.model_path),
    )

