from __future__ import annotations

import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.api.dependencies.auth import get_current_user
from app.schemas.api import ExportDetectionsRequest
from app.schemas.auth import UserPublic
from app.services.gpkg_export import build_detections_gpkg

router = APIRouter()


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-")
    return cleaned or "marras"


@router.post("/detections-gpkg")
def export_detections_gpkg(
    payload: ExportDetectionsRequest,
    current_user: UserPublic = Depends(get_current_user),
) -> Response:
    """Genera un GeoPackage con las detecciones georreferenciadas del analisis.

    Recibe detecciones filtradas, CRS y transformacion afin del GeoTIFF original,
    convierte poligonos OBB de pixeles a coordenadas reales y devuelve un
    fichero GPKG descargable para uso en software GIS.
    """
    try:
        data = build_detections_gpkg(
            detections=[det.model_dump() for det in payload.detections],
            transform=payload.transform,
            crs=payload.crs,
            parcel_name=payload.parcel_name,
            conf_threshold=payload.conf_threshold,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - GDAL/fiona internal failures
        raise HTTPException(
            status_code=500,
            detail=f"Error generando el GeoPackage: {exc}",
        ) from exc

    base = _sanitize_filename(payload.parcel_name or "marras")
    filename = f"{base}_marras.gpkg"
    return Response(
        content=data,
        media_type="application/geopackage+sqlite3",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(filename)}',
        },
    )
