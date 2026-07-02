from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.dependencies.auth import get_current_user
from app.schemas.auth import UserPublic
from app.core.config import settings
from app.schemas.api import PreviewImageResponse
from app.services.image_service import encode_png_base64, load_image_from_upload, resize_for_preview

router = APIRouter()


@router.post("", response_model=PreviewImageResponse)
async def generate_preview(
    file: UploadFile = File(...),
    current_user: UserPublic = Depends(get_current_user),
) -> PreviewImageResponse:
    """Carga una imagen o GeoTIFF y devuelve previsualizacion junto con metadatos geoespaciales.

    Esta ruta permite al frontend mostrar la parcela antes de ejecutar el modelo.
    Para GeoTIFF conserva resolucion, CRS, transformacion afin, area, centro y
    fecha de adquisicion cuando estan disponibles.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Archivo vacío.")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande. Máximo permitido: {settings.max_upload_mb} MB.",
        )

    try:
        loaded = load_image_from_upload(content, file.filename or "upload.bin")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    source_height, source_width = loaded.image_rgb.shape[:2]
    preview = resize_for_preview(loaded.image_rgb, max_side=1920)
    preview_height, preview_width = preview.shape[:2]

    return PreviewImageResponse(
        file_type=loaded.file_type,
        source_width=int(source_width),
        source_height=int(source_height),
        preview_width=int(preview_width),
        preview_height=int(preview_height),
        resolution_x=float(loaded.resolution_x),
        resolution_y=float(loaded.resolution_y),
        resolution_unit=loaded.resolution_unit,
        crs=loaded.crs,
        parcel_area_hectares=loaded.parcel_area_hectares,
        location_center_lat=loaded.location_center_lat,
        location_center_lon=loaded.location_center_lon,
        acquisition_date=loaded.acquisition_date,
        preview_png_base64=encode_png_base64(preview),
    )
