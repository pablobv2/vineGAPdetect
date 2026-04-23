from fastapi import APIRouter, Depends, Request

from app.api.dependencies.auth import get_current_user
from app.schemas.auth import UserPublic
from app.core.config import settings
from app.schemas.api import ModelInfoResponse

router = APIRouter()


@router.get("/info", response_model=ModelInfoResponse)
def model_info(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> ModelInfoResponse:
    registry = request.app.state.model_registry
    xai_methods = ["eigencam"] if registry.yolo_cam_available else []
    return ModelInfoResponse(
        model_path=str(registry.model_path),
        device=registry.device,
        xai_methods=xai_methods,
        default_slice_size=settings.default_slice_size,
        max_upload_mb=settings.max_upload_mb,
    )
