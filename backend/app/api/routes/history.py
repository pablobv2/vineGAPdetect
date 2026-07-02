from __future__ import annotations

import json
import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status

from sqlalchemy import func

from app.api.dependencies.auth import get_current_user
from app.core.config import settings
from app.db.models import AnalysisHistory, UserModel
from app.schemas.api import (
    AnalysisHistoryDetail,
    AnalysisHistoryItem,
    JobAcceptedResponse,
    JobType,
    QuotaResponse,
    SaveParcelResponse,
)
from app.schemas.auth import UserPublic
from app.services.image_service import encode_preview_jpeg, load_image_from_upload

router = APIRouter()


def _parse_transform(value: str | None) -> list[float] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list) or len(parsed) != 6:
        return None
    try:
        return [float(item) for item in parsed]
    except (TypeError, ValueError):
        return None


def _parse_layers(value: str | None) -> list[int]:
    if value is None or not value.strip():
        return [18]
    layers: list[int] = []
    for item in value.split(","):
        part = item.strip()
        if part:
            layers.append(int(part))
    return layers or [18]


def _artifact_path(row: AnalysisHistory) -> Path | None:
    raw = row.source_artifact_path
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (settings.repo_root / path).resolve()
    return path


def _ensure_history_access(row: AnalysisHistory, current_user: UserPublic) -> None:
    if current_user.role != "admin" and row.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Acceso no autorizado.")


def _ensure_source_hash(row: AnalysisHistory) -> str | None:
    if row.source_sha256:
        return row.source_sha256
    artifact_path = _artifact_path(row)
    if artifact_path is None or not artifact_path.exists():
        return None
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    row.source_sha256 = digest
    row.source_file_size_bytes = row.source_file_size_bytes or artifact_path.stat().st_size
    return digest


def _find_saved_duplicate(db, row: AnalysisHistory) -> AnalysisHistory | None:
    digest = _ensure_source_hash(row)
    query = db.query(AnalysisHistory).filter(
        AnalysisHistory.user_id == row.user_id,
        AnalysisHistory.saved == True,  # noqa: E712
        AnalysisHistory.id != row.id,
    )
    if digest:
        duplicate = query.filter(AnalysisHistory.source_sha256 == digest).first()
        if duplicate is not None:
            return duplicate
        if row.source_file_size_bytes:
            candidates = query.filter(
                AnalysisHistory.source_file_size_bytes == row.source_file_size_bytes,
                AnalysisHistory.source_artifact_path.isnot(None),
            ).all()
            for candidate in candidates:
                if _ensure_source_hash(candidate) == digest:
                    return candidate

    filename = row.original_filename or row.filename
    file_size = row.source_file_size_bytes
    if filename and file_size:
        return query.filter(
            AnalysisHistory.original_filename == filename,
            AnalysisHistory.source_file_size_bytes == file_size,
        ).first()
    return None


def _select_detection(result_json: str | None, detection_id: int | None, conf_threshold: float) -> dict:
    if not result_json:
        raise HTTPException(status_code=409, detail="Este registro no tiene detecciones almacenadas.")
    try:
        result = json.loads(result_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=409, detail="El resultado almacenado no es JSON valido.") from exc
    detections = result.get("detections") if isinstance(result, dict) else None
    if not isinstance(detections, list) or not detections:
        raise HTTPException(status_code=409, detail="Este registro no tiene detecciones disponibles para XAI.")

    if detection_id is not None:
        selected = next((d for d in detections if int(d.get("id", -1)) == detection_id), None)
        if selected is None:
            raise HTTPException(status_code=404, detail=f"Deteccion #{detection_id} no encontrada en este historial.")
        return selected

    sorted_detections = sorted(
        detections,
        key=lambda d: float(d.get("confidence", 0.0)),
        reverse=True,
    )
    return next(
        (d for d in sorted_detections if float(d.get("confidence", 0.0)) >= conf_threshold),
        sorted_detections[0],
    )


def _get_used_bytes(db, user_id: str) -> int:
    result = db.query(func.sum(AnalysisHistory.source_file_size_bytes)).filter(
        AnalysisHistory.user_id == user_id,
        AnalysisHistory.saved == True,  # noqa: E712
    ).scalar()
    return int(result or 0)


def _history_item(row: AnalysisHistory, username: str | None) -> AnalysisHistoryItem:
    artifact_path = _artifact_path(row)
    return AnalysisHistoryItem(
        id=row.id,
        user_id=row.user_id,
        username=username,
        filename=row.original_filename or row.filename,
        original_filename=row.original_filename or row.filename,
        executed_at=row.executed_at,
        detection_count=row.detection_count,
        all_detection_count=row.all_detection_count or row.detection_count,
        mean_confidence=row.mean_confidence,
        estimated_missing=row.estimated_missing,
        processing_time_s=row.processing_time_s,
        display_confidence_threshold=row.display_confidence_threshold,
        capture_confidence_threshold=row.capture_confidence_threshold,
        typical_vine_width=row.typical_vine_width,
        slice_size=row.slice_size,
        overlap_ratio=row.overlap_ratio,
        model_path=row.model_path,
        source_width=row.source_width,
        source_height=row.source_height,
        file_type=row.file_type,
        resolution_x=row.resolution_x,
        resolution_y=row.resolution_y,
        resolution_unit=row.resolution_unit,
        crs=row.crs,
        transform=_parse_transform(row.transform_json),
        parcel_area_hectares=row.parcel_area_hectares,
        location_center_lat=row.location_center_lat,
        location_center_lon=row.location_center_lon,
        acquisition_date=row.acquisition_date,
        has_source_artifact=bool(artifact_path and artifact_path.exists()),
        saved=bool(row.saved),
        source_file_size_bytes=row.source_file_size_bytes,
    )


@router.get("/quota", response_model=QuotaResponse)
def get_user_quota(
    request: Request,
    current_user: UserPublic = Depends(get_current_user),
) -> QuotaResponse:
    """Devuelve el espacio usado y el limite de almacenamiento del usuario.

    Calcula la cuota a partir de las parcelas guardadas en el historico y
    permite al frontend bloquear nuevas conservaciones antes de superar el
    maximo configurado para cada cuenta.
    """
    session_factory = request.app.state.auth_service._sf
    with session_factory() as db:
        used = _get_used_bytes(db, current_user.id)
    return QuotaResponse(used_bytes=used, total_bytes=settings.user_storage_quota_bytes)


@router.get("", response_model=list[AnalysisHistoryItem])
def get_history(
    request: Request,
    limit: int = 200,
    current_user: UserPublic = Depends(get_current_user),
) -> list[AnalysisHistoryItem]:
    """Lista analisis historicos visibles para el usuario autenticado.

    Los administradores consultan todos los registros y los operarios solo los
    suyos. La respuesta contiene resumenes, parametros usados y metadatos de
    imagen suficientes para navegar y filtrar el historico.
    """
    session_factory = request.app.state.auth_service._sf

    with session_factory() as db:
        query = db.query(AnalysisHistory, UserModel.username).outerjoin(
            UserModel, AnalysisHistory.user_id == UserModel.id
        ).filter(
            AnalysisHistory.saved == True,  # noqa: E712
            AnalysisHistory.source_artifact_path.isnot(None),
        )
        if current_user.role != "admin":
            query = query.filter(AnalysisHistory.user_id == current_user.id)
        rows = query.order_by(AnalysisHistory.executed_at.desc()).limit(limit).all()

    return [_history_item(row, username) for row, username in rows]


@router.delete("/{history_id}", status_code=204)
def delete_history_item(
    request: Request,
    history_id: int,
    current_user: UserPublic = Depends(get_current_user),
) -> None:
    """Borra un analisis historico y su artefacto fuente si existe."""
    session_factory = request.app.state.auth_service._sf
    with session_factory() as db:
        row = db.query(AnalysisHistory).filter(AnalysisHistory.id == history_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Registro no encontrado.")
        _ensure_history_access(row, current_user)
        artifact_path = _artifact_path(row)
        db.delete(row)
        db.commit()
    if artifact_path and artifact_path.exists():
        try:
            artifact_path.unlink()
        except OSError:
            pass


@router.post("/{history_id}/save", response_model=SaveParcelResponse)
def save_history_item(
    request: Request,
    history_id: int,
    current_user: UserPublic = Depends(get_current_user),
) -> SaveParcelResponse:
    """Marca una inferencia historica como parcela guardada del usuario.

    Verifica permisos, evita duplicados por hash o metadatos de fichero,
    comprueba la cuota disponible y conserva el registro para que aparezca en
    Mis parcelas sin duplicar el artefacto fuente.
    """
    session_factory = request.app.state.auth_service._sf
    with session_factory() as db:
        row = db.query(AnalysisHistory).filter(AnalysisHistory.id == history_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Registro no encontrado.")
        _ensure_history_access(row, current_user)

        if row.saved:
            used = _get_used_bytes(db, current_user.id)
            return SaveParcelResponse(saved=True, used_bytes=used, total_bytes=settings.user_storage_quota_bytes)

        duplicate = _find_saved_duplicate(db, row)
        if duplicate is not None:
            db.commit()
            raise HTTPException(
                status_code=409,
                detail="Esta parcela ya esta guardada en Mis parcelas.",
            )

        file_size = int(row.source_file_size_bytes or 0)
        used = _get_used_bytes(db, current_user.id)

        if used + file_size > settings.user_storage_quota_bytes:
            used_gb = used / (1024 ** 3)
            raise HTTPException(
                status_code=409,
                detail=(
                    f"No hay suficiente espacio en el inventario del usuario "
                    f"({used_gb:.2f} GB de 5 GB usados). "
                    "Libera espacio eliminando parcelas desde Mis parcelas."
                ),
            )

        row.saved = True
        db.commit()
        used_after = _get_used_bytes(db, current_user.id)

    return SaveParcelResponse(saved=True, used_bytes=used_after, total_bytes=settings.user_storage_quota_bytes)


@router.post("/{history_id}/xai", response_model=JobAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def create_history_xai_job(
    request: Request,
    history_id: int,
    detection_id: int | None = Form(None),
    xai_scope: str = Form("patch"),
    conf_threshold: float = Form(settings.default_xai_confidence_threshold),
    target_layers: str | None = Form(None),
    imgsz: int = Form(settings.default_xai_imgsz),
    current_user: UserPublic = Depends(get_current_user),
) -> JobAcceptedResponse:
    """Crea un trabajo XAI reutilizando la imagen original guardada en el historial.

    Recupera el artefacto fuente persistido, selecciona la deteccion indicada o
    la mejor segun umbral, calcula su centro y lanza un job Eigen-CAM enfocado
    sobre esa marra sin repetir la inferencia completa.
    """
    session_factory = request.app.state.auth_service._sf
    with session_factory() as db:
        row = db.query(AnalysisHistory).filter(AnalysisHistory.id == history_id).first()

    if row is None:
        raise HTTPException(status_code=404, detail="Registro no encontrado.")
    _ensure_history_access(row, current_user)

    artifact_path = _artifact_path(row)
    if artifact_path is None or not artifact_path.exists():
        raise HTTPException(
            status_code=409,
            detail=(
                "Este analisis historico no conserva el TIFF original. "
                "Vuelva a ejecutar la inferencia una vez para crear un historial con artefacto fuente y XAI fiable."
            ),
        )

    try:
        layers = _parse_layers(target_layers)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"target_layers invalido: {exc}") from exc

    scope_normalized = xai_scope.strip().lower()
    if scope_normalized not in {"patch", "full"}:
        raise HTTPException(status_code=422, detail="Ambito XAI no soportado. Use patch o full.")

    bbox_values = None
    cx = None
    cy = None
    selected = None
    if scope_normalized == "patch":
        selected = _select_detection(row.result_json, detection_id, conf_threshold)
        bbox = selected.get("bbox_xyxy")
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise HTTPException(status_code=409, detail="La deteccion seleccionada no tiene bbox valida.")
        bbox_values = [float(value) for value in bbox]
        cx = int(round((bbox_values[0] + bbox_values[2]) / 2))
        cy = int(round((bbox_values[1] + bbox_values[3]) / 2))

    payload = {
        "file_bytes": artifact_path.read_bytes(),
        "filename": row.original_filename or row.filename,
        "method": "eigencam",
        "xai_scope": scope_normalized,
        "target_layers": layers,
        "conf_threshold": conf_threshold,
        "imgsz": imgsz,
        "cx": cx,
        "cy": cy,
        "focus_bbox": bbox_values,
        "focus_confidence": selected.get("confidence") if selected else None,
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


@router.get("/{history_id}", response_model=AnalysisHistoryDetail)
def get_history_item(
    request: Request,
    history_id: int,
    current_user: UserPublic = Depends(get_current_user),
) -> AnalysisHistoryDetail:
    """Recupera detalle, previsualizacion, resultado y XAI almacenados de un analisis.

    Devuelve la informacion necesaria para restaurar el dashboard: imagen
    previsualizada, JSON de detecciones, parametros de ejecucion, metadatos
    geoespaciales y mapa XAI precalculado si existe.
    """
    session_factory = request.app.state.auth_service._sf

    with session_factory() as db:
        result = db.query(AnalysisHistory, UserModel.username).outerjoin(
            UserModel, AnalysisHistory.user_id == UserModel.id
        ).filter(AnalysisHistory.id == history_id).first()

    if result is None:
        raise HTTPException(status_code=404, detail="Registro no encontrado.")

    row, username = result
    _ensure_history_access(row, current_user)

    item = _history_item(row, username)
    artifact_path = _artifact_path(row)
    if artifact_path is None or not artifact_path.exists():
        raise HTTPException(
            status_code=409,
            detail="Esta parcela no conserva el GeoTIFF original y no puede restaurarse con la logica actual.",
        )

    source_bytes = artifact_path.read_bytes()
    loaded = load_image_from_upload(source_bytes, row.original_filename or row.filename)
    preview_b64 = encode_preview_jpeg(loaded.image_rgb, max_side=800, quality=75)

    return AnalysisHistoryDetail(
        **item.model_dump(),
        preview_png_b64=preview_b64,
        result_json=row.result_json,
    )
