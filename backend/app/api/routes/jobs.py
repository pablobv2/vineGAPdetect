from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.api.dependencies.auth import get_current_user, require_operator_or_admin
from app.core.config import settings
from app.schemas.api import DeleteJobResponse, JobAcceptedResponse, JobStatus, JobStatusResponse, JobType
from app.schemas.auth import UserPublic

router = APIRouter()


def _parse_layers(value: str) -> list[int]:
    parsed: list[int] = []
    for item in value.split(","):
        part = item.strip()
        if not part:
            continue
        parsed.append(int(part))
    return parsed


def _parse_focus_bbox(value: str | None) -> list[float] | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"focus_bbox invalido: {exc}") from exc
    if not isinstance(parsed, list) or len(parsed) != 4:
        raise HTTPException(status_code=422, detail="focus_bbox debe ser una lista [x1, y1, x2, y2].")
    try:
        return [float(item) for item in parsed]
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"focus_bbox invalido: {exc}") from exc


async def _read_upload_or_400(file: UploadFile) -> bytes:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Archivo vacío.")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande. Máximo permitido: {settings.max_upload_mb} MB.",
        )
    return content


@router.post("/inference", response_model=JobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_inference_job(
    request: Request,
    file: UploadFile = File(...),
    confidence_threshold: float = Form(settings.default_confidence_threshold),
    display_confidence_threshold: float = Form(settings.default_confidence_threshold),
    overlap_ratio: float = Form(settings.default_overlap_ratio),
    typical_vine_width: float = Form(settings.default_typical_vine_width),
    slice_size: int = Form(settings.default_slice_size),
    current_user: UserPublic = Depends(require_operator_or_admin),
) -> JobAcceptedResponse:
    content = await _read_upload_or_400(file)

    if not request.app.state.model_registry.is_model_available():
        model_path = request.app.state.model_registry.model_path
        raise HTTPException(
            status_code=500,
            detail=f"Modelo no encontrado en la ruta configurada: {model_path}",
        )

    payload = {
        "file_bytes": content,
        "filename": file.filename or "upload.bin",
        "confidence_threshold": confidence_threshold,
        "display_confidence_threshold": display_confidence_threshold,
        "overlap_ratio": overlap_ratio,
        "typical_vine_width": typical_vine_width,
        "slice_size": slice_size,
        "user_id": current_user.id,
    }
    record = request.app.state.job_manager.submit(
        job_type=JobType.inference,
        handler=request.app.state.inference_service.run,
        payload=payload,
    )

    return JobAcceptedResponse(
        job_id=record.job_id,
        job_type=record.job_type,
        status=record.status,
        created_at=record.created_at,
    )


@router.post("/xai", response_model=JobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_xai_job(
    request: Request,
    file: UploadFile = File(...),
    method: str = Form("eigencam"),
    xai_scope: str = Form("patch"),
    target_layers: str | None = Form(None),
    conf_threshold: float = Form(settings.default_xai_confidence_threshold),
    imgsz: int = Form(settings.default_xai_imgsz),
    cx: int | None = Form(None),
    cy: int | None = Form(None),
    focus_bbox: str | None = Form(None),
    focus_confidence: float | None = Form(None),
    current_user: UserPublic = Depends(require_operator_or_admin),
) -> JobAcceptedResponse:
    content = await _read_upload_or_400(file)
    method_normalized = method.strip().lower()
    scope_normalized = xai_scope.strip().lower()
    if scope_normalized not in {"patch", "full"}:
        raise HTTPException(status_code=422, detail="Ambito XAI no soportado. Use patch o full.")
    if method_normalized != "eigencam":
        raise HTTPException(status_code=422, detail="Método XAI no soportado. Use eigencam.")

    if not request.app.state.model_registry.yolo_cam_available:
        raise HTTPException(status_code=500, detail="Dependencia yolo_cam no disponible en backend.")

    if target_layers is None or not target_layers.strip():
        layers = []
    else:
        try:
            layers = _parse_layers(target_layers)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"target_layers inválido: {exc}") from exc

    parsed_focus_bbox = _parse_focus_bbox(focus_bbox)

    payload = {
        "file_bytes": content,
        "filename": file.filename or "upload.bin",
        "method": "eigencam",
        "xai_scope": scope_normalized,
        "target_layers": layers,
        "conf_threshold": conf_threshold,
        "imgsz": imgsz,
        "cx": cx,
        "cy": cy,
        "focus_bbox": parsed_focus_bbox,
        "focus_confidence": focus_confidence,
    }
    record = request.app.state.job_manager.submit(
        job_type=JobType.xai,
        handler=request.app.state.xai_service.run,
        payload=payload,
    )

    return JobAcceptedResponse(
        job_id=record.job_id,
        job_type=record.job_type,
        status=record.status,
        created_at=record.created_at,
    )


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    request: Request,
    job_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> JobStatusResponse:
    record = request.app.state.job_manager.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job no encontrado.")

    return JobStatusResponse(
        job_id=record.job_id,
        job_type=record.job_type,
        status=record.status,
        progress=record.progress,
        created_at=record.created_at,
        started_at=record.started_at,
        ended_at=record.ended_at,
        error=record.error,
        result=record.result,
    )


@router.delete("/{job_id}", response_model=DeleteJobResponse)
def delete_job(
    request: Request,
    job_id: str,
    current_user: UserPublic = Depends(get_current_user),
) -> DeleteJobResponse:
    deleted = request.app.state.job_manager.delete(job_id)
    if not deleted:
        record = request.app.state.job_manager.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Job no encontrado.")
        if record.status in {JobStatus.queued, JobStatus.running}:
            raise HTTPException(status_code=409, detail="No se puede eliminar un job en ejecución.")
    return DeleteJobResponse(deleted=deleted)
